"""
Simplified scheduler - hands everything to Gemini
"""
import time
import threading
from datetime import datetime, timedelta
from typing import Optional

from tasks.scheduled_actions_v2 import (
    get_due_actions,
    update_action_status,
    update_trigger_time,
    create_scheduled_action
)
from tasks.action_executor_v2 import ActionExecutor
from agents.ServoController import ServoController

class ActionScheduler:
    """Background scheduler for automated actions"""
    
    def __init__(self, servo_controller: Optional[ServoController] = None,
                 check_interval: int = 10):
        self.servo_controller = servo_controller or ServoController()
        self.executor = ActionExecutor(self.servo_controller)
        self.check_interval = check_interval
        self.running = False
        self.scheduler_thread = None
    
    def start(self):
        """Start the scheduler"""
        if self.running:
            print("Scheduler already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        print(f"✅ Scheduler started (checking every {self.check_interval}s)")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        self.executor.cleanup()
        print("🛑 Scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                due_actions = get_due_actions(current_time)
                
                for action in due_actions:
                    # Update to active
                    update_action_status(action.id, 'active', action.attempt_count)
                    
                    # Execute via Gemini
                    result = self.executor.execute_scheduled_action(
                        command=action.command,
                        completion_mode=action.completion_mode,
                        attempt_count=action.attempt_count,
                        context=action.context
                    )
                    
                    if result['completed']:
                        # Task complete!
                        update_action_status(action.id, 'completed')
                        print(f"✅ Action {action.id} completed: {result['reason']}")
                        
                        # Handle recurring tasks
                        if action.recurring and action.recurring_interval_seconds:
                            # Check if we should continue recurring
                            if action.recurring_until:
                                recurring_deadline = datetime.strptime(action.recurring_until, '%Y-%m-%d %H:%M:%S')
                                if datetime.now() >= recurring_deadline:
                                    print(f"⏰ Recurring action {action.id} reached end time, stopping")
                                    continue
                            
                            # Create next occurrence
                            next_trigger = (
                                datetime.now() + timedelta(seconds=action.recurring_interval_seconds)
                            ).strftime('%Y-%m-%d %H:%M:%S')
                            
                            # Get parent_id (if this is already a spawned recurring task, keep original parent)
                            parent_id = action.parent_recurring_id if action.parent_recurring_id else action.id
                            
                            new_action = create_scheduled_action(
                                command=action.command,
                                trigger_time=next_trigger,
                                completion_mode=action.completion_mode,
                                context=action.context,
                                recurring=True,
                                recurring_interval_seconds=action.recurring_interval_seconds,
                                recurring_until=action.recurring_until,
                                parent_recurring_id=parent_id
                            )
                            
                            print(f"🔄 Recurring action spawned: ID {new_action.id} at {next_trigger}")
                    
                    elif result['should_retry']:
                        # Check if we should still retry
                        if action.retry_until:
                            retry_deadline = datetime.strptime(action.retry_until, '%Y-%m-%d %H:%M:%S')
                            if datetime.now() > retry_deadline:
                                update_action_status(action.id, 'expired')
                                print(f"⏰ Action {action.id} expired")
                                continue
                        
                        # Schedule next retry
                        next_attempt = (
                            datetime.now() + timedelta(seconds=result['retry_delay'])
                        ).strftime('%Y-%m-%d %H:%M:%S')
                        
                        update_trigger_time(action.id, next_attempt)
                        update_action_status(action.id, 'scheduled', action.attempt_count + 1)
                        print(f"🔄 Action {action.id} will retry at {next_attempt}")
                    
                    else:
                        # No retry needed but not completed (edge case)
                        update_action_status(action.id, 'completed')
                
                time.sleep(self.check_interval)
            
            except Exception as e:
                print(f"❌ Scheduler error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(self.check_interval)
    
    def is_running(self) -> bool:
        return self.running

