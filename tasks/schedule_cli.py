"""
Simple CLI for managing scheduled actions
"""
from datetime import datetime, timedelta
from tasks.scheduled_actions_v2 import (
    get_all_scheduled_actions,
    create_scheduled_action,
    delete_scheduled_action
)

def list_scheduled_actions():
    """List all scheduled actions"""
    actions = get_all_scheduled_actions()
    
    if not actions:
        print("\n📋 No scheduled actions")
        return
    
    print("\n📋 Scheduled Actions:")
    print("=" * 80)
    for action in actions:
        status_emoji = {
            'scheduled': '⏰',
            'active': '🔄',
            'completed': '✅',
            'expired': '⏱️'
        }.get(action.status, '❓')
        
        recurring_emoji = '🔄' if action.recurring else ''
        
        print(f"{status_emoji} ID: {action.id} {recurring_emoji}")
        print(f"   Command: {action.command}")
        print(f"   Trigger: {action.trigger_time}")
        print(f"   Mode: {action.completion_mode}")
        print(f"   Status: {action.status} (Attempts: {action.attempt_count})")
        if action.recurring:
            interval_mins = action.recurring_interval_seconds // 60 if action.recurring_interval_seconds else 0
            print(f"   🔄 Recurring: every {interval_mins} minutes")
            if action.recurring_until:
                print(f"   Until: {action.recurring_until}")
        if action.last_attempt:
            print(f"   Last Attempt: {action.last_attempt}")
        print("-" * 80)

def schedule_wake_up():
    """Schedule a wake-up action"""
    print("\n⏰ Schedule Wake-Up")
    
    # Get time
    try:
        hour = int(input("Hour (0-23): "))
        minute = int(input("Minute (0-59): "))
    except ValueError:
        print("❌ Invalid input")
        return
    
    # Calculate trigger time (today or tomorrow)
    now = datetime.now()
    trigger = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if trigger <= now:
        trigger += timedelta(days=1)
    
    message = input("Wake-up message (default: 'Time to wake up!'): ") or "Time to wake up!"
    
    # Calculate retry deadline (1 hour after trigger)
    retry_until = (trigger + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    
    action = create_scheduled_action(
        command=f"Wake me up - {message}",
        trigger_time=trigger.strftime('%Y-%m-%d %H:%M:%S'),
        completion_mode='retry_with_condition',
        retry_until=retry_until
    )
    
    print(f"✅ Wake-up scheduled for {trigger}")
    print(f"   Action ID: {action.id}")
    print(f"   Will retry until: {retry_until}")

def schedule_reminder():
    """Schedule a simple reminder"""
    print("\n📝 Schedule Reminder")
    
    # Get time
    try:
        hour = int(input("Hour (0-23): "))
        minute = int(input("Minute (0-59): "))
    except ValueError:
        print("❌ Invalid input")
        return
    
    # Calculate trigger time
    now = datetime.now()
    trigger = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if trigger <= now:
        trigger += timedelta(days=1)
    
    message = input("Reminder message: ")
    
    if not message:
        print("❌ Message required")
        return
    
    action = create_scheduled_action(
        command=f"Remind me to {message}",
        trigger_time=trigger.strftime('%Y-%m-%d %H:%M:%S'),
        completion_mode='one_shot'
    )
    
    print(f"✅ Reminder scheduled for {trigger}")
    print(f"   Action ID: {action.id}")

def schedule_recurring_task():
    """Schedule a recurring task"""
    print("\n🔄 Schedule Recurring Task")
    
    message = input("Task message: ")
    if not message:
        print("❌ Message required")
        return
    
    try:
        interval_minutes = int(input("Interval in minutes (e.g., 5 for every 5 minutes): "))
        if interval_minutes <= 0:
            print("❌ Interval must be positive")
            return
    except ValueError:
        print("❌ Invalid interval")
        return
    
    # Calculate first trigger time (start after the interval)
    now = datetime.now()
    trigger = (now + timedelta(minutes=interval_minutes)).replace(second=0, microsecond=0)
    
    # Optional: set end time
    end_time_str = input("End time (HH:MM, leave blank for no end): ").strip()
    recurring_until = None
    if end_time_str:
        try:
            end_hour, end_minute = map(int, end_time_str.split(':'))
            recurring_until_dt = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            if recurring_until_dt <= now:
                recurring_until_dt += timedelta(days=1)
            recurring_until = recurring_until_dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            print("❌ Invalid end time format")
            return
    
    action = create_scheduled_action(
        command=message,
        trigger_time=trigger.strftime('%Y-%m-%d %H:%M:%S'),
        completion_mode='one_shot',
        recurring=True,
        recurring_interval_seconds=interval_minutes * 60,
        recurring_until=recurring_until
    )
    
    print(f"✅ Recurring task scheduled!")
    print(f"   Action ID: {action.id}")
    print(f"   First trigger: {trigger}")
    print(f"   Repeats every: {interval_minutes} minutes")
    if recurring_until:
        print(f"   Until: {recurring_until}")
    else:
        print(f"   Runs indefinitely (delete to stop)")

def delete_action():
    """Delete a scheduled action"""
    list_scheduled_actions()
    
    try:
        action_id = int(input("\nEnter action ID to delete: "))
        delete_scheduled_action(action_id)
        print(f"✅ Action {action_id} deleted")
    except ValueError:
        print("❌ Invalid ID")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main CLI loop"""
    while True:
        print("\n" + "=" * 40)
        print("SCHEDULED ACTIONS MANAGER")
        print("=" * 40)
        print("1. List all scheduled actions")
        print("2. Schedule wake-up")
        print("3. Schedule reminder")
        print("4. Schedule recurring task 🔄")
        print("5. Delete action")
        print("6. Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            list_scheduled_actions()
        elif choice == '2':
            schedule_wake_up()
        elif choice == '3':
            schedule_reminder()
        elif choice == '4':
            schedule_recurring_task()
        elif choice == '5':
            delete_action()
        elif choice == '6':
            print("Goodbye!")
            break
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    main()

