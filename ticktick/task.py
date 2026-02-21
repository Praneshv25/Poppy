"""
Task class wrapper for TickTick API responses.
Provides filtering, sorting, and utility methods.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class Task:
    """Task wrapper class with filtering and utility methods."""
    id: str
    title: str
    project_id: str
    project_name: str
    status: int = 0
    priority: int = 0
    content: str = ""
    desc: str = ""
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    time_zone: str = "UTC"
    is_all_day: bool = False
    repeat_flag: Optional[str] = None
    tags: List[str] = None
    column_id: Optional[str] = None
    etag: Optional[str] = None
    kind: str = "TEXT"
    sort_order: Optional[int] = None
    completed_time: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Task":
        """Create Task from API response dictionary."""
        return Task(
            id=data.get("id", ""),
            title=data.get("title", ""),
            project_id=data.get("projectId", ""),
            project_name=data.get("projectName", ""),
            status=data.get("status", 0),
            priority=data.get("priority", 0),
            content=data.get("content", ""),
            desc=data.get("desc", ""),
            start_date=data.get("startDate"),
            due_date=data.get("dueDate"),
            time_zone=data.get("timeZone", "UTC"),
            is_all_day=data.get("isAllDay", False),
            repeat_flag=data.get("repeatFlag"),
            tags=data.get("tags", []),
            column_id=data.get("columnId"),
            etag=data.get("etag"),
            kind=data.get("kind", "TEXT"),
            sort_order=data.get("sortOrder"),
            completed_time=data.get("completedTime")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Task to dictionary (camelCase for API compatibility)."""
        return {
            "id": self.id,
            "title": self.title,
            "projectId": self.project_id,
            "projectName": self.project_name,
            "status": self.status,
            "priority": self.priority,
            "content": self.content,
            "desc": self.desc,
            "startDate": self.start_date,
            "dueDate": self.due_date,
            "timeZone": self.time_zone,
            "isAllDay": self.is_all_day,
            "repeatFlag": self.repeat_flag,
            "tags": self.tags,
            "columnId": self.column_id,
            "etag": self.etag,
            "kind": self.kind,
            "sortOrder": self.sort_order,
            "completedTime": self.completed_time
        }
    
    def is_overdue(self) -> bool:
        """Check if task is overdue (past due date and not completed)."""
        if self.status == 2:
            return False
        if not self.due_date:
            return False
        try:
            due = datetime.fromisoformat(self.due_date.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            return now > due
        except (ValueError, AttributeError):
            return False
    
    def matches_filters(
        self,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        project_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_overdue: Optional[bool] = None
    ) -> bool:
        """Check if task matches given filters."""
        if status is not None and self.status != status:
            return False
        if priority is not None and self.priority != priority:
            return False
        if project_id is not None and self.project_id != project_id:
            return False
        if tags is not None:
            if not any(tag in self.tags for tag in tags):
                return False
        if is_overdue is not None and self.is_overdue() != is_overdue:
            return False
        return True
    
    @staticmethod
    def sort_by_start_date(tasks: List["Task"], reverse: bool = False) -> List["Task"]:
        """Sort tasks by start_date. Tasks without start_date appear last."""
        def sort_key(task: Task):
            if not task.start_date:
                return (1, "")
            return (0, task.start_date)
        return sorted(tasks, key=sort_key, reverse=reverse)
    
    @staticmethod
    def sort_by_due_date(tasks: List["Task"], reverse: bool = False) -> List["Task"]:
        """Sort tasks by due_date. Tasks without due_date appear last."""
        def sort_key(task: Task):
            if not task.due_date:
                return (1, "")
            return (0, task.due_date)
        return sorted(tasks, key=sort_key, reverse=reverse)
    
    @staticmethod
    def sort_by_priority(tasks: List["Task"], reverse: bool = True) -> List["Task"]:
        """Sort tasks by priority (default: high to low)."""
        return sorted(tasks, key=lambda t: t.priority, reverse=reverse)
