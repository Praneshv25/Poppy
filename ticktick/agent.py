#!/usr/bin/env python3
"""
TickTick Sub-Agent — A self-contained task management agent that can be called
by the main robot agent (speedDemon) or any other agent.

Maintains a persistent MCP server connection in a background thread and exposes
a simple interface:

    from ticktick.agent import TickTickAgent

    agent = TickTickAgent()
    agent.start()                              # boots MCP server, connects
    result = agent.ask("Add a task: buy milk")  # handles multi-step tool calls
    needs, ctx = agent.validate_task_need(transcript)  # like validate_search_need
    agent.stop()
"""

import asyncio
import json
import os
import sys
import threading
from datetime import datetime
from typing import Optional, Tuple

from dotenv import load_dotenv

load_dotenv(override=True)

import google.genai as genai
from google.genai.types import GenerateContentConfig
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


GEMINI_MODEL = "gemini-3-flash-preview"


def _extract_text(response) -> str:
    """
    Safely extract text from a Gemini response, filtering out
    thought_signature and other non-text parts that Gemini 3 includes.
    Returns empty string if no text parts are found.
    """
    try:
        parts = response.candidates[0].content.parts
        if not parts:
            return ""
        text_parts = []
        for part in parts:
            if hasattr(part, "text") and part.text is not None:
                text_parts.append(part.text)
        return "".join(text_parts).strip()
    except (IndexError, AttributeError, TypeError):
        try:
            return (response.text or "").strip()
        except Exception:
            return ""


# Keywords for fast pre-filtering (avoids an LLM call for clearly unrelated queries)
TASK_KEYWORDS = [
    "task", "todo", "to-do", "to do", "ticktick", "tick tick",
    "remind", "reminder", "deadline", "due date", "due tomorrow",
    "complete", "finish", "check off", "mark done", "mark complete",
    "add to my list", "add to list", "create task", "new task",
    "delete task", "remove task", "my tasks", "my projects",
    "what do i have to do", "what's on my list", "what do i need to do",
    "project list", "inbox",
]


def _get_system_prompt() -> str:
    """Build a fresh system prompt with the current date/time."""
    now = datetime.now()
    return f"""\
You are a task management sub-agent with access to TickTick tools.
You receive instructions from a main agent or user about task management.
Execute the request using the available tools and return a clear, concise summary.

Current date and time: {now.strftime("%A, %B %d, %Y at %I:%M %p")}
Timezone: {now.astimezone().tzname()}

IMPORTANT RULES:
- When calling a tool, respond ONLY with a JSON object (no markdown, no extra text):
  {{"tool": "<tool_name>", "arguments": {{<arguments>}}}}
- If you need to show results or talk, respond with plain text (no JSON).
- After receiving tool results, summarize them clearly and concisely.
- For operations that need a project_id and you don't have one, first call get_projects
  to find it, then proceed.
- When creating tasks with due dates, use ISO 8601 format (e.g. "2026-02-20T09:00:00+0000").
  Use the current date/time above to resolve relative dates like "today", "tomorrow", "next Monday", etc.
- Keep responses brief — you're reporting back to another agent.
"""


def _build_tools_description(tools: list) -> str:
    """Format MCP tools into a text block for the LLM."""
    lines = ["Available tools:\n"]
    for t in tools:
        props = t.inputSchema.get("properties", {})
        required = t.inputSchema.get("required", [])
        params = []
        for pname, pinfo in props.items():
            req_marker = " (required)" if pname in required else ""
            params.append(
                f"    - {pname}: {pinfo.get('description', pinfo.get('type', ''))}{req_marker}"
            )
        params_str = "\n".join(params) if params else "    (no parameters)"
        lines.append(f"  {t.name}: {t.description}\n{params_str}\n")
    return "\n".join(lines)


