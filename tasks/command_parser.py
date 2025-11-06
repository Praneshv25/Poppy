"""
Parse natural language scheduling requests using Gemini
"""
import google.genai as genai
from google.genai.types import GenerateContentConfig
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import os

class SchedulingRequest(BaseModel):
    """Parsed scheduling request"""
    should_schedule: bool
    command: str
    trigger_time: str  # ISO format
    completion_mode: str  # 'one_shot', 'retry_until_acknowledged', 'retry_with_condition'
    retry_until: Optional[str]  # Optional deadline
    confirmation_message: str  # What to say to user

def parse_scheduling_request(transcript: str) -> Optional[SchedulingRequest]:
    """
    Use Gemini to parse ANY scheduling request
    
    Examples:
    - "Wake me up at 7am" → retry_with_condition
    - "Remind me to drink water at 3pm" → one_shot
    - "Tell me to stretch every hour" → one_shot (recurring handled separately)
    - "Check if I'm still working at 5pm" → retry_with_condition
    """
    client = genai.Client(api_key=os.getenv("API_KEY"))
    
    current_time = datetime.now()
    current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
    current_day = current_time.strftime('%A')  # Monday, Tuesday, etc.
    
    parsing_prompt = f"""
Analyze this user request and determine if it's a scheduling request.

Current date/time: {current_time_str} ({current_day})

User said: "{transcript}"

IMPORTANT: Only consider this a scheduling request if there is EXPLICIT time-related language indicating a FUTURE action.

Scheduling indicators (YES):
- "at [time]" - "at 7am", "at 3pm", "at midnight"
- "in [duration]" - "in 20 minutes", "in 2 hours"
- "tomorrow", "tonight", "next week"
- "wake me up at/in/tomorrow"
- "remind me at/in/tomorrow"
- "tell me when it's [time]"

NOT scheduling (NO):
- "let me know [about something]" (without specific future time)
- "tell me about" (current information)
- Questions without time indicators
- "today" when asking for current information

Determine:
1. Is this a request to schedule a FUTURE action with a SPECIFIC time?
2. If yes:
   - What is the command to execute later?
   - When should it trigger?
   - What completion mode?
     * "one_shot": Just deliver message once (reminders, notifications)
     * "retry_until_acknowledged": Keep trying until user responds
     * "retry_with_condition": Keep trying until condition met (wake up, check status)
   - Optional: deadline to stop retrying
   - What to say to confirm the scheduling?

OUTPUT (JSON):
{{
  "should_schedule": true/false,
  "command": "the command to execute later",
  "trigger_time": "2025-11-05 15:00:00" (ISO format),
  "completion_mode": "one_shot|retry_until_acknowledged|retry_with_condition",
  "retry_until": "2025-11-05 15:30:00" or null,
  "confirmation_message": "Okay, I'll wake you up at 7 AM tomorrow"
}}

EXAMPLES:

"Wake me up at 7am tomorrow"
→ {{
  "should_schedule": true,
  "command": "Wake me up",
  "trigger_time": "2025-11-06 07:00:00",
  "completion_mode": "retry_with_condition",
  "retry_until": "2025-11-06 08:00:00",
  "confirmation_message": "Okay, I'll wake you up at 7 AM tomorrow. I'll keep trying until you're out of bed."
}}

"Remind me to take my medicine at 2pm"
→ {{
  "should_schedule": true,
  "command": "Remind me to take my medicine",
  "trigger_time": "2025-11-05 14:00:00",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "Got it, I'll remind you about your medicine at 2 PM today."
}}

"Check if the package arrived at 5pm"
→ {{
  "should_schedule": true,
  "command": "Check if the package arrived",
  "trigger_time": "2025-11-05 17:00:00",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "I'll check for the package at 5 PM today."
}}

"Remind me to drink water"
→ {{
  "should_schedule": true,
  "command": "Remind me to drink water",
  "trigger_time": "2025-11-05 {(current_time + timedelta(minutes=5)).strftime('%H:%M:%S')}",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "I'll remind you to drink water in 5 minutes."
}}

"What's the weather like?"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": ""
}}

"Let me know who won the election"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": ""
}}

"Tell me about the news today"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": ""
}}

"Can you search for information about X"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": ""
}}

"Tell me when it's 3 o'clock"
→ {{
  "should_schedule": true,
  "command": "Tell me it's 3 o'clock",
  "trigger_time": "2025-11-05 15:00:00",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "I'll let you know when it's 3 PM."
}}

TIME PARSING RULES:
- "7am tomorrow" → next day at 7:00
- "2pm" or "2pm today" → today at 14:00
- "in 30 minutes" → current time + 30 minutes
- "in 2 hours" → current time + 2 hours
- "at noon" → 12:00
- "at midnight" → 00:00 (next day if past midnight)
- If time has passed today, schedule for tomorrow
- Be smart about context (if user says "7am" at 8pm, they mean tomorrow)

COMPLETION MODE GUIDELINES:
- Wake-up tasks: retry_with_condition (keep trying until person is up)
- Simple reminders: one_shot (just deliver message once)
- Status checks: one_shot (check and report)
- Alarms/notifications: one_shot
- Monitoring tasks: retry_with_condition (keep checking until condition met)

CRITICAL: Be CONSERVATIVE in detecting scheduling requests!
- If there's NO explicit future time indicator → NOT a scheduling request
- "Let me know", "tell me about", "what is" without time → NOT scheduling
- Questions about current events → NOT scheduling
- Only schedule when user CLEARLY wants something to happen at a FUTURE time
"""
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[{"role": "user", "parts": [{"text": parsing_prompt}]}],
            config=GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=SchedulingRequest
            )
        )
        
        result: SchedulingRequest = response.parsed
        
        if result.should_schedule:
            print(f"✅ Parsed scheduling request:")
            print(f"   Command: {result.command}")
            print(f"   Trigger: {result.trigger_time}")
            print(f"   Mode: {result.completion_mode}")
            return result
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error parsing scheduling request: {e}")
        return None

