import speech_recognition as sr
import pyttsx3
import base64
import json
import time
import threading
import cv2
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# === NEW: Transformers & PEFT Imports ===
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

# === VLM for Scene Description ===
from llama_cpp import Llama

# === IMPORT SERVO CONTROLLER ===
from ServoController import ServoController


# ==============================================================================
# === 1. LOAD FINE-TUNED MISTRAL MODEL (Mac / Non-CUDA Version)
# ==============================================================================

# --- Configuration ---
BASE_MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"
ADAPTER_PATH = "./meLlamo-expert-robot-v1"

print("Loading fine-tuned model for Mac (MPS)...")

# --- Set the device to Apple's Metal Performance Shaders (MPS) ---
device = torch.device("mps")

# --- Load the base model without quantization, specifying a half-precision data type ---
# Note: This will use significantly more RAM/VRAM than the 4-bit version.
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL_ID,
    torch_dtype=torch.float16,  # Use float16 to save memory
    trust_remote_code=True,
).to(device) # Move the model to the MPS device

# --- Load the fine-tuned LoRA adapter and apply it to the base model ---
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)

# --- Load the tokenizer from the adapter directory ---
tokenizer = AutoTokenizer.from_pretrained(ADAPTER_PATH)

print("? Fine-tuned model and tokenizer loaded successfully on MPS device!")


# ==============================================================================
# === 2. VLM, VOICE, AND ROBOT SETUP (Largely Unchanged)
# ==============================================================================

# === VLM for Scene Description (SmolVLM) ===
llm = Llama.from_pretrained(
    repo_id="ggml-org/SmolVLM-500M-Instruct-GGUF",
    filename="SmolVLM-500M-Instruct-Q8_0.gguf",
    verbose=False
)

# === Voice Setup ===
engine = pyttsx3.init()
voices = engine.getProperty('voices')
rate = engine.getProperty('rate')
volume = engine.getProperty('volume')

# === System Prompt ===
try:
    # This is now the "Instruction" part of the prompt
    with open('pices_system_prompt.txt', 'r') as f:
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
sending_to_model = False # Renamed for clarity

# === Camera Setup ===
cam = cv2.VideoCapture(0)

# ==============================================================================
# === 3. HELPER FUNCTIONS (Action Translator Added)
# ==============================================================================

def get_frame_data():
    ret, frame = cam.read()
    if not ret:
        print("Failed to capture frame.")
        return None
    # No need to resize for SmolVLM if it handles it, but can keep for consistency
    _, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes()

def get_scene_description_from_smolvlm(image_bytes: bytes) -> str:
    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
    prompt = f"USER: <image>\nDescribe this scene for a robot assistant.\nASSISTANT:"
    try:
        print("Sending image to SmolVLM for scene description...")
        output = llm(prompt, max_tokens=150, stop=["USER:", "\n"], temperature=0.7)
        description = output['choices'][0]['text'].strip()
        print("SmolVLM Scene Description:", description)
        return description
    except Exception as e:
        print("SmolVLM error:", e)
        return "Unable to describe the scene."

def execute_motion_sequence(actions: List[Dict[str, Any]]) -> bool:
    """This function remains the same, it now receives translated actions."""
    print(f"Executing {len(actions)} translated actions...")
    for i, action in enumerate(actions):
        cmd_type = action.get('type', 'unknown')
        print(f"Action {i + 1}: Type={cmd_type}, Details={action}")
        if cmd_type == 'motor':
            command = action.get('command')
            args = action.get('args', [])
            if command == 'move_up' and args: servo_controller.move_up(args[0])
            elif command == 'move_down' and args: servo_controller.move_down(args[0])
            elif command == 'move_forward' and args: servo_controller.move_forward(args[0])
            elif command == 'move_backward' and args: servo_controller.move_backward(args[0])
            elif command == 'move_left' and args: servo_controller.move_left(args[0])
            elif command == 'move_right' and args: servo_controller.move_right(args[0])
            elif command == 'move_servo' and len(args) >= 2: servo_controller.move_servo(args[0], args[1])
            else: print(f"Unknown motor command: {command}")
        elif cmd_type == 'wait':
            time.sleep(action.get('duration', 1.0))
    return True

def parse_ai_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Finds and parses the first valid JSON object in the model's response."""
    try:
        json_start = response_text.find('{')
        if json_start == -1: return None
        # Attempt to find a matching brace to isolate the JSON object
        brace_count = 0
        json_end = -1
        for i, char in enumerate(response_text[json_start:]):
            if char == '{': brace_count += 1
            elif char == '}': brace_count -= 1
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
# === 4. NEW: ACTION TRANSLATOR
# ==============================================================================
def translate_actions(act_list: List[list]) -> List[Dict[str, Any]]:
    """Translates the new `act` format to the old dictionary format."""
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
        # 7 is 'wait'
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
        elif cmd_id == 7: # Wait command
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
    robot_state_str = json.dumps(robot_state_dict) # Pass state as a clean JSON string

    # 2. Compose the prompt in the fine-tuned format
    input_content = (
        f"User Command: {user_input}\n\n"
        f"Current robot state: {robot_state_str}\n\n"
        f"Scene description: {scene_description}"
    )

    final_prompt = f"""### Instruction:
{INSTRUCTION_PROMPT}

### Input:
{input_content}

### Response:
"""

    # 3. Send to the fine-tuned model
    print("\n--- Sending to Fine-tuned Model ---")
    inputs = tokenizer(final_prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False, # Use greedy for deterministic robot commands
            pad_token_id=tokenizer.eos_token_id
        )

    response_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    model_reply = response_text.split("### Response:")[1].strip()
    print("Model Reply:", model_reply)

    # 4. Parse and execute using the *new* JSON format
    structured_response = parse_ai_response(model_reply)
    if structured_response:
        print("Parsed response successfully.")
        # Translate the 'act' list
        actions_to_execute = translate_actions(structured_response.get('act', []))
        if actions_to_execute:
            threading.Thread(target=execute_motion_sequence, args=(actions_to_execute,)).start()

        # Handle followup using 'fu' and 'fp' keys
        if structured_response.get('fu') and structured_response.get('fp'):
            schedule_followup(structured_response.get('fp'), 3.0)

        # Return the voice response from the 'vr' key
        return structured_response.get('vr', "I processed the command but have nothing to say.")
    else:
        # Fallback if JSON parsing fails
        return model_reply


# ==============================================================================
# === 6. MAIN LOOP (Unchanged Logic, just uses text input now)
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
            # Speak the activation confirmation
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