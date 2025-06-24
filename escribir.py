from ollama import chat, ChatResponse
from eyes import capture_image, describe_image_with_llava
import json
from vector import add_document, retrieve_context
from task_manager import create_task, get_all_tasks, get_upcoming_reminders, update_task, delete_task, search_tasks_semantically
from datetime import datetime
import re
import time # Added for sleep in terminal_loop
from datetime import datetime, timedelta
#
# FRIDAY_SYS_PROMPT = """
# You are Friday, a concise, helpful AI assistant that returns decisions in strict JSON.
#
# Always respond with only a valid JSON object:
#
# {
#   "requires_vision": true | false,
#   "requires_external_context": true | false,
#   "requires_personal_context": true | false,
#   "store_personal_context": true | false,
#   "store_as_task": true | false,
#   "model_complexity": "default" | "advanced",
#   "reason": "short explanation",
#   "response": "your reply to the user"
# }
#
# Flags:
# - "requires_vision": set true if the user asks about an image or visual input.
# - "requires_external_context": set true for current events or unknown facts.
# - "requires_personal_context": set true if the question depends on user's past or preferences.
# - "store_personal_context": true if user gives new info Friday should remember.
# - "store_as_task": true if the message is a todo/reminder with a clear time or deadline.
# - "model_complexity": "advanced" only for abstract or risky reasoning.
#
# Examples:
#
# User: "What do you see in this image?"
# ? {
#   "requires_vision": true,
#   "requires_external_context": false,
#   "requires_personal_context": false,
#   "store_personal_context": false,
#   "store_as_task": false,
#   "model_complexity": "default",
#   "reason": "User asked about an image",
#   "response": "Let me look at the image."
# }
#
# User: "Remind me to call mom at 7pm."
# ? {
#   "requires_vision": false,
#   "requires_external_context": false,
#   "requires_personal_context": false,
#   "store_personal_context": false,
#   "store_as_task": true,
#   "model_complexity": "default",
#   "reason": "Future reminder with time",
#   "response": "Got it. I?ll remind you to call mom at 7pm."
# }
#
# Be brief and clear. Never return text outside the JSON.
# """

FRIDAY_SYS_PROMPT = """
You are Friday, a concise, helpful AI assistant. Always respond with a valid JSON object and nothing else.

The format is:

{
  "requires_vision": true | false,
  "requires_external_context": true | false,
  "requires_personal_context": true | false,
  "store_personal_context": true | false,
  "store_as_task": true | false,
  "model_complexity": "default" | "advanced",
  "reason": "short explanation",
  "response": "short human-style reply"
}

Example:

User: "Remind me to eat at 9:40 pm today"
?
{
  "requires_vision": false,
  "requires_external_context": false,
  "requires_personal_context": false,
  "store_personal_context": false,
  "store_as_task": true,
  "model_complexity": "default",
  "reason": "Future reminder with time",
  "response": "Got it. I'll remind you to eat at 9:40 PM today."
}

Only return the JSON. Never include text outside the object. Never omit a key.
"""





convo_history = [{
    "role": "system",
    "content": FRIDAY_SYS_PROMPT
}]


def handle_request(request):
    convo_history.append({
        "role": "user",
        "content": request
    })

    response: ChatResponse = chat(model='llama3.1:8b', messages=convo_history)
    reply = response.message.content.strip()

    try:
        parsed = json.loads(reply)
        convo_history.append({ "role": "assistant", "content": parsed['response'] })

        return {
            **parsed,
            "original_request": request
        }

    except json.JSONDecodeError:
        print("[?] Failed to parse JSON from assistant response.")
        print("Raw reply:", reply)

        convo_history.append({ "role": "assistant", "content": reply })
        return {
            "requires_vision": False,
            "requires_external_context": False,
            "requires_personal_context": False,
            "store_personal_context": False,
            "store_as_task": False,
            "model_complexity": "default",
            "reason": "Parsing failed",
            "response": reply,
            "original_request": request
        }


def process_user_request(user_input):
    result = handle_request(user_input)
    print(result)

    # Step 1: Handle vision
    if result["requires_vision"]:
        image_path = capture_image("frame.jpg")
        vision_desc = describe_image_with_llava(image_path)

        followup = f"""The user asked: "{result['original_request']}"
Here is what I see: "{vision_desc}"
Please answer the original question now using this visual context."""

        convo_history.append({ "role": "user", "content": followup })
        response = chat(model='llama3.2', messages=convo_history)
        reply = response.message.content.strip()
        convo_history.append({ "role": "assistant", "content": reply })
        result["response"] = reply # Update the main response
        # Removed: print("\nFriday (vision-assisted):", reply)

    # Step 2: External context (placeholder)
    if result["requires_external_context"]:
        print("[?] External context needed ? Not yet implemented.")

    # Step 3: Query personal context
    if result["requires_personal_context"]:
        info = retrieve_context(convo_history[-1]['content'])
        print("[?] Retrieve personal context")

        followup_message = f"""The user asked: "{result['original_request']}"
Here is relevant personal context: "{info}"
Please answer the original question now using this context."""

        convo_history.append({ "role": "user", "content": followup_message })
        response = chat(model='llama3.2', messages=convo_history)
        reply = response.message.content.strip()
        convo_history.append({ "role": "assistant", "content": reply })
        result["response"] = reply # Update the main response
        # Removed: print("\nFriday (context-assisted):", reply)

    # Step 4: Store new memory or task
    if result["store_personal_context"]:
        print("Trying to add: ", result['original_request'])
        add_document(result['original_request'])
        print("[?] Store personal context.")
        # Append to the existing response
        result["response"] += " Noted. I've stored that in your memory."

    if result["store_as_task"]:
        task_details = parse_task_details(result['original_request'])
        new_task = create_task(
            description=task_details['description'],
            due_date=task_details['due_date'],
            due_time=task_details['due_time'],
            reminder_time=task_details['reminder_time'],
            priority=task_details['priority']
        )
        print(f"Task stored: '{new_task.description}' with ID: {new_task.id}")
        result["response"] += f" I've added '{new_task.description}' to your tasks."
        if new_task.reminder_time:
            result["response"] += f" I'll remind you on {new_task.reminder_time}."

    # Step 5: Handle complex models (optional switch) # Prob won't need
    # if result["model_complexity"] == "advanced":
    #     print("[?] Consider switching to an advanced model ? optional.")

    return result["response"]

