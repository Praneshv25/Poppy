#!/usr/bin/env python3
"""
TickTick MCP Server
A Model Context Protocol server for interacting with TickTick's API.
Supports retrieving and creating tasks.
"""

import asyncio
import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import time
from dotenv import load_dotenv
from ticktickToken import get_access_token
from task import Task

import requests
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp import types

# Load environment variables from .env file
load_dotenv()


class TickTickAPI:
    """TickTick API client for task management."""
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize TickTick API client.
        
        Args:
            access_token: OAuth2 access token for TickTick API
        """
        self.access_token = access_token or os.getenv("TICKTICK_ACCESS_TOKEN")
        self.base_url = "https://api.ticktick.com/open/v1"
        
        if not self.access_token:
            raise ValueError(
                "No access token provided. Set TICKTICK_ACCESS_TOKEN environment variable "
                "or pass access_token to constructor."
            )
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to TickTick API with automatic token refresh on 401."""
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=30
            )
            
            # If 401, try refreshing token once
            if response.status_code == 401:
                try:
                    self.access_token = get_access_token()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=data,
                        params=params,
                        timeout=30
                    )
                except Exception as refresh_error:
                    raise Exception(f"Token refresh failed: {str(refresh_error)}")
            
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            raise Exception(f"TickTick API request failed: {str(e)}")
    
    def get_tasks(
        self,
        project_id: str,
        completed: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve tasks for a specific project using /project/{id}/data.
        
        Args:
            project_id: Project ID whose tasks to fetch
            completed: Whether to include completed tasks
        
        Returns:
            List of task dictionaries
        """
        pdata = self.get_project_data(project_id)
        tasks = pdata.get("tasks", []) if isinstance(pdata, dict) else []
        if not completed and isinstance(tasks, list):
            tasks = [t for t in tasks if t.get("status", 0) != 2]
        return tasks if isinstance(tasks, list) else []
    
    def get_task_by_id(self, task_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific task by ID.
        
        Args:
            task_id: The task ID
        
        Returns:
            Task dictionary
        """
        endpoint = f"task/{task_id}"
        return self._make_request("GET", endpoint)
    
    def create_task(
        self,
        title: str,
        project_id: str,
        content: Optional[str] = None,
        due_date: Optional[str] = None,
        priority: int = 0,
        tags: Optional[List[str]] = None,
        all_day: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new task in TickTick.
        
        Args:
            title: Task title (required)
            project_id: Project to add task to (required)
            content: Task description/notes
            due_date: Due date in ISO format (e.g., "2025-10-15T10:00:00+0000")
            priority: Priority level (0=None, 1=Low, 3=Medium, 5=High)
            tags: List of tag names
            all_day: Whether the task is an all-day event
        
        Returns:
            Created task dictionary
        """
        task_data = {
            "title": title,
            "priority": priority,
            "allDay": all_day
        }
        
        if content:
            task_data["content"] = content
        
        # Always include projectId
        task_data["projectId"] = project_id
        
        if due_date:
            # Validate and format due date
            try:
                # Parse various date formats
                if 'T' in due_date:
                    dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromisoformat(due_date)
                task_data["dueDate"] = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
            except ValueError as e:
                raise ValueError(
                    f"Invalid due_date format: {str(e)}. "
                    "Use ISO 8601 format: YYYY-MM-DDTHH:MM:SS+0000"
                )
        
        if tags:
            task_data["tags"] = tags
        
        endpoint = "task"
        return self._make_request("POST", endpoint, data=task_data)
    
    def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        due_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing task.
        
        Args:
            task_id: Task ID to update
            title: New title
            content: New content
            status: Task status (0=active, 2=completed)
            priority: New priority level
            due_date: New due date
        
        Returns:
            Updated task dictionary
        """
        # First get the current task
        current_task = self.get_task_by_id(task_id)
        
        # Update only provided fields
        if title is not None:
            current_task["title"] = title
        if content is not None:
            current_task["content"] = content
        if status is not None:
            current_task["status"] = status
        if priority is not None:
            current_task["priority"] = priority
        if due_date is not None:
            if 'T' in due_date:
                dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(due_date)
            current_task["dueDate"] = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        
        endpoint = f"task/{task_id}"
        return self._make_request("POST", endpoint, data=current_task)
    
    def complete_task(self, task_id: str) -> Dict[str, Any]:
        """
        Mark a task as completed.
        
        Args:
            task_id: Task ID to complete
        
        Returns:
            Updated task dictionary
        """
        return self.update_task(task_id, status=2)
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """
        Retrieve all projects/lists.
        
        Returns:
            List of project dictionaries
        """
        endpoint = "project"
        result = self._make_request("GET", endpoint)
        return result if isinstance(result, list) else []

    def get_project_data(self, project_id: str) -> Dict[str, Any]:
        """
        Retrieve project with its tasks and columns.
        Uses GET /open/v1/project/{projectId}/data
        """
        endpoint = f"project/{project_id}/data"
        data = self._make_request("GET", endpoint)
        return data if isinstance(data, dict) else {}

    def get_all_open_projects_tasks(self, include_completed: bool = False) -> List[Dict[str, Any]]:
        """
        Aggregate tasks across all non-closed projects using project data API.

        Args:
            include_completed: Whether to include completed tasks

        Returns:
            Flat list of task dicts with injected project metadata (projectId, projectName)
        """
        tasks: List[Dict[str, Any]] = []
        projects = self.get_projects()
        for proj in projects:
            if proj.get("closed"):
                continue
            pid = proj.get("id")
            if not pid:
                continue
            pdata = self.get_project_data(pid)
            proj_tasks = pdata.get("tasks", []) if isinstance(pdata, dict) else []
            for t in proj_tasks:
                if not include_completed and t.get("status", 0) == 2:
                    continue
                # Ensure projectId; API returns it on tasks, but inject/override to be safe
                t["projectId"] = pid
                if "project" in pdata and isinstance(pdata["project"], dict):
                    t["projectName"] = pdata["project"].get("name")
                else:
                    t["projectName"] = proj.get("name")
                tasks.append(t)
        return tasks

    def get_all_projects_tasks(
        self,
        include_completed: bool = False,
        include_closed: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Aggregate tasks across all projects.

        Args:
            include_completed: Whether to include completed tasks
            include_closed: Whether to include closed projects as well

        Returns:
            Flat list of task dicts with injected project metadata
        """
        tasks: List[Dict[str, Any]] = []
        projects = self.get_projects()
        for proj in projects:
            if not include_closed and proj.get("closed"):
                continue
            pid = proj.get("id")
            if not pid:
                continue
            pdata = self.get_project_data(pid)
            proj_tasks = pdata.get("tasks", []) if isinstance(pdata, dict) else []
            for t in proj_tasks:
                if not include_completed and t.get("status", 0) == 2:
                    continue
                t["projectId"] = pid
                if "project" in pdata and isinstance(pdata["project"], dict):
                    t["projectName"] = pdata["project"].get("name")
                else:
                    t["projectName"] = proj.get("name")
                tasks.append(t)
        return tasks

    def get_all_projects_tasks_as_objects(
        self,
        include_completed: bool = False,
        include_closed: bool = True
    ) -> List[Task]:
        """
        Aggregate tasks across all projects and return as Task objects.
        
        Args:
            include_completed: Whether to include completed tasks
            include_closed: Whether to include closed projects
        
        Returns:
            List of Task objects
        """
        raw_tasks = self.get_all_projects_tasks(include_completed, include_closed)
        return [Task.from_dict(t) for t in raw_tasks]
    
    def get_tasks_as_objects(
        self,
        project_id: str,
        completed: bool = False
    ) -> List[Task]:
        """
        Retrieve tasks for a project and return as Task objects.
        
        Args:
            project_id: Project ID whose tasks to fetch
            completed: Whether to include completed tasks
        
        Returns:
            List of Task objects
        """
        raw_tasks = self.get_tasks(project_id, completed)
        return [Task.from_dict(t) for t in raw_tasks]


# Initialize the MCP server
app = Server("ticktick-mcp-server")

# Global TickTick API client (will be initialized with credentials)
ticktick_client: Optional[TickTickAPI] = None


def ensure_client_initialized() -> bool:
    """Attempt to initialize the global TickTick client if not yet initialized."""
    global ticktick_client
    if ticktick_client is not None:
        return True
    # Try environment variable
    access_token = os.getenv("TICKTICK_ACCESS_TOKEN")
    if not access_token:
        # Try helper (will use cache/refresh or interactive auth)
        try:
            access_token = get_access_token()
        except Exception as e:
            print(f"⚠️  Token helper failed: {e}", file=os.sys.stderr)
            access_token = None
    if access_token:
        try:
            ticktick_client = TickTickAPI(access_token)
            return True
        except Exception as e:
            print(f"⚠️  Failed to initialize TickTick client: {e}", file=os.sys.stderr)
    return False


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available TickTick tools."""
    return [
        types.Tool(
            name="get_tasks",
            description="Retrieve tasks from a specific project (requires project_id).",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project ID whose tasks to fetch"
                    },
                    "include_completed": {
                        "type": "boolean",
                        "description": "Whether to include completed tasks (default: false)"
                    }
                },
                "required": ["project_id"]
            }
        ),
        types.Tool(
            name="get_project_data",
            description="Retrieve project data (project, tasks, columns) for a given projectId",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project ID to fetch"
                    }
                },
                "required": ["project_id"]
            }
        ),
        types.Tool(
            name="get_all_tasks",
            description="Retrieve tasks across all projects. Optionally include completed and closed projects.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_completed": {
                        "type": "boolean",
                        "description": "Whether to include completed tasks (default: false)"
                    },
                    "include_closed": {
                        "type": "boolean",
                        "description": "Whether to include closed projects (default: true)"
                    }
                }
            }
        ),
        types.Tool(
            name="get_task_by_id",
            description="Retrieve a specific task by its ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to retrieve"
                    }
                },
                "required": ["task_id"]
            }
        ),
        types.Tool(
            name="create_task",
            description="Create a new task in TickTick with title, description, due date, priority, and tags",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title (required)"
                    },
                    "content": {
                        "type": "string",
                        "description": "Task description or notes"
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Project ID to add the task to"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in ISO 8601 format (e.g., '2025-10-15T10:00:00+0000')"
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority level: 0=None, 1=Low, 3=Medium, 5=High (default: 0)",
                        "enum": [0, 1, 3, 5]
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tag names"
                    },
                    "all_day": {
                        "type": "boolean",
                        "description": "Whether this is an all-day task (default: false)"
                    }
                },
                "required": ["title"]
            }
        ),
        types.Tool(
            name="update_task",
            description="Update an existing task's properties",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to update"
                    },
                    "title": {
                        "type": "string",
                        "description": "New task title"
                    },
                    "content": {
                        "type": "string",
                        "description": "New task content/description"
                    },
                    "status": {
                        "type": "integer",
                        "description": "Task status: 0=active, 2=completed",
                        "enum": [0, 2]
                    },
                    "priority": {
                        "type": "integer",
                        "description": "New priority level: 0=None, 1=Low, 3=Medium, 5=High",
                        "enum": [0, 1, 3, 5]
                    },
                    "due_date": {
                        "type": "string",
                        "description": "New due date in ISO format"
                    }
                },
                "required": ["task_id"]
            }
        ),
        types.Tool(
            name="complete_task",
            description="Mark a task as completed",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task ID to mark as completed"
                    }
                },
                "required": ["task_id"]
            }
        ),
        types.Tool(
            name="get_projects",
            description="Retrieve all projects/lists from TickTick",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    
    if not ticktick_client:
        if not ensure_client_initialized():
            return [types.TextContent(
                type="text",
                text=(
                    "Error: TickTick client not initialized. Either set TICKTICK_ACCESS_TOKEN "
                    "in the environment, or run the OAuth flow once (the server will open a browser) "
                    "to cache a token at ~/.config/meLlamo/ticktick_token.json."
                )
            )]
    
    try:
        if name == "get_tasks":
            project_id = arguments["project_id"]
            include_completed = arguments.get("include_completed", False)
            tasks = ticktick_client.get_tasks(
                project_id=project_id,
                completed=include_completed
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(tasks, indent=2)
            )]
        
        elif name == "get_task_by_id":
            task_id = arguments["task_id"]
            task = ticktick_client.get_task_by_id(task_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(task, indent=2)
            )]
        
        elif name == "get_project_data":
            project_id = arguments["project_id"]
            data = ticktick_client.get_project_data(project_id)
            return [types.TextContent(
                type="text",
                text=json.dumps(data, indent=2)
            )]

        elif name == "get_all_tasks":
            include_completed = arguments.get("include_completed", False)
            include_closed = arguments.get("include_closed", True)
            tasks = ticktick_client.get_all_projects_tasks(
                include_completed=include_completed,
                include_closed=include_closed
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(tasks, indent=2)
            )]
        
        elif name == "create_task":
            task = ticktick_client.create_task(
                title=arguments["title"],
                content=arguments.get("content"),
                project_id=arguments.get("project_id"),
                due_date=arguments.get("due_date"),
                priority=arguments.get("priority", 0),
                tags=arguments.get("tags"),
                all_day=arguments.get("all_day", False)
            )
            return [types.TextContent(
                type="text",
                text=f"✅ Task created successfully!\n\n{json.dumps(task, indent=2)}"
            )]
        
        elif name == "update_task":
            task = ticktick_client.update_task(
                task_id=arguments["task_id"],
                title=arguments.get("title"),
                content=arguments.get("content"),
                status=arguments.get("status"),
                priority=arguments.get("priority"),
                due_date=arguments.get("due_date")
            )
            return [types.TextContent(
                type="text",
                text=f"✅ Task updated successfully!\n\n{json.dumps(task, indent=2)}"
            )]
        
        elif name == "complete_task":
            task = ticktick_client.complete_task(arguments["task_id"])
            return [types.TextContent(
                type="text",
                text=f"✅ Task marked as completed!\n\n{json.dumps(task, indent=2)}"
            )]
        
        elif name == "get_projects":
            projects = ticktick_client.get_projects()
            return [types.TextContent(
                type="text",
                text=json.dumps(projects, indent=2)
            )]
        
        else:
            return [types.TextContent(
                type="text",
                text=f"❌ Unknown tool: {name}"
            )]
    
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Error executing {name}: {str(e)}"
        )]


async def main():
    """Main entry point for the MCP server."""
    global ticktick_client
    
    # Initialize TickTick client from environment variable or via token helper
    print("TOKEN_PRESENT", bool(os.getenv("TICKTICK_ACCESS_TOKEN")), file=os.sys.stderr)
    # Try to initialize now; if it fails, lazy init will be attempted on first tool call
    if ensure_client_initialized():
        print("✅ TickTick MCP Server initialized successfully", file=os.sys.stderr)
    else:
        print("⚠️  TickTick client not initialized yet; will attempt on first tool call.", file=os.sys.stderr)
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ticktick-mcp-server",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

