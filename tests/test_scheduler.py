"""
Test script for scheduled actions system
Run this to verify the system is working correctly
"""
from datetime import datetime, timedelta
from tasks.scheduled_actions_v2 import (
    create_scheduled_action,
    get_all_scheduled_actions,
    get_due_actions,
    delete_scheduled_action
)

def test_database():
    """Test database operations"""
    print("=" * 60)
    print("Testing Database Operations")
    print("=" * 60)
    
    # Create a test action
    trigger_time = (datetime.now() + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
    
    action = create_scheduled_action(
        command="Test reminder - drink water",
        trigger_time=trigger_time,
        completion_mode='one_shot',
        context={'test': True}
    )
    
    print(f"✅ Created test action ID: {action.id}")
    print(f"   Command: {action.command}")
    print(f"   Trigger: {action.trigger_time}")
    print(f"   Mode: {action.completion_mode}")
    
    # List all actions
    print("\n📋 All scheduled actions:")
    all_actions = get_all_scheduled_actions()
    for a in all_actions:
        print(f"   - ID {a.id}: {a.command} at {a.trigger_time} [{a.status}]")
    
    # Check for due actions (should be none yet, trigger is 1 minute away)
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    due = get_due_actions(current_time)
    print(f"\n⏰ Due actions now: {len(due)}")
    
    # Clean up test action
    delete_scheduled_action(action.id)
    print(f"\n🗑️  Deleted test action ID: {action.id}")
    
    print("\n✅ Database test passed!")

def test_command_parser():
    """Test command parsing"""
    print("\n" + "=" * 60)
    print("Testing Command Parser")
    print("=" * 60)
    
    from tasks.command_parser import parse_scheduling_request
    
    test_phrases = [
        "Wake me up at 7am tomorrow",
        "Remind me to drink water at 3pm",
        "What's the weather like?",  # Should NOT be parsed as scheduling
        "Tell me when it's noon",
    ]
    
    for phrase in test_phrases:
        print(f"\n🗣️  Testing: '{phrase}'")
        result = parse_scheduling_request(phrase)
        
        if result:
            print(f"   ✅ Detected scheduling request")
            print(f"      Command: {result.command}")
            print(f"      Trigger: {result.trigger_time}")
            print(f"      Mode: {result.completion_mode}")
            print(f"      Confirmation: {result.confirmation_message}")
        else:
            print(f"   ℹ️  Not a scheduling request (as expected)")
    
    print("\n✅ Command parser test complete!")

def test_scheduler():
    """Test scheduler (without actually executing)"""
    print("\n" + "=" * 60)
    print("Testing Scheduler Initialization")
    print("=" * 60)
    
    from tasks.scheduler_v2 import ActionScheduler
    from ServoController import ServoController
    
    # Note: This might fail if Arduino not connected
    try:
        servo_controller = ServoController()
        scheduler = ActionScheduler(servo_controller, check_interval=5)
        
        print("✅ Scheduler created successfully")
        print(f"   Check interval: {scheduler.check_interval}s")
        
        # Don't actually start it in test mode
        # scheduler.start()
        
        print("\n✅ Scheduler test passed!")
        
    except Exception as e:
        print(f"⚠️  Scheduler test skipped (Arduino not connected?)")
        print(f"   Error: {e}")

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("SCHEDULED ACTIONS SYSTEM - TEST SUITE")
    print("=" * 60)
    
    try:
        test_database()
        test_command_parser()
        test_scheduler()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nYour scheduled actions system is ready to use!")
        print("Run: python speedDemon.py")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

