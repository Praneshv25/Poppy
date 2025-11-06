#!/usr/bin/env python3
"""
Quick utility to view and clean scheduled actions
"""
from tasks.scheduled_actions_v2 import (
    get_all_scheduled_actions,
    delete_scheduled_action,
    update_action_status
)

def main():
    print("=" * 60)
    print("SCHEDULED ACTIONS DATABASE")
    print("=" * 60)
    
    actions = get_all_scheduled_actions()
    
    if not actions:
        print("\n✅ No scheduled actions in database")
        return
    
    print(f"\n📋 Found {len(actions)} action(s):\n")
    
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
        print(f"   Status: {action.status}")
        print(f"   Attempts: {action.attempt_count}")
        if action.last_attempt:
            print(f"   Last Attempt: {action.last_attempt}")
        print("-" * 60)
    
    # Offer to clean up completed/expired actions
    completed_count = sum(1 for a in actions if a.status in ['completed', 'expired'])
    
    if completed_count > 0:
        print(f"\n🧹 Found {completed_count} completed/expired action(s)")
        response = input("Delete them? (y/n): ").strip().lower()
        
        if response == 'y':
            for action in actions:
                if action.status in ['completed', 'expired']:
                    delete_scheduled_action(action.id)
                    print(f"   ✅ Deleted action {action.id}")
            print(f"\n🎉 Cleaned up {completed_count} action(s)")

if __name__ == "__main__":
    main()

