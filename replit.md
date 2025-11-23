# D&D AI Dungeon Master - Replit Project

## Overview
This project is an interactive, turn-based Dungeons & Dragons session runner powered by OpenAI agents. It simulates a Dungeon Master (DM) that can manage lore, campaign memory, and gameplay mechanics, allowing players to experience dynamic storytelling and game logic.

**Status**: ✅ Ready for use (requires OpenAI API key configuration)

## Recent Changes

### November 23, 2025 - Pixel-Perfect Banner Bridge System
- ✅ Created automated banner gradient generator using Pillow
  - Extracts full edge columns from banner images (1024px height)
  - Generates 100px wide bridge PNG with pixel-perfect interpolation
  - Preserves vertical color variation row-by-row for seamless transitions
  - Handles transparency compositing on dark background (#080B10)
- ✅ Implemented pixel-perfect header design
  - Left banner positioned at left edge, auto-sized to header height
  - Right banner positioned at right edge, auto-sized to header height
  - Bridge image stretched across full header width with `background-size: 100% 100%`
  - No visible seams or color jumps between banners and bridge
- ✅ Created regeneration workflow in `scripts/generate_banner_gradient.py`
  - Script outputs `static/images/ui/banner_bridge.png`
  - Documented in `scripts/README.md` for future banner updates
- ✅ Architect-reviewed and validated for pixel-perfect quality

### November 23, 2025 - Multi-Agent DM System Complete
- ✅ Implemented router-based multi-agent orchestration for DM responses
  - Created 7 specialized agents with distinct roles:
    - **Router Agent**: Classifies player input intent and routes to appropriate specialist
    - **Narrative Short Agent**: Provides 1-2 sentence descriptions for routine actions
    - **Narrative Long Agent**: Provides 2-5 paragraph rich descriptions for significant moments
    - **Q&A Situation Agent**: Answers questions about environment, NPCs, and spatial details
    - **Q&A Rules Agent**: Answers D&D 5e rules questions using searchLore
    - **Travel Agent**: Resolves movement and journey mechanics
    - **Gameplay Agent**: Adjudicates dice rolls and action resolution
  - Each specialist has appropriate tool access (lore, memory, dice) for their role
  - Single-hop architecture: Router → Specialist → Response (no agent chaining)
- ✅ Created orchestration layer in `src/orchestration/turn_router.py`
  - Handles router classification and specialist dispatch
  - Merges specialist responses with session state updates
  - Robust JSON parsing (bare JSON first, then fenced blocks)
  - Detailed logging for routing decisions and debugging
- ✅ Feature flag integration with backwards compatibility
  - `USE_MULTI_AGENT_DM` environment variable enables/disables multi-agent system
  - Defaults to disabled (false) for backwards compatibility
  - Legacy single-agent path preserved when disabled
- ✅ All 7 prompts created in `prompts/system/` directory
- ✅ All agents use `gpt-4o-mini` model for cost efficiency
- ✅ Architect-reviewed and validated implementation

### October 4, 2025 - Session Generation System Complete
- ✅ Fixed campaign outline template substitution in session planning
  - Modified `setup_agents_for_campaign()` to accept `campaign_outline` parameter
  - Implemented `{campaign-outline}` placeholder replacement in `dm_new_session.md` prompt
  - Updated `create_session()` and `generate_post_session_analysis()` to pass campaign outline
- ✅ Fixed session plan extraction and validation
  - Corrected result extraction to use `RunResult.final_output` attribute
  - Fixed session_plan assignment (extracted JSON IS the plan, not nested under a key)
  - Added validation that raises errors when required keys are missing
  - Prevents empty session plans from being saved to disk
- ✅ Switched `dm_new_session_agent` to GPT-4o for reliable JSON output
- ✅ All tests passing: sessions created with fully populated plans

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