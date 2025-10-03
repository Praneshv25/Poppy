import speech_recognition as sr
import pyttsx3
import google.genai as genai
from google.genai.types import GenerateContentConfig, SafetySetting, HarmCategory, HarmBlockThreshold
import cv2
import base64
import json
import time
import threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import ollama
import openai
import base64
from llama_cpp import Llama

# === IMPORT SERVO CONTROLLER ===
from ServoController import ServoController

openai.api_base = "http://localhost:8080/v1"
openai.api_key = "not-needed"

# === ENHANCED VOICE SETUP ===
engine = pyttsx3.init()
voices = engine.getProperty('voices')
rate = engine.getProperty('rate')
volume = engine.getProperty('volume')
llm = Llama.from_pretrained(
	repo_id="ggml-org/SmolVLM-500M-Instruct-GGUF",
	filename="SmolVLM-500M-Instruct-Q8_0.gguf",
)

# === GEMINI CLIENT SETUP ===
client = genai.Client(api_key="AIzaSyDosNbIypDa8kk3LLIWrVNGPwYkzj9V0UE")  # <-- Replace with your Gemini API key

generation_config = GenerateContentConfig(
    temperature=0.8,
    top_p=0.9,
    top_k=40,
    max_output_tokens=8192,
)

# === SYSTEM PROMPT ===
try:
    with open('scorpio_system_prompt.txt', 'r') as f:
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
wake_word = "herbie"
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


def get_scene_description_from_smolvlm(image_bytes: bytes) -> str:
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    prompt = (
        "Describe the image in detail for a robot assistant.\n"
        f"<image>{encoded_image}</image>"
    )
    try:
        print("Sending image to llama-cpp (direct)...")
        output = llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )

        return output['choices'][0]['message']['content']
    except Exception as e:
        print("llama-cpp error:", e)
        return "Unable to describe the scene."

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


# === ENHANCED GEMINI REQUEST FUNCTION ===
def get_response(user_input: str) -> str:
    global conversation_history

    # === 1. Capture camera image ===
    frame_data = get_frame_data()
    if not frame_data:
        return "Camera input failed."
    image_bytes = base64.b64decode(frame_data)
    scene_description = get_scene_description_from_smolvlm(image_bytes)

    # === 2. LLaVA: Visual scene description ===
    # try:
    #     print("Sending image to LLaVA...")
    #     llava_response = ollama.chat(model='llava:7b', messages=[
    #         {
    #             "role": "user",
    #             "content": "Describe the current scene in detail for a robot assistant.",
    #             "images": [frame_data]
    #         }
    #     ])
    #     scene_description = llava_response["message"]["content"]
    #     print("LLaVA scene description:", scene_description)
    # except Exception as e:
    #     print("Error using LLaVA:", e)
    #     scene_description = "Unable to describe the current scene."

    # === 3. Get robot state ===
    robot_state = servo_controller.get_current_state()
    state_info = f"Current robot state: elevation_servo_pos={robot_state['elevation_servo_pos']}, translation_servo_pos={robot_state['translation_servo_pos']}, rotation_stepper_deg={robot_state['rotation_stepper_deg']}"

    # === 4. Compose user message with state and scene ===
    user_message = f"""User command: {user_input}

    {state_info}
    
    Scene description from camera:
    {scene_description}
    
    Respond only in this JSON format:
    {{
      "voice_response": "string",
      "actions": [{{"type": "motor"|"wait"|"vision_check", "command": "string", "args": [...], "duration": float}}],
      "requires_followup": true|false,
      "followup_prompt": "string"
    }}"""

    # === 5. Append user message to conversation history ===
    if not conversation_history:
        conversation_history.append({"role": "system", "content": system_prompt})
    conversation_history.append({"role": "user", "content": user_message})

    # === 6. Send to Mistral via Ollama ===
    try:
        print("sending to mistral")
        response = ollama.chat(model='mistral:latest', messages=conversation_history)
        model_reply = response["message"]["content"]
        print("Mistral reply:", model_reply)
    except Exception as e:
        print("Error using Mistral:", e)
        return "Failed to get a response from the language model."

    # === 7. Add assistant reply to history ===
    conversation_history.append({"role": "assistant", "content": model_reply})

    # === 8. Parse structured JSON ===
    structured_response = parse_ai_response(model_reply)

    if structured_response:
        print("Parsed structured response successfully")

        actions = structured_response.get('actions', [])
        if actions:
            threading.Thread(target=execute_motion_sequence, args=(actions,)).start()

        if structured_response.get('requires_followup') and structured_response.get('followup_prompt'):
            schedule_followup(structured_response.get('followup_prompt'), 3.0)

        voice_response = structured_response.get('voice_response', model_reply)
        return voice_response
    else:
        return model_reply


# === MAIN LOOP ===
# recognizer = sr.Recognizer()
#
# print("Robot control system initialized. Say 'gemini' to start interaction.")
# print("Current robot state:", servo_controller.get_current_state())
#
# while listening:
#     with sr.Microphone() as source:
#         print("Listening...")
#         recognizer.adjust_for_ambient_noise(source)
#         try:
#             audio = recognizer.listen(source, timeout=7.0)
#             response = recognizer.recognize_google(audio)
#             print("Heard:", response)
#
#             if any(word in response.lower() for word in exit_words):
#                 sending_to_gemini = False
#                 if followup_timer:
#                     followup_timer.cancel()
#                 print("Stopped sending responses to Gemini.")
#                 continue
#
#             if wake_word in response.lower() and not sending_to_gemini:
#                 sending_to_gemini = True
#                 print("Wake word detected. Resumed Gemini interaction.")
#                 continue
#
#             if sending_to_gemini:
#                 # Cancel any pending followup when user speaks
#                 if followup_timer:
#                     followup_timer.cancel()
#                     pending_followup = None
#
#                 reply = get_response(response)
#                 engine.setProperty('rate', 200)
#                 engine.setProperty('volume', volume)
#                 engine.setProperty('voice', voices[0].id)
#                 engine.say(reply)
#                 engine.runAndWait()
#
#         except sr.UnknownValueError:
#             print("Didn't recognize anything.")
#         except sr.RequestError as e:
#             print(f"Speech Recognition error: {e}")
#         except Exception as e:
#             print(f"Unexpected error: {e}")


print("Robot control system initialized.")
print("Type your commands below. Type 'exit' to stop.")
print("Current robot state:", servo_controller.get_current_state())

while listening:
    try:
        user_input = input("\n>>> ").strip()

        if any(word in user_input.lower() for word in exit_words):
            sending_to_gemini = False
            if followup_timer:
                followup_timer.cancel()
            print("Exiting robot assistant.")
            break

        if wake_word in user_input.lower() and not sending_to_gemini:
            sending_to_gemini = True
            print("Wake word detected. Interaction started.")
            continue

        if sending_to_gemini:
            # Cancel any pending followup when user speaks
            if followup_timer:
                followup_timer.cancel()
                pending_followup = None

            reply = get_response(user_input)
            print("Robot:", reply)
            engine.setProperty('rate', 200)
            engine.setProperty('volume', volume)
            engine.setProperty('voice', voices[0].id)
            engine.say(reply)
            engine.runAndWait()

    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
        break
    except Exception as e:
        print(f"Unexpected error: {e}")

# Cleanup
cam.release()
cv2.destroyAllWindows()
servo_controller.close()