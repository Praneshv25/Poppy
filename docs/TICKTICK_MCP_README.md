# TickTick MCP Server

A Model Context Protocol (MCP) server that provides integration with TickTick's task management API.

## Features

- ✅ **Retrieve Tasks** - Get all tasks or filter by project
- ✅ **Get Task Details** - Retrieve a specific task by ID
- ✅ **Create Tasks** - Create new tasks with title, description, due dates, priority, and tags
- ✅ **Update Tasks** - Modify existing tasks
- ✅ **Complete Tasks** - Mark tasks as done via dedicated complete endpoint
- ✅ **Delete Tasks** - Remove tasks by project and task ID
- ✅ **Get Projects** - List all your TickTick projects/lists

## Installation

### 1. Install Dependencies

```bash
cd /Users/PV/PycharmProjects/Poppy
pip install -r requirements.txt
```

Or install the MCP package separately:

```bash
pip install mcp
```

### 2. Get TickTick API Access Token

TickTick uses OAuth 2.0 for authentication. Here's how to get your access token:

#### Option A: Using TickTick Developer Portal (Recommended for Apps)

1. Go to [TickTick Developer Portal](https://developer.ticktick.com)
2. Register a new application
3. Get your `client_id` and `client_secret`
4. Implement OAuth 2.0 flow to get access token

#### Option B: Using Browser Developer Tools (Quick Setup)

1. Log in to [TickTick Web App](https://ticktick.com)
2. Open Browser Developer Tools (F12)
3. Go to **Application** → **Local Storage** → `ticktick.com`
4. Find the `token` or `access_token` value
5. Copy this token

**Note:** Tokens obtained this way may expire. For production use, implement proper OAuth 2.0.

### 3. Set Environment Variable

```bash
export TICKTICK_ACCESS_TOKEN="your_access_token_here"
```

Or create a `.env` file:

```bash
echo 'TICKTICK_ACCESS_TOKEN=your_access_token_here' > .env
```

## Usage

### Running the Server Standalone

```bash
python -m ticktick.ticktick_mcp_server
```

### Configuring with Claude Desktop

Add to your MCP configuration file (`~/.config/claude/config.json` on macOS/Linux):

```json
{
  "mcpServers": {
    "ticktick": {
      "command": "python",
      "args": ["-m", "ticktick.ticktick_mcp_server"],
      "cwd": "/Users/PV/PycharmProjects/Poppy",
      "env": {
        "TICKTICK_ACCESS_TOKEN": "your_access_token_here"
      }
    }
  }
}
```

### Configuring with Other MCP Clients

The server communicates over stdio, so any MCP client can connect to it by running the Python script and communicating via stdin/stdout.

## Available Tools

### 1. `get_tasks`

Retrieve tasks from TickTick.

**Parameters:**
- `project_id` (optional, string): Filter tasks by project ID
- `include_completed` (optional, boolean): Include completed tasks (default: false)

**Example:**
```json
{
  "project_id": "inbox123",
  "include_completed": false
}
```

**Response:** JSON array of task objects

---

### 2. `get_all_tasks`

Retrieve tasks across all projects.

**Parameters:**
- `include_completed` (optional, boolean): Include completed tasks (default: false)
- `include_closed` (optional, boolean): Include closed projects (default: true)

**Example:**
```json
{
  "include_completed": false,
  "include_closed": true
}
```

**Response:** JSON array of task objects with project metadata

---

### 3. `create_task`

Create a new task.

**Parameters:**
- `title` (required, string): Task title
- `content` (optional, string): Task description
- `project_id` (optional, string): Project to add task to
- `due_date` (optional, string): ISO 8601 format (e.g., "2025-10-15T10:00:00+0000")
- `priority` (optional, integer): 0=None, 1=Low, 3=Medium, 5=High (default: 0)
- `tags` (optional, array of strings): Tag names
- `all_day` (optional, boolean): All-day task (default: false)

**Example:**
```json
{
  "title": "Complete project proposal",
  "content": "Draft and review the Q4 project proposal",
  "due_date": "2025-10-15T17:00:00+0000",
  "priority": 5,
  "tags": ["work", "urgent"],
  "all_day": false
}
```

**Response:** Created task object with ID

---

### 4. `update_task`

Update an existing task.

**Parameters:**
- `project_id` (required, string): Project ID that owns the task
- `task_id` (required, string): Task ID to update
- `title` (optional, string): New title
- `content` (optional, string): New content
- `status` (optional, integer): 0=active, 2=completed
- `priority` (optional, integer): 0, 1, 3, or 5
- `due_date` (optional, string): New due date

**Example:**
```json
{
  "project_id": "inbox123",
  "task_id": "63f8a1234567890abcdef123",
  "priority": 5,
  "content": "Updated description with more details"
}
```

**Response:** Updated task object

---

### 5. `delete_task`

Delete a task by its ID.

**Parameters:**
- `project_id` (required, string): Project ID that owns the task
- `task_id` (required, string): Task ID to delete

**Example:**
```json
{
  "project_id": "inbox123",
  "task_id": "63f8a1234567890abcdef123"
}
```

**Response:** Empty response on success

---

### 6. `complete_task`

Mark a task as completed using the dedicated complete endpoint.

**Parameters:**
- `project_id` (required, string): Project ID that owns the task
- `task_id` (required, string): Task ID to complete

**Example:**
```json
{
  "project_id": "inbox123",
  "task_id": "63f8a1234567890abcdef123"
}
```

**Response:** Completed task object

---

### 7. `get_projects`

Get all projects/lists.

**Parameters:** None

**Response:** JSON array of project objects

---

## Example Usage with Claude

Once configured, you can ask Claude:

> "Show me all my TickTick tasks"

> "Create a task called 'Buy groceries' due tomorrow at 5pm with high priority"

> "Mark task ID 63f8a123... as completed"

> "List all my TickTick projects"

## TickTick API Documentation

- [Official API Docs](https://developer.ticktick.com/api)
- [Authentication Guide](https://developer.ticktick.com/docs#/openapi?id=authentication)

## Task Object Structure

A typical TickTick task object includes:

```json
{
  "id": "63f8a1234567890abcdef123",
  "projectId": "inbox123",
  "title": "Task Title",
  "content": "Task description",
  "priority": 0,
  "status": 0,
  "dueDate": "2025-10-15T10:00:00+0000",
  "tags": ["tag1", "tag2"],
  "allDay": false,
  "createdTime": "2025-10-01T08:00:00+0000",
  "modifiedTime": "2025-10-01T08:30:00+0000"
}
```

## Troubleshooting

### "Error: TickTick client not initialized"

- Ensure `TICKTICK_ACCESS_TOKEN` environment variable is set
- Verify the token is valid and not expired

### "TickTick API request failed: 401"

- Your access token is invalid or expired
- Get a new token from TickTick

### "TickTick API request failed: 403"

- Your app doesn't have permission for this operation
- Check your OAuth scopes if using developer app

### Invalid Date Format Errors

- Use ISO 8601 format: `YYYY-MM-DDTHH:MM:SS+0000`
- Example: `2025-12-25T14:30:00+0000`

## Security Notes

⚠️ **Important:**
- Keep your access token secure
- Don't commit tokens to version control
- Use environment variables or secure secret management
- Tokens can expire - implement refresh logic for production use

## Development

To modify or extend the server:

1. Edit `ticktick/ticktick_mcp_server.py`
2. The server uses the official `mcp` Python SDK
3. All tools are async and communicate via stdio
4. Add new tools by:
   - Adding methods to `TickTickAPI` class
   - Registering them in `handle_list_tools()`
   - Implementing handlers in `handle_call_tool()`

## License

MIT License - feel free to modify and use as needed.

