#!/usr/bin/env python3
"""
Test script: An interactive Gemini agent that can use the TickTick MCP server tools.
Spawns the MCP server as a subprocess, connects as a client, and lets Gemini
decide which tools to call based on your natural language requests.

Usage:
    conda activate meLlamo
    cd /Users/PV/PycharmProjects/Poppy
    python -m ticktick.test_agent
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

import google.genai as genai
from google.genai.types import GenerateContentConfig

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# --- Config ---
GEMINI_MODEL = "gemini-3-flash-preview"
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    print("Error: API_KEY env var not set (needed for Gemini).")
    sys.exit(1)

gemini_client = genai.Client(api_key=API_KEY)


def _extract_text(response) -> str:
    """Safely extract text from Gemini 3 response, filtering out thought_signature parts."""
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


def get_system_prompt() -> str:
    now = datetime.now()
    return f"""\
You are a helpful task management assistant with access to TickTick tools.
When the user asks about tasks, projects, or anything related to their to-do list,
use the available tools to fulfill their request.

Current date and time: {now.strftime("%A, %B %d, %Y at %I:%M %p")}
Timezone: {now.astimezone().tzname()}

IMPORTANT RULES:
- When calling a tool, respond ONLY with a JSON object (no markdown, no extra text):
  {{"tool": "<tool_name>", "arguments": {{<arguments>}}}}
- If you need to show results or talk to the user, respond with plain text (no JSON).
- If you don't need a tool, just respond normally.
- After receiving tool results, summarize them clearly for the user.
- For operations that need a project_id and you don't have one, first call get_projects
  to find it, then proceed.
- When creating tasks with due dates, use ISO 8601 format (e.g. "2026-02-20T09:00:00+0000").
  Use the current date/time above to resolve relative dates like "today", "tomorrow", "next Monday", etc.
"""


def build_tools_description(tools: list) -> str:
    """Format MCP tools into a text description for the LLM."""
    lines = ["Available tools:\n"]
    for t in tools:
        props = t.inputSchema.get("properties", {})
        required = t.inputSchema.get("required", [])
        params = []
        for pname, pinfo in props.items():
            req_marker = " (required)" if pname in required else ""
            params.append(f"    - {pname}: {pinfo.get('description', pinfo.get('type', ''))}{req_marker}")
        params_str = "\n".join(params) if params else "    (no parameters)"
        lines.append(f"  {t.name}: {t.description}\n{params_str}\n")
    return "\n".join(lines)


async def run_agent():
    """Main agent loop: connect to MCP server, chat with Gemini, call tools."""

    # Determine the Python executable (use the one running this script)
    python_exe = sys.executable

    server_params = StdioServerParameters(
        command=python_exe,
        args=["-m", "ticktick.ticktick_mcp_server"],
        cwd="/Users/PV/PycharmProjects/Poppy",
    )

    print("Starting TickTick MCP server...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Get available tools
            tools_result = await session.list_tools()
            tools = tools_result.tools
            tools_desc = build_tools_description(tools)
            print(f"Connected! {len(tools)} tools available.\n")

            # Conversation state
            conversation = [
                {"role": "user", "parts": [{"text": f"{get_system_prompt()}\n\n{tools_desc}"}]},
                {"role": "model", "parts": [{"text": "Understood. I'm ready to help manage your TickTick tasks. What would you like to do?"}]},
            ]

            print("=" * 60)
            print("  TickTick Agent (type 'quit' to exit)")
            print("=" * 60)
            print()

            while True:
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nGoodbye!")
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break

                conversation.append({"role": "user", "parts": [{"text": user_input}]})

                # Agent loop: keep going until Gemini gives a text response (no tool call)
                max_tool_rounds = 5
                for _ in range(max_tool_rounds):
                    response = gemini_client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=conversation,
                        config=GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=4096,
                        ),
                    )

                    reply = _extract_text(response)

                    # Check if the reply is a tool call (JSON with "tool" key)
                    tool_call = None
                    try:
                        # Handle case where Gemini wraps in ```json ... ```
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
                        print(f"  [Calling {tool_name}({json.dumps(tool_args)})]")

                        # Record the model's tool-call message
                        conversation.append({"role": "model", "parts": [{"text": reply}]})

                        # Execute the tool via MCP
                        try:
                            result = await session.call_tool(tool_name, tool_args)
                            tool_output = "\n".join(
                                c.text for c in result.content if hasattr(c, "text")
                            )
                        except Exception as e:
                            tool_output = f"Tool error: {e}"

                        print(f"  [Result: {tool_output[:200]}{'...' if len(tool_output) > 200 else ''}]")

                        # Feed tool result back to Gemini
                        conversation.append({
                            "role": "user",
                            "parts": [{"text": f"Tool result from {tool_name}:\n{tool_output}"}]
                        })
                        # Continue loop so Gemini can process the result
                        continue
                    else:
                        # Plain text response — show to user and break
                        conversation.append({"role": "model", "parts": [{"text": reply}]})
                        print(f"Agent: {reply}\n")
                        break
                else:
                    print("Agent: (reached max tool rounds, stopping)\n")


def main():
    asyncio.run(run_agent())


if __name__ == "__main__":
    main()
