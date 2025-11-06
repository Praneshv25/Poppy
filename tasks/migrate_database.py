#!/usr/bin/env python3
"""
Database migration script to add recurring task columns
"""
import sqlite3
import os

DATABASE_DIR = 'tasks'
DATABASE_NAME = os.path.join(DATABASE_DIR, 'tasks.db')

def migrate_database():
    """Add recurring columns to existing database"""
    print("=" * 60)
    print("DATABASE MIGRATION: Adding Recurring Task Support")
    print("=" * 60)
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(scheduled_actions)")
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"\nExisting columns: {columns}")
    
    # Add recurring column if it doesn't exist
    if 'recurring' not in columns:
        print("\n➕ Adding 'recurring' column...")
        cursor.execute("ALTER TABLE scheduled_actions ADD COLUMN recurring INTEGER DEFAULT 0")
        print("✅ Added 'recurring'")
    else:
        print("\n✓ Column 'recurring' already exists")
    
    # Add recurring_interval_seconds column if it doesn't exist
    if 'recurring_interval_seconds' not in columns:
        print("➕ Adding 'recurring_interval_seconds' column...")
        cursor.execute("ALTER TABLE scheduled_actions ADD COLUMN recurring_interval_seconds INTEGER")
        print("✅ Added 'recurring_interval_seconds'")
    else:
        print("✓ Column 'recurring_interval_seconds' already exists")
    
    # Add recurring_until column if it doesn't exist
    if 'recurring_until' not in columns:
        print("➕ Adding 'recurring_until' column...")
        cursor.execute("ALTER TABLE scheduled_actions ADD COLUMN recurring_until TEXT")
        print("✅ Added 'recurring_until'")
    else:
        print("✓ Column 'recurring_until' already exists")
    
    # Add parent_recurring_id column if it doesn't exist
    if 'parent_recurring_id' not in columns:
        print("➕ Adding 'parent_recurring_id' column...")
        cursor.execute("ALTER TABLE scheduled_actions ADD COLUMN parent_recurring_id INTEGER")
        print("✅ Added 'parent_recurring_id'")
    else:
        print("✓ Column 'parent_recurring_id' already exists")
    
    conn.commit()
    
    # Verify migration
    cursor.execute("PRAGMA table_info(scheduled_actions)")
    columns = [col[1] for col in cursor.fetchall()]
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE!")
    print("=" * 60)
    print(f"\nFinal columns: {columns}")
    
    conn.close()
    
    print("\n✅ Database ready for recurring tasks!")

if __name__ == "__main__":
    migrate_database()

