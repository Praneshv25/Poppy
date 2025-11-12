import sys
import os
# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import google.genai as genai
from google.genai.types import GenerateContentConfig
import json
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import search.search as search
from pydantic import BaseModel

# Define the structured response model
class RobotResponse(BaseModel):
    vr: str  # voice response
    act: List[List[Any]]  # actions list, e.g., [[4,12],[0,20],[7,1.0]]
    fu: bool  # follow-up needed
    fp: str  # follow-up prompt

# Load environment variables from .env file
load_dotenv()

# === GEMINI CLIENT SETUP ===
client = genai.Client(api_key=os.getenv("API_KEY"))

generation_config = GenerateContentConfig(
    temperature=0.8,
    top_p=0.9,
    top_k=40,
    max_output_tokens=8192,
)

# === SYSTEM PROMPT ===
try:
    # Use absolute path relative to project root
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'speedDemon_system_prompt.txt')
    with open(config_path, 'r') as f:
        system_prompt = f.read()
except FileNotFoundError:
    print("Error: speedDemon_system_prompt.txt not found. Please create the file with the system prompt content.")
    system_prompt = ""

print("System prompt loaded successfully" if system_prompt else "Using fallback system prompt")

# === INITIAL STATE ===
conversation_history = []
exit_words = ["exit", "stop", "quit", "bye", "goodbye"]


def get_response(user_input: str, search_context: Optional[str] = None) -> str:
    """Get response from Gemini without camera input"""
    global conversation_history

    # Create text parts for the prompt
    text_parts = [{"text": f"User command: {user_input}"}]
    
    # Add search context if provided
    if search_context:
        text_parts.append({"text": f"Search context: {search_context}"})
    
    text_parts.append({"text": "Note: This is a CLI test - no visual input available."})

    conversation_history.append({"role": "user", "parts": text_parts})

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=conversation_history,
        config=GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.8,
            top_p=0.9,
            top_k=40,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=RobotResponse,
        )
    )

    # Use structured output directly - no parsing needed!
    robot_response: RobotResponse = response.parsed
    
    print("Gemini:", robot_response.vr)
    print("Actions:", robot_response.act)

    if robot_response.act and isinstance(robot_response.act, list):
        print(f"Actions parsed: {robot_response.act}")
        # In CLI mode, we just display the actions without executing them
        print("(Robot actions would be executed here in real mode)")

    conversation_history.append({"role": "model", "parts": [{"text": robot_response.vr}]})
    return robot_response.vr


# === MAIN LOOP ===
print("=" * 60)
print("SpeedDemon CLI Test Mode")
print("=" * 60)
print("Type your commands below. Type 'exit' to quit.")
print()

while True:
    try:
        # Get user input
        user_input = input("You: ").strip()
        
        if not user_input:
            continue
        
        # Check for exit commands
        if any(word in user_input.lower() for word in exit_words):
            print("Goodbye!")
            break
        
        # Check if search is needed
        # Get recent conversation context (pass list, not JSON string)
        recent_context = None
        if len(conversation_history) > 0:
            # Pass last 4 items (2 question-answer pairs) as a list
            recent_context = conversation_history[-4:] if len(conversation_history) >= 4 else conversation_history

        need_search, search_result = search.validate_search_need(user_input, conversation_context=recent_context)
        
        if need_search:
            print(f"[Search needed. Context retrieved: {len(search_result)} chars]")
            reply = get_response(user_input, search_context=search_result)
        else:
            print("[No search needed]")
            reply = get_response(user_input)
        
        print(f"\nRobot: {reply}\n")
        print("-" * 60)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
        break
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()

