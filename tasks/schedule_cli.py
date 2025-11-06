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
        
        print(f"{status_emoji} ID: {action.id}")
        print(f"   Command: {action.command}")
        print(f"   Trigger: {action.trigger_time}")
        print(f"   Mode: {action.completion_mode}")
        print(f"   Status: {action.status} (Attempts: {action.attempt_count})")
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
        print("4. Delete action")
        print("5. Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            list_scheduled_actions()
        elif choice == '2':
            schedule_wake_up()
        elif choice == '3':
            schedule_reminder()
        elif choice == '4':
            delete_action()
        elif choice == '5':
            print("Goodbye!")
            break
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    main()

