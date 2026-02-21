# Project Structure

This document describes the organized file structure of the meLlamo project.

## Directory Overview

```
meLlamo/
├── agents/                    # Robot agent scripts and controllers
├── config/                    # System prompts and configuration files
├── data/                      # Databases, models, and data files
├── docs/                      # Project documentation
├── finetuning/               # Model fine-tuning scripts and configs
├── localExperiments/         # Local experimental agents
├── search/                    # Search functionality module
├── tasks/                     # Task scheduling and management system
├── tests/                     # Test scripts
├── ticktick/                  # TickTick MCP server and API client
├── wakeWord/                  # Wake word detection module
├── venv/                      # Python virtual environment
├── requirements.txt           # Python dependencies
└── .env                       # Environment variables (not in git)
```

## Detailed Structure

### `/agents/` - Robot Agents and Controllers
Main agent scripts that interface with the robot and handle various functionalities:
- `libra.py` - Main Libra agent with full capabilities
- `libraCLI.py` - CLI version of Libra agent
- `speedDemon.py` - Speed Demon agent (optimized for faster responses)
- `speedDemonCLI.py` - CLI version of Speed Demon agent
- `humanCentering.py` - Face detection and human tracking
- `voice.py` - Voice synthesis and audio output
- `ServoController.py` - Hardware servo control interface
- `robot_actions.py` - Robot action translation and execution

### `/config/` - Configuration Files
System prompts and configuration files:
- `libra_system_prompt.txt` - System prompt for Libra agent
- `libra_speed_demon_sys_prompt.txt` - Modified prompt for CLI version
- `speedDemon_system_prompt.txt` - System prompt for Speed Demon agent
- `scheduled_action_system_prompt.txt` - Prompt for scheduled action execution

### `/data/` - Data Storage
Persistent data, databases, and models:
- `pvelsDB.chroma/` - ChromaDB vector database for context storage
- `meLlamo-expert-robot-v1/` - Fine-tuned model adapter
- `frame.jpg` - Captured camera frame
- `orange.log` - Application log file

### `/docs/` - Documentation
Project documentation and guides:
- `PROJECT_STRUCTURE.md` - This file
- `SETUP_SUMMARY.md` - Initial setup and configuration guide
- `SCHEDULED_ACTIONS_README.md` - Scheduled actions system documentation
- `RECURRING_TASKS_SUMMARY.md` - Recurring tasks implementation guide
- `TICKTICK_MCP_README.md` - TickTick MCP server documentation

### `/finetuning/` - Model Fine-tuning
Scripts and data for fine-tuning language models:
- `dataset.jsonl` - Training dataset
- `dataset.py` - Dataset preparation script
- `leChat.py` - Fine-tuning script
- `mergeModel.py` - LoRA adapter merging script
- `config.yml` - Fine-tuning configuration

### `/localExperiments/` - Experimental Agents
Experimental versions using different models:
- `pices.py` - Agent using GGUF models
- `scorpio.py` - Agent with alternative model configuration
- `bot.gguf` - Local GGUF model file
- System prompts for experimental agents

### `/search/` - Search Module
Web search and information retrieval:
- `search.py` - Search implementation
- `search_sys_prompt.txt` - Search agent system prompt

### `/tasks/` - Task Management System
Comprehensive task scheduling and execution system:
- `scheduled_actions_v2.py` - Database operations for scheduled actions
- `scheduler_v2.py` - Background scheduler
- `action_executor_v2.py` - Action execution engine
- `command_parser.py` - Natural language command parsing
- `schedule_cli.py` - CLI for managing scheduled actions
- `task_manager.py` - Task database manager
- `vector.py` - Vector database utilities
- `tasks.db` - SQLite database for tasks
- `check_scheduled_actions.py` - Utility to view/manage actions
- `migrate_database.py` - Database migration script

### `/ticktick/` - TickTick MCP Server
TickTick task management integration via Model Context Protocol:
- `ticktick_mcp_server.py` - MCP server with task CRUD tools
- `ticktickToken.py` - OAuth2 authentication and token management
- `task.py` - Task data class wrapper for TickTick API responses

### `/tests/` - Test Scripts
Test scripts for various components:
- `test_scheduler.py` - Tests for the scheduler system
- `test_recurring.py` - Tests for recurring tasks
- `testMovement.py` - Hardware movement tests

### `/wakeWord/` - Wake Word Detection
Voice activation and wake word detection:
- `wake.py` - Wake word detection implementation
- Model files for "Heimdell" and "Mister Carson" wake words

## Import Path Updates

After the reorganization, import paths have been updated throughout the codebase:

### Module Imports
- `ServoController` → `agents.ServoController`
- `robot_actions` → `agents.robot_actions`
- `voice` → `agents.voice`
- `humanCentering` → `agents.humanCentering`
- `ticktickToken` → `ticktick.ticktickToken`
- `task` (TickTick) → `ticktick.task`

### File Path Updates
- System prompts → `config/[prompt_name].txt`
- Database → `data/pvelsDB.chroma`
- Model → `data/meLlamo-expert-robot-v1`
- Log file → `data/orange.log`

## Running the Project

### Main Agents
```bash
# From project root
python -m agents.libra          # Full Libra agent
python -m agents.libraCLI       # CLI Libra agent
python -m agents.speedDemon     # Speed Demon agent
python -m agents.speedDemonCLI  # CLI Speed Demon agent
```

### Task Management
```bash
# View scheduled actions
python -m tasks.check_scheduled_actions

# Schedule actions via CLI
python -m tasks.schedule_cli
```

### Tests
```bash
# Run tests
python -m tests.test_scheduler
python -m tests.test_recurring
python -m tests.testMovement
```

## Notes

- The project root remains the working directory for all scripts
- All file paths are relative to the project root
- The `venv/` virtual environment should be activated before running any scripts
- The `.env` file contains sensitive configuration (not tracked by git)
- Database files in `data/` and `tasks/` are tracked by git but may contain local state