class TickTickAgent:
    """
    Self-contained TickTick task management sub-agent.

    Maintains a persistent MCP server connection in a background thread.
    The main agent can call ask() from any thread to delegate task operations.

    Lifecycle:
        agent.start()   -> boots MCP subprocess, connects, discovers tools
        agent.ask(...)   -> thread-safe, blocking; returns text result
        agent.stop()     -> tears down connection and background thread
    """

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._session: Optional[ClientSession] = None
        self._tools_desc: str = ""
        self._ready = threading.Event()
        self._stop_event: Optional[asyncio.Event] = None
        self._gemini_client = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, timeout: float = 15.0) -> bool:
        """
        Start the MCP server subprocess and connect.
        Blocks until the connection is ready or *timeout* seconds elapse.
        Returns True if successfully connected.
        """
        api_key = os.getenv("API_KEY")
        if not api_key:
            print("[TickTickAgent] Error: API_KEY env var not set.")
            return False

        self._gemini_client = genai.Client(api_key=api_key)
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="ticktick-agent"
        )
        self._thread.start()

        ready = self._ready.wait(timeout=timeout)
        if ready and self._session is not None:
            self._running = True
            print("[TickTickAgent] Ready — MCP server connected.")
        else:
            print("[TickTickAgent] Failed to connect to MCP server.")
        return self._running

    def stop(self):
        """Shut down the MCP server connection and background thread."""
        if self._stop_event and self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._stop_event.set)
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[TickTickAgent] Stopped.")

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(self, instruction: str, timeout: float = 30.0) -> str:
        """
        Send a natural-language task request to the sub-agent.

        Thread-safe and blocking.  Handles multi-step tool calling internally
        and returns a concise text summary of what was done.
        """
        if not self._running or not self._loop or not self._session:
            return "[TickTickAgent] Not connected. Call start() first."

        future = asyncio.run_coroutine_threadsafe(
            self._process_request(instruction), self._loop
        )
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            return "[TickTickAgent] Request timed out."
        except Exception as e:
            return f"[TickTickAgent] Error: {e}"

    def validate_task_need(
        self, query: str, conversation_context=None
    ) -> Tuple[bool, str]:
        """
        Check if a user query needs task management, and if so, handle it.

        Returns ``(True, result_text)`` if the request was task-related and
        was handled, or ``(False, "")`` otherwise.

        Follows the same pattern as ``search.validate_search_need()``.
        """
        if not self._running:
            return (False, "")

        # 1. Fast keyword pre-filter (no API call)
        query_lower = query.lower()
        if not any(kw in query_lower for kw in TASK_KEYWORDS):
            return (False, "")

        # 2. Confirm with a quick LLM call
        context_str = ""
        if conversation_context:
            if isinstance(conversation_context, list):
                context_str = (
                    f"Recent conversation: {json.dumps(conversation_context[-2:])}\n\n"
                )
            elif isinstance(conversation_context, str):
                context_str = f"Context: {conversation_context}\n\n"

        validation_prompt = (
            f"{context_str}"
            f'User said: "{query}"\n\n'
            f"Is this a task management request (creating, viewing, completing, "
            f"deleting, or modifying tasks/to-dos)? Answer ONLY 'Yes' or 'No'."
        )

        try:
            response = self._gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=validation_prompt,
                config=GenerateContentConfig(temperature=0, max_output_tokens=10),
            )

            reply_text = _extract_text(response)
            if reply_text and "Yes" in reply_text:
                instruction = query
                if context_str:
                    instruction = f"{context_str}User request: {query}"

                result = self.ask(instruction)
                print(f"[TickTickAgent] Handled: {result[:120]}...")
                return (True, result)
        except Exception as e:
            print(f"[TickTickAgent] Validation error: {e}")

        return (False, "")

    # ------------------------------------------------------------------
    # Internal — background event loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        """Entry point for the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_and_serve())
        except Exception as e:
            print(f"[TickTickAgent] Event loop error: {e}")
        finally:
            self._loop.close()

    async def _connect_and_serve(self):
        """Connect to the MCP server and keep the connection alive."""
        self._stop_event = asyncio.Event()

        python_exe = sys.executable
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        server_params = StdioServerParameters(
            command=python_exe,
            args=["-m", "ticktick.ticktick_mcp_server"],
            cwd=project_root,
        )

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session

                    tools_result = await session.list_tools()
                    self._tools_desc = _build_tools_description(tools_result.tools)

                    self._ready.set()

                    # Block here until stop() is called
                    await self._stop_event.wait()
        except Exception as e:
            print(f"[TickTickAgent] Connection error: {e}")
            self._ready.set()  # Unblock start() even on failure

    async def _process_request(self, instruction: str) -> str:
        """Run the Gemini tool-calling loop for a single request."""
        system_prompt = _get_system_prompt()

        conversation = [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{self._tools_desc}"}]},
            {"role": "model", "parts": [{"text": "Ready. What task operation do you need?"}]},
            {"role": "user", "parts": [{"text": instruction}]},
        ]

        max_tool_rounds = 5
        for _ in range(max_tool_rounds):
            response = self._gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=conversation,
                config=GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=2048,
                ),
            )

            reply = _extract_text(response)

            # Check if the reply is a tool call (JSON with "tool" key)
            tool_call = None
            try:
                cleaned = reply
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict) and "tool" in parsed:
                    tool_call = parsed
            except (json.JSONDecodeError, ValueError):
                pass

            if tool_call:
                tool_name = tool_call["tool"]
                tool_args = tool_call.get("arguments", {})
                print(f"  [TickTickAgent] Calling {tool_name}({json.dumps(tool_args)})")

                conversation.append({"role": "model", "parts": [{"text": reply}]})

                try:
                    result = await self._session.call_tool(tool_name, tool_args)
                    tool_output = "\n".join(
                        c.text for c in result.content if hasattr(c, "text")
                    )
                except Exception as e:
                    tool_output = f"Tool error: {e}"

                conversation.append({
                    "role": "user",
                    "parts": [{"text": f"Tool result from {tool_name}:\n{tool_output}"}],
                })
                continue
            else:
                # Final text response
                return reply

        return "(TickTick agent reached max tool rounds without a final answer)"
