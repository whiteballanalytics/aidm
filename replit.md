# D&D AI Dungeon Master - Replit Project

## Overview
This project is an interactive, turn-based Dungeons & Dragons session runner powered by OpenAI agents. It simulates a Dungeon Master (DM) that can manage lore, campaign memory, and gameplay mechanics, allowing players to experience dynamic storytelling and game logic.

**Status**: ✅ Ready for use (requires OpenAI API key configuration)

## Recent Changes

### October 4, 2025 - Session Generation System
- ✅ Fixed campaign outline template substitution in session planning
  - Modified `setup_agents_for_campaign()` to accept `campaign_outline` parameter
  - Implemented `{campaign-outline}` placeholder replacement in `dm_new_session.md` prompt
  - Updated `create_session()` and `generate_post_session_analysis()` to pass campaign outline
- ✅ Switched `dm_new_session_agent` back to GPT-4o (from GPT-5) for more reliable JSON output
- ⚠️ Known issue: Session plan JSON extraction needs improvement (agent returns text without JSON blocks)

### September 21, 2025 - Initial Setup
- ✅ Imported GitHub repository and configured for Replit environment
- ✅ Installed Python 3.11 and all required dependencies
- ✅ Created missing configuration structure (config/, mirror/ directories)
- ✅ Set up web interface wrapper for the console application
- ✅ Configured workflow to run on port 5000 with web preview
- ✅ Set up deployment configuration for VM target (persistent storage)
- ⚠️ OpenAI API key configuration required for full functionality

## Project Architecture

### Core Components
- **Backend**: Python-based AI agents using OpenAI's API
- **Frontend**: Simple web interface wrapping the console application
- **Storage**: Local file system for campaigns, sessions, and memory
- **Vector Stores**: OpenAI vector stores for lore and campaign memory

### Directory Structure
```
├── src/                    # Main application code
│   ├── main.py            # Core D&D session runner
│   └── library/           # Support modules
├── config/                # Configuration files
├── mirror/                # Persistent storage
│   ├── campaigns/         # Campaign outlines
│   ├── sessions/          # Session logs
│   └── mem_mirror/        # Memory mirrors
├── prompts/               # System prompts for agents
├── run_server.py          # Web interface wrapper
└── requirements.txt       # Python dependencies
```

## Configuration Required

### 1. OpenAI API Keys
The application requires OpenAI API keys to function. Set these environment variables:
- `OPENAI_API_KEY_AGENT` - For agent requests
- `OPENAI_API_KEY_VDB` - For vector database searches (can be same as above)

### 2. Vector Stores (Optional)
- Configure world lore in `config/vectorstores.json`
- Campaign memory is created automatically in `config/memorystores.json`

## User Preferences
- **Deployment**: VM target (for persistent storage and long-running sessions)
- **Port**: 5000 (web interface)
- **Storage**: Local file system for campaign persistence
- **Security**: Environment variables for API key management

## Usage
1. **Development**: The workflow "DnD Server" is configured and running
2. **Web Interface**: Access through the preview pane (port 5000)
3. **Configuration**: Set OpenAI API keys through Replit's secrets manager
4. **Deployment**: Ready for publishing with VM deployment target

## Features
- Turn-based D&D sessions with AI-driven Dungeon Master
- Lore and memory search using vector stores
- Dice rolling for game mechanics
- Session and campaign management with persistent storage
- Web interface for user-friendly interaction
- Extensible agent architecture for new tools and prompts

## Technical Notes
- Uses OpenAI Agents SDK for AI functionality
- Starlette/FastAPI for web framework
- Asyncio for handling concurrent sessions
- Pydantic for data validation
- Vector stores for semantic search of game content