import voice
import google.genai as genai
from google.genai.types import GenerateContentConfig
import cv2
import base64
import json
import time
import os
import threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# === IMPORT SERVO CONTROLLER ===
from ServoController import ServoController

# === IMPORT WAKE WORD & TRANSCRIPTION ===
from wakeWord.wake import listen_for_wake_word


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
    with open('speedDemon_system_prompt.txt', 'r') as f:
        system_prompt = f.read()
except FileNotFoundError:
    print("Error: speedDemon_system_prompt.txt not found. Please create the file with the system prompt content.")
    system_prompt = ""

print("System prompt loaded successfully" if system_prompt else "Using fallback system prompt")

# === ROBOT CONTROLLER INITIALIZATION ===
servo_controller = ServoController()

# === INITIAL STATE ===
conversation_history = []
listening = True
exit_words = ["exit", "stop", "quit", "bye", "goodbye"]

# === CAMERA SETUP ===
cam = cv2.VideoCapture(0)


def get_frame_data():
    ret, frame = cam.read()
    if not ret:
        print("Failed to capture frame.")
        return None
    resized = cv2.resize(frame, (224, 224))
    _, buffer = cv2.imencode('.jpg', resized)
    return base64.b64encode(buffer).decode('utf-8')


# === MOTION EXECUTION SYSTEM ===
def execute_motion_sequence(actions: List[Dict[str, Any]]) -> bool:
    """Execute a sequence of robot actions"""
    print(f"Executing {len(actions)} actions...")

    for i, action in enumerate(actions):
        print(f"Action {i + 1}: {action.get('type', 'unknown')}")

        if action.get('type') == 'motor':
            command = action.get('command')
            args = action.get('args', [])

            # Map commands to servo controller methods
            if command == 'move_up' and args:
                servo_controller.move_up(args[0])
            elif command == 'move_down' and args:
                servo_controller.move_down(args[0])
            elif command == 'move_forward' and args:
                servo_controller.move_forward(args[0])
            elif command == 'move_backward' and args:
                servo_controller.move_backward(args[0])
            elif command == 'move_left' and args:
                servo_controller.move_left(args[0])
            elif command == 'move_right' and args:
                servo_controller.move_right(args[0])
            elif command == 'move_servo' and len(args) >= 2:
                servo_controller.move_servo(args[0], args[1])
            elif command == 'hold_position' and args:
                servo_controller.hold_position(args[0])
            else:
                print(f"Unknown motor command: {command}")

        elif action.get('type') == 'wait':
            duration = action.get('duration', 1.0)
            time.sleep(duration)

        # elif action.get('type') == 'vision_check':
        #     # Placeholder for vision processing
        #     print(f"Vision check: {action.get('target', 'general')}")

        # Brief pause between actions for safety
        time.sleep(0.1)

    return True


def translate_actions(act_list: List[list]) -> List[Dict[str, Any]]:
    if not act_list:
        return []

    command_map = {
        0: 'move_forward',
        1: 'move_backward',
        2: 'move_up',
        3: 'move_down',
        4: 'move_left',
        5: 'move_right',
        6: 'move_servo',
        7: 'wait',
    }

    translated_list = []
    for action in act_list:
        if not isinstance(action, list) or len(action) < 1:
            print(f"Invalid action format: {action}")
            continue

        cmd_id = action[0]
        if cmd_id in command_map and cmd_id != 7:
            translated_list.append({
                'type': 'motor',
                'command': command_map[cmd_id],
                'args': action[1:]
            })
        elif cmd_id == 7:
            translated_list.append({
                'type': 'wait',
                'duration': action[1] if len(action) > 1 and isinstance(action[1], (int, float)) else 1.0
            })
        else:
            print(f"Unknown command ID: {cmd_id}")
    return translated_list

def parse_ai_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse AI response and extract structured data"""
    try:
        # Look for JSON structure in the response
        start_idx = response_text.find('{')
        if start_idx == -1:
            return None

        # Find the matching closing brace
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(response_text)):
            if response_text[i] == '{':
                brace_count += 1
            elif response_text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break

        if end_idx == -1:
            return None

        json_str = response_text[start_idx:end_idx + 1]
        return json.loads(json_str)

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"Response parsing error: {e}")
        return None



# === ENHANCED GEMINI REQUEST FUNCTION ===
def get_response(user_input: str) -> str:
    global conversation_history

    frame_data = get_frame_data()
    if not frame_data:
        return "Camera input failed."

    # Include current robot state in the prompt
    robot_state = servo_controller.get_current_state()
    state_info = f"Current robot state: elevation_servo_pos={robot_state['elevation_servo_pos']}, translation_servo_pos={robot_state['translation_servo_pos']}, rotation_stepper_deg={robot_state['rotation_stepper_deg']}"

    vision_parts = [
        {"text": f"User command: {user_input}"},
        {"text": state_info},
        {"text": "Here is the current visual scene."},
        {"inline_data": {
            "mime_type": "image/jpeg",
            "data": frame_data
        }}
    ]

    conversation_history.append({"role": "user", "parts": vision_parts})

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=conversation_history,
        config=GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.8,
            top_p=0.9,
            top_k=40,
            max_output_tokens=8192,
        )
    )

    gemini_reply = response.text
    print("Gemini:", gemini_reply)

    # Parse structured response
    structured_response = parse_ai_response(gemini_reply)

    if structured_response:
        print("Parsed structured response successfully")

        vr = structured_response.get('vr') or structured_response.get('voice_response') or gemini_reply
        act = structured_response.get('act')
        if act and isinstance(act, list):
            translated = translate_actions(act)
            if translated:
                threading.Thread(target=execute_motion_sequence, args=(translated,)).start()

        # fu = structured_response.get('fu')
        # fp = structured_response.get('fp')
        # Follow-up handling can be added here if needed using fu/fp

        conversation_history.append({"role": "model", "parts": [{"text": vr}]})
        return vr
    else:
        # Fallback to original response if parsing fails
        conversation_history.append({"role": "model", "parts": [{"text": gemini_reply}]})
        return gemini_reply


# === MAIN LOOP ===
print("Robot control system initialized. Listening for wake word 'Mister Carson'...")
print("Current robot state:", servo_controller.get_current_state())

while listening:
    try:
        # Wait for wake word and get transcription
        print("\nListening for wake word...")
        transcript = listen_for_wake_word()
        
        if transcript:
            print(f"Heard: {transcript}")
            
            # Check for exit commands
            if any(word in transcript.lower() for word in exit_words):
                print("Exit command detected. Shutting down...")
                listening = False
                break
            
            # Process the command with Gemini
            reply = get_response(transcript)
            voice.stream_audio(reply)
        else:
            print("No transcript received.")

    except KeyboardInterrupt:
        print("\nInterrupted by user. Shutting down...")
        listening = False
        break
    except Exception as e:
        print(f"Unexpected error: {e}")

# Cleanup
cam.release()
cv2.destroyAllWindows()
servo_controller.close()