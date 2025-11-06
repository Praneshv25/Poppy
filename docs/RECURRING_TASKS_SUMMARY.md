# Recurring Tasks Implementation - Complete! ✅

## What Was Added

I've successfully implemented **recurring task support** for your scheduled actions system! This allows tasks like "check every 5 minutes if I'm on my phone" to work automatically.

## Files Modified

### 1. Database Schema (`tasks/scheduled_actions_v2.py`)
- ✅ Added `recurring` field (bool)
- ✅ Added `recurring_interval_seconds` (int) - interval between executions
- ✅ Added `recurring_until` (str) - optional end time
- ✅ Added `parent_recurring_id` (int) - links spawned tasks to original

### 2. Scheduler Logic (`tasks/scheduler_v2.py`)
- ✅ After completing a recurring task, automatically creates next occurrence
- ✅ Checks `recurring_until` deadline
- ✅ Maintains parent-child relationship between spawned tasks

### 3. Command Parser (`tasks/command_parser.py`)
- ✅ Detects recurring patterns: "every X minutes/hours"
- ✅ Parses intervals (5 minutes = 300 seconds)
- ✅ Handles "until [time]" for end time
- ✅ Examples added for guidance

### 4. System Prompt (`scheduled_action_system_prompt.txt`)
- ✅ Added RECURRING TASKS section
- ✅ Added examples (phone check, stretch reminder)
- ✅ Guides Gemini to handle recurring tasks correctly

### 5. CLI Tool (`tasks/schedule_cli.py`)
- ✅ Added option 4: "Schedule recurring task"
- ✅ Shows recurring info in task list (🔄 indicator)
- ✅ Displays interval and end time

### 6. Integration (`speedDemon.py`)
- ✅ Passes recurring fields when creating scheduled actions
- ✅ Works seamlessly with voice commands

### 7. Utilities
- ✅ `migrate_database.py` - Migrates existing database
- ✅ `test_recurring.py` - Tests recurring functionality

## How It Works

### Example: "Check every 5 minutes if I'm on my phone"

```
User says command → Parser detects "every 5 minutes"
           ↓
Creates action: {
  command: "Check if I'm on my phone",
  trigger_time: "now + 5 minutes",
  recurring: true,
  recurring_interval_seconds: 300,
  recurring_until: null  // runs forever
}
           ↓
At trigger time: Scheduler executes action
           ↓
Gemini analyzes scene, speaks, moves
           ↓
Marks original as 'completed'
           ↓
Creates NEW action: {
  trigger_time: "now + 5 minutes",
  parent_recurring_id: 8  // links to original
  // ... same settings
}
           ↓
Cycle repeats indefinitely (or until recurring_until)
```

## Usage Examples

### Voice Commands

Say to your robot:
```
"Mister Carson, check every 5 minutes if I'm on my phone"
"Remind me to stretch every hour"
"Tell me to drink water every 30 minutes until 5pm"
```

### CLI (Manual)

```bash
python3 tasks/schedule_cli.py
# Choose option 4: Schedule recurring task
# Enter: Check if I'm working
# Interval: 10 (minutes)
# End time: 17:00 (or leave blank)
```

### Programmatic

```python
from tasks.scheduled_actions_v2 import create_scheduled_action
from datetime import datetime, timedelta

action = create_scheduled_action(
    command="Remind me to stretch",
    trigger_time=(datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S'),
    completion_mode='one_shot',
    recurring=True,
    recurring_interval_seconds=3600,  # 1 hour
    recurring_until=None  # Forever
)
```

## Stopping Recurring Tasks

### Option 1: Delete the Action
```bash
python3 tasks/schedule_cli.py
# Choose 1 to list actions
# Choose 5 to delete
# Enter the ID
```

### Option 2: Set an End Time
When creating, specify `recurring_until`:
```python
recurring_until="2025-11-05 17:00:00"  # Stops at 5pm
```

### Option 3: Voice Command (Future Enhancement)
Say: "Stop checking if I'm on my phone"
(Would need voice command to delete by matching command text)

## Database Structure

