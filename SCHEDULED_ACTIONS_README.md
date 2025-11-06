# Scheduled Actions System

A generalized automated task scheduling system for your robot that works with **ANY command** using Gemini's intelligence.

## Overview

The scheduled actions system allows your robot to:
- Execute tasks at specific times
- Retry tasks until completion criteria are met
- Handle complex scenarios like wake-ups, reminders, monitoring, and more
- Make intelligent decisions about task completion using vision and AI

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    speedDemon.py (Main)                    │
├────────────────────────────────────────────────────────────┤
│  Main Thread                    Background Thread          │
│  • Wake word detection          • ActionScheduler          │
│  • Speech transcription         • Monitors database        │
│  • Normal interactions          • Executes due actions     │
│  • Scheduling commands          • Handles retries          │
└────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────────────┐
                    │  Database     │
                    │  (tasks.db)   │
                    └───────────────┘
```

## Files Created

### Core System
- `tasks/scheduled_actions_v2.py` - Database schema and CRUD operations
- `tasks/action_executor_v2.py` - Executes scheduled actions using Gemini
- `tasks/scheduler_v2.py` - Background scheduler thread
- `tasks/command_parser.py` - Parses natural language scheduling requests
- `scheduled_action_system_prompt.txt` - System prompt for scheduled actions

### Tools
- `tasks/schedule_cli.py` - Command-line interface for managing scheduled actions

### Modified
- `speedDemon.py` - Enhanced with scheduler integration

## Usage

### 1. Running the Robot with Scheduler

```bash
python speedDemon.py
```

The scheduler starts automatically in the background.

### 2. Scheduling Actions via Voice

Simply speak naturally to schedule actions:

**Wake-up:**
```
"Mister Carson, wake me up at 7am tomorrow"
```

**Reminders:**
```
"Remind me to drink water at 3pm"
"Remind me to take my medicine in 30 minutes"
"Tell me to stretch in 2 hours"
```

**Monitoring:**
```
"Check if the door is open at midnight"
"Tell me when my coffee is ready"
```

**Notifications:**
```
"Tell me when it's 5 o'clock"
"Let me know at noon"
```

### 3. Managing Scheduled Actions via CLI

```bash
python tasks/schedule_cli.py
```

Options:
1. **List all scheduled actions** - View all scheduled, active, completed tasks
2. **Schedule wake-up** - Create a wake-up action
3. **Schedule reminder** - Create a reminder
4. **Delete action** - Remove a scheduled action

## Completion Modes

### `one_shot`
Execute once and mark as complete. Used for:
- Simple reminders
- Notifications
- Time announcements
- Status checks

**Example:**
```
User: "Remind me to drink water at 3pm"
→ At 3pm: Speaks message once → Complete
```

### `retry_until_acknowledged`
Keep trying until user responds or acknowledges. Used for:
- Important notifications
- Alerts requiring attention

**Example:**
```
User: "Tell me when it's time to leave"
→ Keeps reminding until user interacts
```

### `retry_with_condition`
Keep trying until Gemini determines a condition is met. Used for:
- Wake-ups (retry until person is standing)
- Monitoring (retry until state changes)
- Persistent tasks

**Example:**
```
User: "Wake me up at 7am"
→ At 7am: Scans room, finds person in bed
→ Speaks: "Good morning! Time to wake up!"
→ Checks: Person still lying down
→ Retry in 30s
→ Speaks again: "Time to get up!"
→ Checks: Person is standing
→ Success! "Have a great day!"
```

## How It Works

### 1. Scheduling Flow

```
User says: "Wake me up at 7am"
       ↓
parse_scheduling_request() → Gemini analyzes request
       ↓
Creates database entry:
  - command: "Wake me up"
  - trigger_time: "2025-11-06 07:00:00"
  - completion_mode: "retry_with_condition"
       ↓
Robot confirms: "Okay, I'll wake you up at 7 AM tomorrow"
```

### 2. Execution Flow

```
Scheduler checks time every 10s
       ↓
Finds due action at 7:00:00 AM
       ↓
ActionExecutor.execute_scheduled_action()
       ↓
Captures camera frame + robot state
       ↓
Sends to Gemini with scheduled_action_system_prompt
       ↓
Gemini analyzes scene and decides:
  - What to say
  - What movements to make
  - Is task complete?
  - Should retry?
       ↓
Executes actions and speaks
       ↓
