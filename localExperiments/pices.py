import speech_recognition as sr
import pyttsx3
import base64
import json
import time
import threading
import cv2
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# === GGUF Model Imports ===
from llama_cpp import Llama

# === IMPORT SERVO CONTROLLER ===
from agents.ServoController import ServoController

# ==============================================================================
# === 1. LOAD MODELS (GGUF Format for Mac Performance)
# ==============================================================================

# --- Path to your CONVERTED LoRA adapter ---
# IMPORTANT: This must be the path to the LoRA adapter AFTER converting it to GGUF format.
ADAPTER_GGUF_PATH = "./bot.gguf"

print("Loading GGUF models for Mac (Metal)...")

# === Main Language Model (Mistral-7B-Instruct GGUF) ===
# This model will handle commands and generate robot actions.
# NOTE: Update the repo_id and filename to match the GGUF file you download.
main_model = Llama.from_pretrained(
    repo_id="MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF",
    filename="Mistral-7B-Instruct-v0.3.Q4_K_M.gguf",
    lora_path=ADAPTER_GGUF_PATH,  # Apply the LoRA adapter at load time
    n_gpu_layers=-1,  # Offload all possible layers to GPU
    n_ctx=4096,  # Context window size
    verbose=False
)

# AFTER: Loads from a local file
# main_model = Llama(
#     model_path="/Users/PV/PycharmProjects/meLlamo/bot.gguf", # <-- IMPORTANT: Update this path
#     lora_path=ADAPTER_GGUF_PATH,
#     n_gpu_layers=-1,
#     n_ctx=4096,
#     verbose=False
# )

# === VLM for Scene Description (SmolVLM) ===
# This model remains the same.
vision_model = Llama.from_pretrained(
    repo_id="ggml-org/SmolVLM-500M-Instruct-GGUF",
    filename="SmolVLM-500M-Instruct-Q8_0.gguf",
    n_gpu_layers=-1,
    verbose=False
)

print("? All models loaded successfully using llama-cpp-python!")

# ==============================================================================
# === 2. VOICE AND ROBOT SETUP (Unchanged)
# ==============================================================================

# === Voice Setup ===
engine = pyttsx3.init()
voices = engine.getProperty('voices')
rate = engine.getProperty('rate')
volume = engine.getProperty('volume')

# === System Prompt ===
try:
    with open('localExperiments/pices_system_prompt.txt', 'r') as f:
        INSTRUCTION_PROMPT = f.read()
except FileNotFoundError:
    print("Error: scorpio_system_prompt.txt not found.")
    INSTRUCTION_PROMPT = "You are an expert robotic control system. Given the user's command, the current robot state, and a description of the scene, generate a JSON response with the robot's actions and speech."

# === Robot Controller & State ===
servo_controller = ServoController()
listening = True
wake_word = "herbie"
exit_words = ["exit", "stop", "quit", "bye", "goodbye"]
pending_followup = None
followup_timer = None
sending_to_model = False

# === Camera Setup ===
cam = cv2.VideoCapture(0)


# ==============================================================================
# === 3. HELPER FUNCTIONS (Unchanged)
# ==============================================================================

def get_frame_data():
    ret, frame = cam.read()
    if not ret:
        print("Failed to capture frame.")
        return None
    _, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes()


def get_scene_description_from_smolvlm(image_bytes: bytes) -> str:
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    prompt = f"USER: <image>\nDescribe this scene\nASSISTANT:"
    try:
        print("Sending image to SmolVLM for scene description...")
        output = vision_model(prompt, max_tokens=150, stop=["USER:", "\n"], temperature=0.7)
        description = output['choices'][0]['text'].strip()
        print("SmolVLM Scene Description:", description)
        return description
    except Exception as e:
        print("SmolVLM error:", e)
        return "Unable to describe the scene."


def execute_motion_sequence(actions: List[Dict[str, Any]]) -> bool:
    print(f"Executing {len(actions)} translated actions...")
    for i, action in enumerate(actions):
        cmd_type = action.get('type', 'unknown')
        print(f"Action {i + 1}: Type={cmd_type}, Details={action}")
        if cmd_type == 'motor':
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
            elif command == 'wait' and args:
                time.sleep(args[0])
            else:
                print(f"Unknown motor command: {command}")
        elif cmd_type == 'wait':
            time.sleep(action.get('duration', 1.0))
    return True


