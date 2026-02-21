import speech_recognition as sr
import pyttsx3
import google.genai as genai
from google.genai.types import GenerateContentConfig, SafetySetting, HarmCategory, HarmBlockThreshold
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
load_dotenv(override=True)

# === IMPORT SERVO CONTROLLER ===
from agents.ServoController import ServoController

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
    # Use absolute path relative to project root
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'libra_system_prompt.txt')
    with open(config_path, 'r') as f:
        system_prompt = f.read()
except FileNotFoundError:
    print("Error: libra_system_prompt.txt not found. Please create the file with the system prompt content.")
    system_prompt = ""

print("System prompt loaded successfully" if system_prompt else "Using fallback system prompt")

# === ROBOT CONTROLLER INITIALIZATION ===
servo_controller = ServoController()

# === INITIAL STATE ===
conversation_history = []
listening = True
sending_to_gemini = False
wake_word = "wake"
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

        elif action.get('type') == 'vision_check':
            # Placeholder for vision processing
            print(f"Vision check: {action.get('target', 'general')}")

        # Brief pause between actions for safety
        time.sleep(0.1)

    return True


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


def schedule_followup(followup_prompt: str, delay: float = 3.0):
    """Schedule a followup prompt after motion completion"""
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

def speak_async(text):
    def _speak():
        engine.say(text)
        engine.runAndWait()
    threading.Thread(target=_speak).start()

def speak(text, rate=200, volume=1.0, voice_index=0):
    tts = pyttsx3.init()
    voices = tts.getProperty('voices')
    tts.setProperty('rate', rate)
    tts.setProperty('volume', volume)
    if voices:
        tts.setProperty('voice', voices[voice_index].id)
    tts.say(text)
    tts.runAndWait()
    tts.stop()

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
        model="gemini-3-flash-preview",
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

        # Execute motion sequence if present
        actions = structured_response.get('actions', [])
        if actions:
            threading.Thread(target=execute_motion_sequence, args=(actions,)).start()

        # Schedule followup if needed
        if structured_response.get('requires_followup') and structured_response.get('followup_prompt'):
            schedule_followup(structured_response.get('followup_prompt'), 3.0)

        # Return voice response for TTS
        voice_response = structured_response.get('voice_response', gemini_reply)
        conversation_history.append({"role": "model", "parts": [{"text": voice_response}]})
        return voice_response
    else:
        # Fallback to original response if parsing fails
        conversation_history.append({"role": "model", "parts": [{"text": gemini_reply}]})
        return gemini_reply


# === MAIN LOOP ===
recognizer = sr.Recognizer()

print("Robot control system initialized. Say 'hey' to start interaction.")
print("Current robot state:", servo_controller.get_current_state())

while listening:
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=7.0)
            response = recognizer.recognize_google(audio)
            print("Heard:", response)

            if any(word in response.lower() for word in exit_words):
                sending_to_gemini = False
                if followup_timer:
                    followup_timer.cancel()
                print("Stopped sending responses to Gemini.")
                continue

            if wake_word in response.lower() and not sending_to_gemini:
                sending_to_gemini = True
                print("Wake word detected. Resumed Gemini interaction.")
                continue

            if sending_to_gemini:
                # Cancel any pending followup when user speaks
                if followup_timer:
                    followup_timer.cancel()
                    pending_followup = None

                reply = get_response(response)
                # engine.setProperty('rate', 200)
                # engine.setProperty('volume', volume)
                # engine.setProperty('voice', voices[0].id)
                # engine.say(reply)
                # engine.runAndWait()
                speak(reply, rate=200, volume=volume, voice_index=0)


        except sr.UnknownValueError:
            print("Didn't recognize anything.")
        except sr.RequestError as e:
            print(f"Speech Recognition error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

# Cleanup
cam.release()
cv2.destroyAllWindows()
servo_controller.close()