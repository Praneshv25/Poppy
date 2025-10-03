import speech_recognition as sr
import pyttsx3
import google.genai as genai
from google.genai.types import GenerateContentConfig, SafetySetting, HarmCategory, HarmBlockThreshold
import cv2
import base64
import json
import os
import time
import threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# === IMPORT SERVO CONTROLLER ===
from ServoController import ServoController

# === ENHANCED VOICE SETUP ===
engine = pyttsx3.init()
voices = engine.getProperty('voices')
rate = engine.getProperty('rate')
volume = engine.getProperty('volume')

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
    # We now read the modified system prompt from the file
    with open('libra_speed_demon_sys_prompt.txt', 'r') as f:
        system_prompt = f.read()
except FileNotFoundError:
    print("Error: libra_system_prompt.txt not found. Please create the file with the system prompt content.")
    system_prompt = ""

print("System prompt loaded successfully." if system_prompt else "Error: System prompt not found.")

# === ROBOT CONTROLLER INITIALIZATION ===
servo_controller = ServoController()

# === INITIAL STATE ===
conversation_history = []
sending_to_gemini = False
exit_words = ["exit", "stop", "quit", "bye", "goodbye"]
pending_followup = None
followup_timer = None

# === CAMERA SETUP ===
cam = cv2.VideoCapture(0)


def get_frame_data():
    ret, frame = cam.read()
    if not ret:
        print("Failed to capture frame.")
        return None
    resized = cv2.resize(frame, (224, 224))
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]
    _, buffer = cv2.imencode('.jpg', resized, encode_param)
    return base64.b64encode(buffer).decode('utf-8')


# === ACTION TRANSLATION ===
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
        if cmd_id in command_map:
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


# === MOTION EXECUTION SYSTEM ===
def execute_motion_sequence(actions: List[Dict[str, Any]]) -> bool:
    print(f"Executing {len(actions)} actions...")
    for i, action in enumerate(actions):
        print(f"Action {i + 1}: {action.get('type', 'unknown')}")

        if action.get('type') == 'motor':
            command = action.get('command')
            args = action.get('args', [])
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

        elif action.get('type') == 'vision_check':
            print(f"Vision check: {action.get('target', 'general')}")

        time.sleep(0.1)
    return True


# === JSON PARSING (ADAPTED FOR NEW KEYS & ROBUSTNESS) ===
def parse_ai_response(response_text: str) -> Optional[Dict[str, Any]]:
    try:
        # Find the first opening brace '{'
        start_idx = response_text.find('{')
        if start_idx == -1:
            print("No JSON object found in the response.")
            return None

        # Find the matching closing brace '}' by counting
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(response_text)):
            if response_text[i] == '{':
                brace_count += 1
            elif response_text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break

        if end_idx == -1:
            print("Mismatched braces or incomplete JSON object.")
            return None

        # Extract the JSON string from the found start and end points
        json_str = response_text[start_idx:end_idx]

        # Now, attempt to parse the extracted string
        return json.loads(json_str)

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"Response parsing error: {e}")
        return None


def schedule_followup(followup_prompt: str, delay: float = 3.0):
    global pending_followup, followup_timer

    def execute_followup():
        global pending_followup
        if pending_followup:
            print(f"Follow-up: {pending_followup}")
            engine.say(pending_followup)
            engine.runAndWait()
            pending_followup = None

    if followup_timer:
        followup_timer.cancel()

    pending_followup = followup_prompt
    followup_timer = threading.Timer(delay, execute_followup)
    followup_timer.start()


# === ENHANCED GEMINI REQUEST FUNCTION ===
def get_response(user_input: str) -> str:
    global conversation_history

    frame_data = get_frame_data()
    if not frame_data:
        return "Camera input failed."

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

    structured_response = parse_ai_response(gemini_reply)

    if structured_response:
        print("Parsed structured response successfully")

        actions = translate_actions(structured_response.get('act', []))
        if actions:
            threading.Thread(target=execute_motion_sequence, args=(actions,)).start()

        if structured_response.get('fu') and structured_response.get('fp'):
            schedule_followup(structured_response.get('fp'), 3.0)

        voice_response = structured_response.get('vr', gemini_reply)
        conversation_history.append({"role": "model", "parts": [{"text": voice_response}]})
        return voice_response
    else:
        conversation_history.append({"role": "model", "parts": [{"text": gemini_reply}]})
        return gemini_reply


# === MAIN LOOP (MODIFIED FOR TYPED INPUT) ===
print("Robot control system initialized. Type 'exit' to quit.")
print("Current robot state:", servo_controller.get_current_state())

while True:
    try:
        user_input = input("You: ")
        if any(word in user_input.lower() for word in exit_words):
            print("Goodbye!")
            break

        if followup_timer:
            followup_timer.cancel()
            pending_followup = None

        reply = get_response(user_input)
        engine.setProperty('rate', 200)
        engine.setProperty('volume', volume)
        engine.setProperty('voice', voices[0].id)
        engine.say(reply)
        engine.runAndWait()

    except Exception as e:
        print(f"Unexpected error: {e}")

# Cleanup
cam.release()
cv2.destroyAllWindows()
servo_controller.close()