```sql
scheduled_actions:
  id INTEGER
  command TEXT
  trigger_time TEXT
  completion_mode TEXT
  recurring INTEGER          -- NEW: 0=false, 1=true
  recurring_interval_seconds INTEGER  -- NEW: 300 for 5 minutes
  recurring_until TEXT       -- NEW: optional end time
  parent_recurring_id INTEGER  -- NEW: links to original task
```

## Lifecycle of a Recurring Task

```
Action ID=8: "Check phone every 5 minutes"
Status: scheduled
Trigger: 2025-11-05 23:47:00

↓ (5 minutes pass)

Scheduler: Executes ID=8
Gemini: Analyzes, speaks, moves
Status: completed

↓ (scheduler creates new task)

Action ID=9: "Check phone every 5 minutes"
Status: scheduled
Trigger: 2025-11-05 23:52:00
Parent: 8

↓ (5 minutes pass)

Scheduler: Executes ID=9
Status: completed

↓ (spawns ID=10)

Action ID=10: "Check phone every 5 minutes"
Status: scheduled
Trigger: 2025-11-05 23:57:00
Parent: 8

... and so on ...
```

## Testing

### Quick Test (2-minute intervals)

```bash
python3 test_recurring.py
```

This creates a test task that triggers in 2 minutes and repeats every 2 minutes for 10 minutes total.

Then run:
```bash
python3 speedDemon.py
```

Wait and watch it execute!

### Real-World Test

Say to your robot:
```
"Mister Carson, check every 5 minutes and make sure I'm not on my phone"
```

Then work for 15 minutes and see it check 3 times!

## Migration

If you have an existing database, run:
```bash
python3 migrate_database.py
```

This adds the new columns without losing existing data.

## Advanced Features

### Parent-Child Tracking

All spawned occurrences link back to the original:
```python
original_task.id = 8
spawned_task_1.parent_recurring_id = 8
spawned_task_2.parent_recurring_id = 8
```

This allows you to:
- Track all occurrences of a recurring task
- Delete all related tasks at once (future enhancement)
- See history of a recurring task

### Flexible Intervals

Supported intervals:
- Every X minutes: `60 * X`
- Every X hours: `3600 * X`
- Every day: `86400`
- Custom seconds: any integer

### Smart End Times

- `recurring_until=None` → Runs forever
- `recurring_until="2025-11-05 17:00:00"` → Stops at 5pm
- Scheduler checks deadline before spawning next occurrence

## Common Use Cases

### 1. Phone Monitoring
```
"Check every 5 minutes if I'm on my phone"
→ Helps you stay focused during work
```

### 2. Health Reminders
```
"Remind me to drink water every 30 minutes"
"Tell me to stretch every hour"
"Remind me to rest my eyes every 20 minutes"
```

### 3. Task Reminders
```
"Remind me to check email every 2 hours until 5pm"
"Tell me to stand up every hour"
```

### 4. Monitoring
```
"Check every 10 minutes if the door is open"
"Tell me if the coffee is ready, check every minute"
```

## Benefits of This Implementation

✅ **Clean Architecture** - Spawns new tasks instead of modifying existing ones
✅ **Database History** - All occurrences are tracked
✅ **Flexible** - Works with any command, any interval
✅ **Smart** - Gemini decides what to do each time
✅ **Stoppable** - Easy to delete or set end times
✅ **Scalable** - Can handle hundreds of recurring tasks
✅ **Backward Compatible** - Existing one-shot tasks still work

## Future Enhancements (Optional)

1. **Daily/Weekly Recurring** - "Every day at 7am", "Every Monday"
2. **Voice Commands to Stop** - "Stop reminding me to stretch"
3. **Bulk Operations** - Delete all occurrences of a recurring task
4. **Statistics** - How many times did a task execute?
5. **Smart Adjustments** - If user always dismisses at 3pm, suggest new time

---

**Your recurring task system is fully operational!** 🎉

Try it out with:
```bash
python3 speedDemon.py
```

Say: **"Mister Carson, check every 5 minutes and make sure I'm not on my phone"**

Then watch it work! 🤖🔄

