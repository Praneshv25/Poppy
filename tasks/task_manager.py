import sys
import os
# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
import uuid
from datetime import datetime

# Assuming vector.py is in the same directory or accessible via PYTHONPATH
from tasks.vector import add_document, retrieve_context

DATABASE_NAME = 'tasks.db'

class Task:
    def __init__(self, id=None, description=None, due_date=None, due_time=None,
                 reminder_time=None, status='pending', priority='medium', vector_id=None):
        self.id = id
        self.description = description
        self.due_date = due_date
        self.due_time = due_time
        self.reminder_time = reminder_time
        self.status = status
        self.priority = priority
        self.vector_id = vector_id

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "due_date": self.due_date,
            "due_time": self.due_time,
            "reminder_time": self.reminder_time,
            "status": self.status,
            "priority": self.priority,
            "vector_id": self.vector_id
        }

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # This allows accessing columns by name
    return conn

def create_tasks_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            due_date TEXT,
            due_time TEXT,
            reminder_time TEXT,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            vector_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_task(description, due_date=None, due_time=None, reminder_time=None,
                status='pending', priority='medium'):
    conn = get_db_connection()
    cursor = conn.cursor()

    vector_id = None
    if description:
        # Add document to ChromaDB and get its vector_id
        doc_id = str(uuid.uuid4()) # Generate UUID here
        add_document(doc_text=description, doc_id=doc_id) # Pass doc_id to add_document
        vector_id = doc_id

    cursor.execute('''
        INSERT INTO tasks (description, due_date, due_time, reminder_time, status, priority, vector_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (description, due_date, due_time, reminder_time, status, priority, vector_id))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return Task(id=task_id, description=description, due_date=due_date,
                due_time=due_time, reminder_time=reminder_time, status=status,
                priority=priority, vector_id=vector_id)

def get_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return Task(**row)
    return None

def get_all_tasks():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks')
    rows = cursor.fetchall()
    conn.close()
    return [Task(**row) for row in rows]

def update_task(task_id, description=None, due_date=None, due_time=None,
                 reminder_time=None, status=None, priority=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    current_task = get_task(task_id)
    if not current_task:
        conn.close()
        return None

    updates = []
    params = []

    if description is not None and description != current_task.description:
        updates.append('description = ?')
        params.append(description)
        # Re-embed if description changes
        if current_task.vector_id:
            # In a real scenario, you might want to remove the old embedding first
            # For simplicity, we'll just add a new one and update the vector_id
            pass # For now, we'll handle re-embedding in a more robust way later if needed
        new_vector_id = str(uuid.uuid4())
        add_document(doc_text=description, doc_id=new_vector_id)
        updates.append('vector_id = ?')
        params.append(new_vector_id)
    elif description is None and current_task.description is None:
        # If description is explicitly set to None and was None, do nothing
        pass
    elif description is None and current_task.description is not None:
        # If description is explicitly set to None but was not None, clear it
        updates.append('description = ?')
        params.append(None)
        updates.append('vector_id = ?')
        params.append(None) # Clear vector_id if description is cleared

    if due_date is not None:
        updates.append('due_date = ?')
        params.append(due_date)
    if due_time is not None:
        updates.append('due_time = ?')
        params.append(due_time)
    if reminder_time is not None:
        updates.append('reminder_time = ?')
        params.append(reminder_time)
    if status is not None:
        updates.append('status = ?')
        params.append(status)
    if priority is not None:
        updates.append('priority = ?')
        params.append(priority)

    if not updates:
        conn.close()
        return current_task # No updates to perform

    query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
    params.append(task_id)

    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()
    return get_task(task_id)

def delete_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0 # True if a row was deleted

def get_tasks_by_status(status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE status = ?', (status,))
    rows = cursor.fetchall()
    conn.close()
    return [Task(**row) for row in rows]

def get_tasks_by_due_date(date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE due_date = ? ORDER BY due_time ASC', (date,))
    rows = cursor.fetchall()
    conn.close()
    return [Task(**row) for row in rows]

def get_tasks_by_priority(priority):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE priority = ?', (priority,))
    rows = cursor.fetchall()
    conn.close()
    return [Task(**row) for row in rows]

def get_upcoming_reminders():
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        SELECT * FROM tasks
        WHERE reminder_time IS NOT NULL AND reminder_time <= ? AND status != 'completed'
        ORDER BY reminder_time ASC
    ''', (now,))
    rows = cursor.fetchall()
    conn.close()
    return [Task(**row) for row in rows]

def search_tasks_semantically(query):
    # Retrieve relevant document IDs and documents from ChromaDB
    relevant_docs, relevant_ids = retrieve_context(query)
    if not relevant_ids:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create a placeholder string for the IN clause (e.g., '?,?,?')
    placeholders = ','.join('?' * len(relevant_ids))
    query_sql = f'SELECT * FROM tasks WHERE vector_id IN ({placeholders})'

    cursor.execute(query_sql, relevant_ids)
    rows = cursor.fetchall()
    conn.close()

    # Return tasks, maintaining the order of relevance from ChromaDB if possible,
    # or simply all found tasks. For now, just return all found tasks.
    found_tasks = {row['vector_id']: Task(**row) for row in rows}
    
    # Reorder tasks based on the order of relevant_ids from ChromaDB
    ordered_tasks = []
    for doc_id in relevant_ids:
        if doc_id in found_tasks:
            ordered_tasks.append(found_tasks[doc_id])
    
    return ordered_tasks

# Initialize the database when the module is imported
create_tasks_table()

print(get_all_tasks())
#
# if __name__ == "__main__":
#     # Example Usage:
#     print("Initializing tasks database...")
#     create_tasks_table()
#
#     # Create some tasks
#     task1 = create_task("Buy groceries for dinner", "2025-06-17", "18:00:00", "2025-06-17 17:30:00", priority="high")
#     task2 = create_task("Finish report for work", "2025-06-18", "09:00:00", "2025-06-18 08:00:00", status="in_progress")
#     task3 = create_task("Call mom", None, None, "2025-06-17 10:30:00", priority="medium")
#     task4 = create_task("Plan weekend trip to the mountains", status="pending", priority="low")
#
#     print("\nAll tasks:")
#     for task in get_all_tasks():
#         print(task.to_dict())
#
#     print("\nTask 1 details:")
#     print(get_task(task1.id).to_dict())
#
#     print("\nTasks with status 'pending':")
#     for task in get_tasks_by_status('pending'):
#         print(task.to_dict())
#
#     print("\nTasks due on 2025-06-17:")
#     for task in get_tasks_by_due_date('2025-06-17'):
#         print(task.to_dict())
#
#     print("\nUpdating Task 1 status to 'completed' and description:")
#     updated_task1 = update_task(task1.id, description="Bought groceries and cooked dinner", status="completed")
#     print(updated_task1.to_dict())
#
#     print("\nUpcoming reminders:")
#     # To test this, you might need to adjust system time or reminder_time values
#     for reminder in get_upcoming_reminders():
#         print(reminder.to_dict())
#
#     print("\nSemantic search for 'report':")
#     # This will currently match based on exact text returned by retrieve_context
#     # A more robust solution needs retrieve_context to return IDs.
#     for task in search_tasks_semantically('report'):
#         print(task.to_dict())
#
#     print("\nDeleting Task 4:")
#     if delete_task(task4.id):
#         print("Task 4 deleted successfully.")
#     else:
#         print("Failed to delete Task 4.")
#
#     print("\nAll tasks after deletion:")
#     for task in get_all_tasks():
#         print(task.to_dict())
