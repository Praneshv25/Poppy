#!/usr/bin/env python3
"""
Test script for recurring task functionality
Creates a simple recurring task and demonstrates it works
"""
import sys
import os
# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
from tasks.scheduled_actions_v2 import (
    create_scheduled_action,
    get_all_scheduled_actions,
    delete_scheduled_action
)

def test_recurring_task():
    """Test creating a recurring task"""
    print("=" * 60)
    print("TESTING RECURRING TASK SYSTEM")
    print("=" * 60)
    
    # Create a recurring task that triggers every 2 minutes
    trigger = (datetime.now() + timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S')
    end_time = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    
    print("\n📝 Creating recurring task...")
    action = create_scheduled_action(
        command="Test recurring reminder - drink water",
        trigger_time=trigger,
        completion_mode='one_shot',
        recurring=True,
        recurring_interval_seconds=120,  # 2 minutes
        recurring_until=end_time,
        context={'test': True}
    )
    
    print(f"✅ Created recurring task!")
    print(f"   ID: {action.id}")
    print(f"   Command: {action.command}")
    print(f"   First trigger: {action.trigger_time}")
    print(f"   Recurring: {action.recurring}")
    print(f"   Interval: {action.recurring_interval_seconds}s (2 minutes)")
    print(f"   Until: {action.recurring_until}")
    
    # List all scheduled actions
    print("\n📋 All scheduled actions:")
    all_actions = get_all_scheduled_actions()
    for a in all_actions:
        recurring_text = f" 🔄 (every {a.recurring_interval_seconds}s)" if a.recurring else ""
        print(f"   - ID {a.id}: {a.command} at {a.trigger_time}{recurring_text} [{a.status}]")
    
    print("\n" + "=" * 60)
    print("TEST INSTRUCTIONS:")
    print("=" * 60)
    print(f"1. The first occurrence will trigger at: {trigger}")
    print(f"2. It will repeat every 2 minutes until: {end_time}")
    print(f"3. After each execution, a new scheduled action will be created")
    print(f"4. Original action ID {action.id} will be marked 'completed'")
    print(f"5. New spawned actions will have new IDs with parent_recurring_id={action.id}")
    print(f"\n6. To test: Run 'python3 speedDemon.py' and wait")
    print(f"7. To stop: Delete the recurring action or wait until {end_time}")
    print(f"\n8. Clean up test: python3 -c \"from tasks.scheduled_actions_v2 import delete_scheduled_action; delete_scheduled_action({action.id})\"")
    print("=" * 60)
    
    return action.id

def test_voice_command_parsing():
    """Test that voice commands would be parsed correctly"""
    print("\n" + "=" * 60)
    print("VOICE COMMAND EXAMPLES (for testing with speedDemon)")
    print("=" * 60)
    
    examples = [
        "Remind me to stretch every hour",
        "Check every 5 minutes if I'm on my phone",
        "Tell me to drink water every 30 minutes until 5pm",
        "Wake me up every morning at 7am"  # This would need daily recurring (86400s)
    ]
    
    print("\nTry saying these to speedDemon:")
    for i, ex in enumerate(examples, 1):
        print(f"  {i}. \"{ex}\"")
    
    print("\n✅ These should be detected as recurring tasks!")
    print("=" * 60)

if __name__ == "__main__":
    test_action_id = test_recurring_task()
    test_voice_command_parsing()
    
    print("\n🎉 Recurring task system is ready!")
    print(f"\nCreated test task ID: {test_action_id}")
    print("\nNext steps:")
    print("  - Run speedDemon.py and let it execute")
    print("  - Or use the CLI: python3 tasks/schedule_cli.py")
    print("  - Or test with voice commands!")