def parse_ai_response(response_text: str) -> Optional[Dict[str, Any]]:
    try:
        json_start = response_text.find('{')
        if json_start == -1: return None
        brace_count = 0
        json_end = -1
        for i, char in enumerate(response_text[json_start:]):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            if brace_count == 0:
                json_end = json_start + i + 1
                break
        if json_end == -1: return None
        json_str = response_text[json_start:json_end]
        return json.loads(json_str)
    except Exception as e:
        print(f"JSON parsing error: {e}")
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

    if followup_timer: followup_timer.cancel()
    pending_followup = followup_prompt
    followup_timer = threading.Timer(delay, execute_followup)
    followup_timer.start()


# ==============================================================================
# === 4. ACTION TRANSLATOR (Unchanged)
# ==============================================================================
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
        cmd_id = action[0]
        if cmd_id in command_map:
            translated_list.append({
                'type': 'motor',
                'command': command_map[cmd_id],
                'args': action[1:]
            })
        elif cmd_id == 7:  # Wait command
            translated_list.append({
                'type': 'wait',
                'duration': action[1] if len(action) > 1 else 1.0
            })
    return translated_list


# ==============================================================================
# === 5. MODIFIED MAIN REQUEST FUNCTION
# ==============================================================================
def get_response(user_input: str) -> str:
    # 1. Get Scene and State
    image_bytes = get_frame_data()
    scene_description = "Camera failed."
    if image_bytes:
        scene_description = get_scene_description_from_smolvlm(image_bytes)

    robot_state_dict = servo_controller.get_current_state()
    robot_state_str = json.dumps(robot_state_dict)

    # 2. Compose the prompt in the fine-tuned format
    # This uses the standard Alpaca instruction format, which Mistral Instruct models handle well.
    final_prompt = f"""### Instruction:
                {INSTRUCTION_PROMPT}
                
                ### Input:
                User Command: {user_input}
                Current robot state: {robot_state_str}
                Scene description: {scene_description}
                
                ### Response:
                """

    # 3. Send to the fine-tuned model (Simplified GGUF call)
    print("\n--- Sending to Fine-tuned GGUF Model ---")

    try:
        output = main_model(
            prompt=final_prompt,
            max_tokens=256,
            stop=["###"],  # Stop generation at the next section
            temperature=0.7,
            echo=False  # Do not repeat the prompt in the output
        )
    except e:
        print(e)

    model_reply = output['choices'][0]['text'].strip()
    print("Model Reply:", model_reply)

    # 4. Parse and execute (Unchanged)
    structured_response = parse_ai_response(model_reply)
    if structured_response:
        print("Parsed response successfully.")
        actions_to_execute = translate_actions(structured_response.get('act', []))
        if actions_to_execute:
            threading.Thread(target=execute_motion_sequence, args=(actions_to_execute,)).start()

        if structured_response.get('fu') and structured_response.get('fp'):
            schedule_followup(structured_response.get('fp'), 3.0)

        return structured_response.get('vr', "I processed the command but have nothing to say.")
    else:
        return model_reply


# ==============================================================================
# === 6. MAIN LOOP (Unchanged)
# ==============================================================================

print("\nRobot control system initialized.")
print("Type 'herbie' to start, then give your commands. Type 'exit' to stop.")

while listening:
    try:
        user_input = input("\n>>> ").strip()

        if any(word in user_input.lower() for word in exit_words):
            if followup_timer: followup_timer.cancel()
            print("Exiting robot assistant.")
            break

        if wake_word in user_input.lower():
            sending_to_model = True
            print("Wake word detected. I'm ready for your command.")
            engine.say("Ready")
            engine.runAndWait()
            continue

        if sending_to_model:
            if followup_timer:
                followup_timer.cancel()
                pending_followup = None

            reply = get_response(user_input)
            print("Robot:", reply)
            engine.setProperty('rate', 200)
            engine.setProperty('volume', volume)
            engine.say(reply)
            engine.runAndWait()

    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
        break
    except Exception as e:
        print(f"An unexpected error occurred in the main loop: {e}")

# Cleanup
cam.release()
cv2.destroyAllWindows()
servo_controller.close()