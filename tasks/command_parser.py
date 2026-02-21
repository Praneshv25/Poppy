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
    recurring: bool  # Is this a recurring task?
    recurring_interval_seconds: Optional[int]  # Interval in seconds (e.g., 300 for 5 minutes)
    recurring_until: Optional[str]  # When to stop recurring

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

╔═══════════════════════════════════════════════════════════════╗
║  CRITICAL: BE EXTREMELY STRICT - Default to NOT scheduling   ║
╚═══════════════════════════════════════════════════════════════╝

INFORMATION QUESTIONS (NOT scheduling - answer NOW):
❌ "When is [event]?" → User wants to KNOW when something is
❌ "When's [event]?" → User wants INFORMATION
❌ "What time is [event]?" → User wants to KNOW the time
❌ "When does [thing] happen?" → User wants INFORMATION
❌ "What is [thing]?" → User wants INFORMATION
❌ "Tell me about [thing]" → User wants INFORMATION NOW
❌ "How's [thing]?" → User wants current STATUS
❌ "What's [thing]?" → User wants INFORMATION NOW

SCHEDULING REQUESTS (YES scheduling - do at FUTURE time):
✅ "Wake me up at [time]"
✅ "Remind me to [action] at [time]"
✅ "Tell me when it's [specific time]" (e.g. "Tell me when it's 3pm")
✅ "Remind me [action] in [duration]"
✅ "Check [thing] at [time]"
✅ "[Action] every [interval]" (recurring)
✅ "Let me know at [time]" (WITH specific future time)

KEY DISTINCTION:
- "When is X?" = Give me information NOW ❌
- "Tell me at X" or "Remind me at X" = Do something LATER ✅

MUST HAVE ONE OF THESE EXPLICIT PHRASES:
- "remind me"
- "wake me up"
- "tell me when it's [specific time]" (NOT "tell me when [event] is")
- "at [specific time]" (with action: "check at 5pm")
- "in [duration]" (with action: "remind in 30 minutes")
- "every [interval]" (recurring)
- "check [thing] at [time]"

NOT scheduling (NO):
- Questions starting with "When", "What", "Where", "How", "Who", "Why"
- "let me know [about something]" (without "at [time]")
- "tell me about" (information request)
- "tell me when [event] is" (asking for info, NOT scheduling)
- "today" when asking for current information
- Any question asking for facts/information

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
  "confirmation_message": "Okay, I'll wake you up at 7 AM tomorrow",
  "recurring": true/false,
  "recurring_interval_seconds": 300 (for "every 5 minutes") or null,
  "recurring_until": "2025-11-05 18:00:00" or null (when to stop recurring)
}}

EXAMPLES:

"Wake me up at 7am tomorrow"
→ {{
  "should_schedule": true,
  "command": "Wake me up",
  "trigger_time": "2025-11-06 07:00:00",
  "completion_mode": "retry_with_condition",
  "retry_until": "2025-11-06 08:00:00",
  "confirmation_message": "Okay, I'll wake you up at 7 AM tomorrow. I'll keep trying until you're out of bed.",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}

"Remind me to take my medicine at 2pm"
→ {{
  "should_schedule": true,
  "command": "Remind me to take my medicine",
  "trigger_time": "2025-11-05 14:00:00",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "Got it, I'll remind you about your medicine at 2 PM today.",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}

"Check every five minutes and make sure I'm not on my phone"
→ {{
  "should_schedule": true,
  "command": "Check that I am not on my phone",
  "trigger_time": "2025-11-05 {(current_time + timedelta(minutes=5)).strftime('%H:%M:%S')}",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "I'll check every 5 minutes to make sure you're not on your phone.",
  "recurring": true,
  "recurring_interval_seconds": 300,
  "recurring_until": null
}}

"Remind me to stretch every hour until 5pm"
→ {{
  "should_schedule": true,
  "command": "Remind me to stretch",
  "trigger_time": "2025-11-05 {(current_time + timedelta(hours=1)).strftime('%H:%M:%S')}",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "I'll remind you to stretch every hour until 5 PM.",
  "recurring": true,
  "recurring_interval_seconds": 3600,
  "recurring_until": "2025-11-05 17:00:00"
}}

"Check if the package arrived at 5pm"
→ {{
  "should_schedule": true,
  "command": "Check if the package arrived",
  "trigger_time": "2025-11-05 17:00:00",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "I'll check for the package at 5 PM today.",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}

"Remind me to drink water"
→ {{
  "should_schedule": true,
  "command": "Remind me to drink water",
  "trigger_time": "2025-11-05 {(current_time + timedelta(minutes=5)).strftime('%H:%M:%S')}",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "I'll remind you to drink water in 5 minutes.",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}

"What's the weather like?"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": "",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}

"Let me know who won the election"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": "",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}

"Tell me about the news today"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": "",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}

"When's the next Super Bowl?"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": "",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}
REASON: This is asking for INFORMATION about when an event occurs, NOT requesting to be notified at that time.

"When is the meeting?"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": "",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}
REASON: User wants to KNOW when the meeting is, not be reminded.

"What time does the game start?"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": "",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}
REASON: User wants to KNOW the time, not schedule a notification.

"Can you search for information about X"
→ {{
  "should_schedule": false,
  "command": "",
  "trigger_time": "",
  "completion_mode": "",
  "retry_until": null,
  "confirmation_message": "",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}

"Tell me when it's 3 o'clock"
→ {{
  "should_schedule": true,
  "command": "Tell me it's 3 o'clock",
  "trigger_time": "2025-11-05 15:00:00",
  "completion_mode": "one_shot",
  "retry_until": null,
  "confirmation_message": "I'll let you know when it's 3 PM.",
  "recurring": false,
  "recurring_interval_seconds": null,
  "recurring_until": null
}}

RECURRING INTERVALS:
- "every X minutes" → recurring_interval_seconds = X * 60
- "every X hours" → recurring_interval_seconds = X * 3600
- "every hour" → recurring_interval_seconds = 3600
- "every day" → recurring_interval_seconds = 86400
- "every 30 seconds" → recurring_interval_seconds = 30

If "until [time]" is mentioned, set recurring_until. Otherwise null (runs forever until manually stopped).

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

╔═══════════════════════════════════════════════════════════════╗
║                    CRITICAL FINAL RULES                       ║
╚═══════════════════════════════════════════════════════════════╝

Be EXTREMELY CONSERVATIVE in detecting scheduling requests!

DEFAULT TO FALSE unless ALL of these are true:
1. User uses explicit scheduling verbs: "remind", "wake", "check at", "tell me at"
2. There is a clear FUTURE time/duration specified
3. User wants an ACTION performed later, NOT information now

NEVER SCHEDULE:
❌ Questions (When? What? Where? How? Who? Why?)
❌ "When is [event]?" - user wants info NOW
❌ "Tell me about [thing]" - user wants info NOW
❌ "What's [thing]?" - user wants info NOW
❌ "Let me know [info]" without "at [time]"
❌ Information requests about future events

ONLY SCHEDULE:
✅ "Remind me [action] at [time]"
✅ "Wake me up at [time]"
✅ "Tell me when it's [specific clock time]"
✅ "Check [thing] at [time]"
✅ "[Action] every [interval]"

When in doubt → should_schedule = false
"""
    
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
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