If not complete: schedules retry
If complete: marks as done
```

## Examples

### Wake-Up Sequence

```
7:00:00 AM - Attempt 1
  Gemini sees: Person in bed under blanket
  Says: "Good morning! Time to wake up!"
  Movements: Rise up, lean forward, friendly tilt
  Decision: Person still in bed → Retry in 30s

7:00:30 AM - Attempt 2
  Gemini sees: Person still in bed, but moving
  Says: "Come on, time to get up!"
  Movements: More animated movements
  Decision: Still in bed → Retry in 30s

7:01:00 AM - Attempt 3
  Gemini sees: Person sitting up on edge of bed
  Says: "Great! You're up! Have a wonderful day!"
  Movements: Happy celebration pose
  Decision: Person awake → Complete ✓
```

### Simple Reminder

```
3:00:00 PM
  Gemini sees: User at desk
  Says: "Time to drink some water!"
  Movements: Gentle rise, friendly tilt
  Decision: One-shot mode → Complete ✓
```

### Monitoring Task

```
User: "Tell me when my coffee is ready"

Attempt 1 (10:00 AM):
  Gemini sees: Coffee maker, red light (brewing)
  Says: "Still brewing, I'll let you know when it's ready"
  Decision: Not ready → Retry in 60s

Attempt 2 (10:01 AM):
  Gemini sees: Coffee maker, green light (ready)
  Says: "Your coffee is ready!"
  Decision: Ready → Complete ✓
```

## Database Schema

```sql
CREATE TABLE scheduled_actions (
    id INTEGER PRIMARY KEY,
    command TEXT NOT NULL,              -- "Wake me up"
    trigger_time TEXT NOT NULL,         -- "2025-11-05 07:00:00"
    completion_mode TEXT,               -- "retry_with_condition"
    retry_until TEXT,                   -- Optional deadline
    status TEXT,                        -- "scheduled", "active", "completed"
    attempt_count INTEGER,              -- Number of attempts made
    context TEXT,                       -- Optional JSON context
    last_attempt TEXT                   -- Last execution time
);
```

## Configuration

### Scheduler Check Interval

Default: 10 seconds. Adjust in `speedDemon.py`:

```python
scheduler = ActionScheduler(servo_controller, check_interval=10)
```

### Retry Delays

Gemini decides retry delays dynamically:
- Normal retry: 30 seconds (wake-ups, urgent tasks)
- Patient retry: 60 seconds (monitoring, status checks)

## Troubleshooting

### Scheduler not starting
- Check console for error messages
- Verify database is accessible: `tasks/tasks.db`
- Ensure `scheduled_action_system_prompt.txt` exists

### Actions not triggering
- Verify time format is correct: `YYYY-MM-DD HH:MM:SS`
- Check scheduler is running: Should see "✅ Scheduler started"
- Use CLI to view scheduled actions: `python tasks/schedule_cli.py`

### Gemini not detecting completion
- Check camera is working
- Ensure lighting is adequate
- Review Gemini's reasoning in console output

## Advanced Usage

### Programmatic Scheduling

```python
from tasks.scheduled_actions_v2 import create_scheduled_action
from datetime import datetime, timedelta

# Schedule for specific time
tomorrow_7am = (datetime.now() + timedelta(days=1)).replace(
    hour=7, minute=0, second=0, microsecond=0
)

action = create_scheduled_action(
    command="Wake me up",
    trigger_time=tomorrow_7am.strftime('%Y-%m-%d %H:%M:%S'),
    completion_mode='retry_with_condition',
    retry_until=(tomorrow_7am + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
)
```

### Custom Context

```python
action = create_scheduled_action(
    command="Check on the plants",
    trigger_time="2025-11-05 18:00:00",
    completion_mode='one_shot',
    context={
        'location': 'living room',
        'notes': 'Water if soil is dry'
    }
)
```

## Future Enhancements

Potential improvements:
- Recurring tasks (daily/weekly/monthly)
- Task dependencies (do X after Y completes)
- Priority levels for task execution
- Mobile app for remote scheduling
- Integration with calendar systems
- Voice confirmation for task completion

## Credits

Built on top of:
- speedDemon robot control system
- Gemini 2.0 vision and intelligence
- MediaPipe for pose/face detection
- ElevenLabs for text-to-speech

---

**Enjoy your intelligent scheduled action system!** 🤖⏰

