"""
Generalized Scheduled Actions - Works with ANY command
No hard-coded behaviors, Gemini decides everything
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

# Database configuration
DATABASE_DIR = 'tasks'
DATABASE_NAME = os.path.join(DATABASE_DIR, 'tasks.db')

def get_db_connection():
    """Get database connection for scheduled actions"""
    # Ensure tasks directory exists
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

class ScheduledAction:
    """Generic scheduled action - just a command + trigger time"""
    def __init__(self, id=None, command=None, trigger_time=None, 
                 completion_mode='one_shot', retry_until=None,
                 status='scheduled', attempt_count=0, 
                 context=None, last_attempt=None):
        self.id = id
        self.command = command  # Natural language: "Remind me to drink water"
        self.trigger_time = trigger_time  # When to execute
        self.completion_mode = completion_mode  # 'one_shot', 'retry_until_acknowledged', 'retry_with_condition'
        self.retry_until = retry_until  # Optional: datetime when to stop retrying
        self.status = status  # 'scheduled', 'active', 'completed', 'expired'
        self.attempt_count = attempt_count
        self.context = context  # Optional: JSON with additional context
        self.last_attempt = last_attempt

    def to_dict(self):
        return {
            "id": self.id,
            "command": self.command,
            "trigger_time": self.trigger_time,
            "completion_mode": self.completion_mode,
            "retry_until": self.retry_until,
            "status": self.status,
            "attempt_count": self.attempt_count,
            "context": self.context,
            "last_attempt": self.last_attempt
        }

def create_scheduled_actions_table():
    """Simplified table schema"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            trigger_time TEXT NOT NULL,
            completion_mode TEXT DEFAULT 'one_shot',
            retry_until TEXT,
            status TEXT DEFAULT 'scheduled',
            attempt_count INTEGER DEFAULT 0,
            context TEXT,
            last_attempt TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_scheduled_action(command: str, trigger_time: str,
                           completion_mode: str = 'one_shot',
                           retry_until: Optional[str] = None,
                           context: Optional[Dict] = None) -> ScheduledAction:
    """
    Create a scheduled action
    
    Args:
        command: Natural language command like "Remind me to drink water"
        trigger_time: ISO datetime string
        completion_mode: How to handle completion
            - 'one_shot': Execute once and mark complete
            - 'retry_until_acknowledged': Keep trying until user responds
            - 'retry_with_condition': Keep retrying, let Gemini decide when done
        retry_until: Optional datetime to stop retrying
        context: Optional additional context (e.g., original full transcript)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    context_json = json.dumps(context) if context else None
    
    cursor.execute('''
        INSERT INTO scheduled_actions 
        (command, trigger_time, completion_mode, retry_until, context, status)
        VALUES (?, ?, ?, ?, ?, 'scheduled')
    ''', (command, trigger_time, completion_mode, retry_until, context_json))
    
    action_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return ScheduledAction(
        id=action_id,
        command=command,
        trigger_time=trigger_time,
        completion_mode=completion_mode,
        retry_until=retry_until,
        context=context_json,
        status='scheduled'
    )

def get_due_actions(current_time: str) -> list:
    """Get all actions due for execution"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM scheduled_actions 
        WHERE status IN ('scheduled', 'active')
        AND trigger_time <= ?
        ORDER BY trigger_time ASC
    ''', (current_time,))
    rows = cursor.fetchall()
    conn.close()
    
    actions = []
    for row in rows:
        action = ScheduledAction(**dict(row))
        if action.context:
            try:
                action.context = json.loads(action.context)
            except:
                action.context = None
        actions.append(action)
    
    return actions

def update_action_status(action_id: int, status: str, 
                        attempt_count: Optional[int] = None):
    """Update action status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if attempt_count is not None:
        cursor.execute('''
            UPDATE scheduled_actions 
            SET status = ?, attempt_count = ?, last_attempt = ?
            WHERE id = ?
        ''', (status, attempt_count, current_time, action_id))
    else:
        cursor.execute('''
            UPDATE scheduled_actions 
            SET status = ?, last_attempt = ?
            WHERE id = ?
        ''', (status, current_time, action_id))
    
    conn.commit()
    conn.close()

def update_trigger_time(action_id: int, new_trigger_time: str):
    """Update trigger time for retry"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE scheduled_actions SET trigger_time = ? WHERE id = ?
    ''', (new_trigger_time, action_id))
    conn.commit()
    conn.close()

def get_all_scheduled_actions():
    """Get all scheduled actions"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM scheduled_actions ORDER BY trigger_time ASC')
    rows = cursor.fetchall()
    conn.close()
    
    actions = []
    for row in rows:
        action = ScheduledAction(**dict(row))
        if action.context:
            try:
                action.context = json.loads(action.context)
            except:
                action.context = None
        actions.append(action)
    
    return actions

def delete_scheduled_action(action_id: int):
    """Delete a scheduled action"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM scheduled_actions WHERE id = ?', (action_id,))
    conn.commit()
    conn.close()

# Initialize table on import
create_scheduled_actions_table()

