import sys
import os
# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents import voice
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
import search.search as search
from pydantic import BaseModel
from ticktick.agent import TickTickAgent
from ticktick.task_poller import TickTickPoller

# Define the structured response model
class RobotResponse(BaseModel):
    vr: str  # voice response
    act: List[List[Any]]  # actions list, e.g., [[4,12],[0,20],[7,1.0]]
    fu: bool  # follow-up needed
    fp: str  # follow-up prompt

# Load environment variables from .env file
load_dotenv(override=True)

# === IMPORT SERVO CONTROLLER ===
from agents.ServoController import ServoController

# === IMPORT WAKE WORD & TRANSCRIPTION ===
from wakeWord.wake import listen_for_wake_word

# === IMPORT SCHEDULER ===
from tasks.scheduler_v2 import ActionScheduler
from tasks.command_parser import parse_scheduling_request
from tasks.scheduled_actions_v2 import create_scheduled_action

# === IMPORT ROBOT ACTIONS ===
from agents.robot_actions import translate_actions, execute_motion_sequence


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

# === ROBOT CONTROLLER INITIALIZATION ===
servo_controller = ServoController()
servo_controller.set_elevation(1)  # Start at middle elevation
servo_controller.set_translation(1)  # Start at middle translation

# === SCHEDULER INITIALIZATION ===
scheduler = ActionScheduler(servo_controller, check_interval=10)
scheduler.start()

# === TICKTICK SUB-AGENT ===
ticktick_agent = TickTickAgent()
if ticktick_agent.start():
    print(f"TickTick sub-agent: Running ✅")
else:
    print(f"TickTick sub-agent: Failed to start ❌ (task management unavailable)")

# === TICKTICK BACKGROUND POLLER ===
task_poller = TickTickPoller(
    ticktick_agent=ticktick_agent,
    voice_fn=voice.stream_audio,
    servo_controller=servo_controller,
    check_interval_minutes=30,
)
if ticktick_agent.is_running():
    task_poller.start()

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


# Motion execution functions now imported from robot_actions module

# === ENHANCED GEMINI REQUEST FUNCTION ===
def get_response(user_input: str, search_context: Optional[str] = None, task_context: Optional[str] = None) -> str:
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
    ]
    
    # Add search context if provided
    if search_context:
        vision_parts.append({"text": f"Search context: {search_context}"})

    # Add task context if provided (from TickTick sub-agent)
    if task_context:
        vision_parts.append({"text": f"Task context: {task_context}"})

    vision_parts.extend([
        {"text": "Here is the current visual scene."},
        {"inline_data": {
            "mime_type": "image/jpeg",
            "data": frame_data
        }}
    ])

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
            response_mime_type="application/json",
            response_schema=RobotResponse,
        )
    )

    # Use structured output directly - no parsing needed!
    robot_response: RobotResponse = response.parsed
    
    print("Gemini:", robot_response.vr)
    print("Actions:", robot_response.act)

    # Execute actions if present
    if robot_response.act and isinstance(robot_response.act, list):
        translated = translate_actions(robot_response.act)
        if translated:
            threading.Thread(target=execute_motion_sequence, args=(translated, servo_controller)).start()

    # fu = robot_response.fu
    # fp = robot_response.fp
    # Follow-up handling can be added here if needed using fu/fp

    conversation_history.append({"role": "model", "parts": [{"text": robot_response.vr}]})
    return robot_response.vr


# === MAIN LOOP ===
print("Robot control system initialized. Listening for wake word 'Mister Carson'...")
print("Current robot state:", servo_controller.get_current_state())
print(f"Scheduler status: {'Running ✅' if scheduler.is_running() else 'Stopped ❌'}")

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
                scheduler.stop()
                listening = False
                break
            
            # === CHECK IF THIS IS A SCHEDULING REQUEST ===
            schedule_request = parse_scheduling_request(transcript)
            
            if schedule_request:
                # This is a scheduling request!
                print(f"📅 Scheduling request detected")
                print(f"   Command: {schedule_request.command}")
                print(f"   Trigger: {schedule_request.trigger_time}")
                print(f"   Mode: {schedule_request.completion_mode}")
                
                # Create the scheduled action in database
                action = create_scheduled_action(
                    command=schedule_request.command,
                    trigger_time=schedule_request.trigger_time,
                    completion_mode=schedule_request.completion_mode,
                    retry_until=schedule_request.retry_until,
                    context={'original_transcript': transcript},
                    recurring=schedule_request.recurring,
                    recurring_interval_seconds=schedule_request.recurring_interval_seconds,
                    recurring_until=schedule_request.recurring_until
                )
                
                # Confirm to user
                voice.stream_audio(schedule_request.confirmation_message)
                print(f"✅ Scheduled action ID: {action.id}")

                # Also add to TickTick for persistent tracking
                if ticktick_agent.is_running():
                    try:
                        ticktick_agent.ask(
                            f"Create a task: '{schedule_request.command}' "
                            f"with due date {schedule_request.trigger_time}"
                        )
                        print(f"📋 Also added to TickTick")
                    except Exception as e:
                        print(f"📋 TickTick sync skipped: {e}")

                continue  # Don't process as normal command

            # === NORMAL INTERACTION ===
            # Get recent conversation context (pass list, not JSON string)
            recent_context = None
            if len(conversation_history) > 0:
                # Pass last 4 items (2 question-answer pairs) as a list
                recent_context = conversation_history[-4:] if len(conversation_history) >= 4 else conversation_history

            # === CHECK IF THIS IS A TASK MANAGEMENT REQUEST ===
            need_task, task_result = ticktick_agent.validate_task_need(
                transcript, conversation_context=recent_context
            )

            # === CHECK IF SEARCH IS NEEDED ===
            need_search, search_result = search.validate_search_need(
                transcript, conversation_context=recent_context
            )

            # Build response with any available context
            reply = get_response(
                transcript,
                search_context=search_result if need_search else None,
                task_context=task_result if need_task else None,
            )
            voice.stream_audio(reply)
        else:
            print("No transcript received.")

    except KeyboardInterrupt:
        print("\nInterrupted by user. Shutting down...")
        task_poller.stop()
        scheduler.stop()
        ticktick_agent.stop()
        listening = False
        break
    except Exception as e:
        print(f"Unexpected error: {e}")

# Cleanup
cam.release()
cv2.destroyAllWindows()
task_poller.stop()
servo_controller.close()
scheduler.stop()
ticktick_agent.stop()
print("Goodbye!")