def parse_task_details(text):
    description = text
    due_date = None
    due_time = None
    reminder_time = None
    priority = None

    # Regex for due date (YYYY-MM-DD)
    date_match = re.search(r'\b(on|by)\s+(\d{4}-\d{2}-\d{2})\b', text, re.IGNORECASE)
    if date_match:
        due_date = date_match.group(2)
        description = description.replace(date_match.group(0), '').strip()

    # Regex for due time (HH:MM or HH:MM:SS)Wh
    time_match = re.search(r'\b(at)\s+(\d{1,2}:\d{2}(?::\d{2})?)\b', text, re.IGNORECASE)
    if time_match:
        due_time = time_match.group(2)
        description = description.replace(time_match.group(0), '').strip()

    # Regex for reminder time (e.g., "remind me at 10:30", "reminder in 5 minutes")
    reminder_match = re.search(r'\bremind me (at|in)\s+(.+?)(?:\.|$)', text, re.IGNORECASE)
    if reminder_match:
        reminder_phrase = reminder_match.group(2).strip()
        current_time = datetime.now()
        try:
            if reminder_match.group(1).lower() == 'at':
                # Try to parse as a specific time today
                parsed_time = datetime.strptime(reminder_phrase, '%H:%M').time()
                reminder_dt = current_time.replace(hour=parsed_time.hour, minute=parsed_time.minute, second=0, microsecond=0)
                if reminder_dt < current_time: # If time is in the past, assume next day
                    reminder_dt += timedelta(days=1)
                reminder_time = reminder_dt.strftime('%Y-%m-%d %H:%M:%S')
            elif reminder_match.group(1).lower() == 'in':
                # Try to parse as a timedelta (e.g., "5 minutes", "2 hours")
                num_match = re.search(r'(\d+)\s+(minute|hour|day)s?', reminder_phrase, re.IGNORECASE)
                if num_match:
                    num = int(num_match.group(1))
                    unit = num_match.group(2).lower()
                    if 'minute' in unit:
                        reminder_dt = current_time + timedelta(minutes=num)
                    elif 'hour' in unit:
                        reminder_dt = current_time + timedelta(hours=num)
                    elif 'day' in unit:
                        reminder_dt = current_time + timedelta(days=num)
                    reminder_time = reminder_dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass # Could not parse reminder time

        description = description.replace(reminder_match.group(0), '').strip()

    # Regex for priority
    priority_match = re.search(r'\b(high|medium|low) priority\b', text, re.IGNORECASE)
    if priority_match:
        priority = priority_match.group(1).lower()
        description = description.replace(priority_match.group(0), '').strip()

    # Clean up description from common task phrases
    description = re.sub(r'^(add|create|schedule|set|make) (a )?(task|reminder|todo)\s*', '', description, flags=re.IGNORECASE).strip()
    description = re.sub(r'\s+to\s+do$', '', description, flags=re.IGNORECASE).strip()


    return {
        "description": description,
        "due_date": due_date,
        "due_time": due_time,
        "reminder_time": reminder_time,
        "priority": priority
    }

def check_and_notify_reminders():
    reminders = get_upcoming_reminders()
    for task in reminders:
        print(f"\n--- REMINDER ---")
        print(f"Task ID: {task.id}")
        print(f"Description: {task.description}")
        if task.due_date:
            print(f"Due Date: {task.due_date}")
        if task.due_time:
            print(f"Due Time: {task.due_time}")
        if task.reminder_time:
            print(f"Reminder Time: {task.reminder_time}")
        print(f"Status: {task.status}")
        print(f"Priority: {task.priority}")
        print(f"----------------\n")
        # Optionally, update task status to 'notified' or similar to prevent repeat notifications
        # update_task(task.id, status='notified') # This would require a 'notified' status

def terminal_loop():
    print("Talk to Friday. Type your message below:")
    while True:
        user_input = input("> ").strip()
        if user_input.lower() == 'list tasks':
            tasks = get_all_tasks()
            if tasks:
                print("\n--- Your Tasks ---")
                for task in tasks:
                    print(f"ID: {task.id}, Desc: {task.description}, Due: {task.due_date} {task.due_time or ''}, Reminder: {task.reminder_time or ''}, Status: {task.status}, Priority: {task.priority}")
                print("------------------\n")
            else:
                print("No tasks found.")
        elif user_input.lower() == 'check reminders':
            check_and_notify_reminders()
        elif user_input:
            process_user_request(user_input)
        else:
            # Periodically check for reminders even if no input
            check_and_notify_reminders()
        # Add a small delay to prevent busy-waiting in the loop
        time.sleep(1)


if __name__ == "__main__":
    terminal_loop()
