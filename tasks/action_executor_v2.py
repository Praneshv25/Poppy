"""
Generalized Action Executor
Hands ANY scheduled command to Gemini with vision/context
"""
import cv2
import time
import base64
from datetime import datetime
from typing import Dict, Any, Optional, List
from agents import voice
import google.genai as genai
from google.genai.types import GenerateContentConfig
from pydantic import BaseModel
import os
import threading

from agents.ServoController import ServoController

class ScheduledActionResponse(BaseModel):
    """Gemini's response to a scheduled action"""
    vr: str  # Voice response to speak
    act: List[List[Any]]  # Robot actions
    completed: bool  # Is the task done?
    should_retry: bool  # Should we try again?
    retry_delay_seconds: int  # How long to wait before retry
    completion_reason: str  # Why is it complete/incomplete

class ActionExecutor:
    """Executes any scheduled command using Gemini intelligence"""
    
    def __init__(self, servo_controller: Optional[ServoController] = None):
        self.servo_controller = servo_controller or ServoController()
        self.cam = cv2.VideoCapture(0)
        self.client = genai.Client(api_key=os.getenv("API_KEY"))
        
        # Load the scheduled action system prompt
        try:
            # Use absolute path relative to project root
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'scheduled_action_system_prompt.txt')
            with open(config_path, 'r') as f:
                self.scheduled_action_prompt_template = f.read()
        except FileNotFoundError:
            print("⚠️ Warning: scheduled_action_system_prompt.txt not found")
            self.scheduled_action_prompt_template = ""
    
    def execute_scheduled_action(self, command: str, completion_mode: str, 
                                 attempt_count: int, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute ANY scheduled command by asking Gemini
        
        Returns: {
            'completed': bool,
            'should_retry': bool,
            'retry_delay': int,
            'voice_response': str
        }
        """
        print(f"\n{'='*60}")
        print(f"⏰ SCHEDULED ACTION (Attempt #{attempt_count + 1})")
        print(f"Command: {command}")
        print(f"Mode: {completion_mode}")
        print(f"{'='*60}\n")
        
        # Get current scene
        ret, frame = self.cam.read()
        if not ret:
            print("⚠️ Failed to capture frame")
            return {
                'completed': False,
                'should_retry': True,
                'retry_delay': 10,
                'voice_response': None,
                'reason': 'Camera failure'
            }
        
        # Encode frame
        resized = cv2.resize(frame, (224, 224))
        _, buffer = cv2.imencode('.jpg', resized)
        frame_data = base64.b64encode(buffer).decode('utf-8')
        
        # Get robot state
        robot_state = self.servo_controller.get_current_state()
        
        # Build the final prompt with dynamic values
        scheduled_action_prompt = f"""
{self.scheduled_action_prompt_template}

CURRENT EXECUTION DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCHEDULED COMMAND: "{command}"
COMPLETION MODE: {completion_mode}
ATTEMPT NUMBER: {attempt_count + 1}
ROBOT STATE: {robot_state}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Execute this scheduled command now.
"""
        
        try:
            # Call Gemini with the scheduled action
            response = self.client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": scheduled_action_prompt},
                            {"inline_data": {
                                "mime_type": "image/jpeg",
                                "data": frame_data
                            }}
                        ]
                    }
                ],
                config=GenerateContentConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=ScheduledActionResponse,
                )
            )
            
            result: ScheduledActionResponse = response.parsed
            
            print(f"🤖 Gemini Response:")
            print(f"   Say: {result.vr}")
            print(f"   Actions: {result.act}")
            print(f"   Completed: {result.completed}")
            print(f"   Should Retry: {result.should_retry}")
            print(f"   Reason: {result.completion_reason}")
            print(f"\n🎯 Starting action execution...")
            
            # Execute actions
            if result.act:
                try:
                    from agents.robot_actions import translate_actions, execute_motion_sequence
                    translated = translate_actions(result.act)
                    if translated:
                        threading.Thread(
                            target=execute_motion_sequence, 
                            args=(translated, self.servo_controller)
                        ).start()
                        time.sleep(0.5)  # Brief delay for movements to start
                except Exception as e:
                    print(f"⚠️  Error executing movements: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Speak response
            if result.vr:
                try:
                    print(f"🔊 Speaking: '{result.vr}'")
                    voice.stream_audio(result.vr)
                    print(f"✅ Voice completed")
                    # Give audio time to finish playing before function returns
                    # Estimate ~3 seconds per sentence
                    estimated_duration = len(result.vr.split()) * 0.4  # ~0.4s per word
                    time.sleep(max(2.0, estimated_duration))  # At least 2 seconds
                except Exception as e:
                    print(f"❌ Voice error: {e}")
                    import traceback
                    traceback.print_exc()
            
            return {
                'completed': result.completed,
                'should_retry': result.should_retry,
                'retry_delay': result.retry_delay_seconds,
                'voice_response': result.vr,
                'reason': result.completion_reason
            }
            
        except Exception as e:
            print(f"❌ Error executing scheduled action: {e}")
            return {
                'completed': False,
                'should_retry': True,
                'retry_delay': 60,
                'voice_response': None,
                'reason': f'Error: {str(e)}'
            }
    
    def cleanup(self):
        """Clean up resources"""
        self.cam.release()
        cv2.destroyAllWindows()

