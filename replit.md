# D&D AI Dungeon Master - Replit Project

## Overview
This project is an interactive, turn-based Dungeons & Dragons session runner powered by OpenAI agents. It simulates a Dungeon Master (DM) that can manage lore, campaign memory, and gameplay mechanics, allowing players to experience dynamic storytelling and game logic. The project aims to provide a dynamic and personalized D&D experience, enabling rich, immersive campaigns with AI assistance.

## User Preferences
- **Deployment**: VM target (for persistent storage and long-running sessions)
- **Port**: 5000 (web interface)
- **Storage**: Local file system for campaign persistence
- **Security**: Environment variables for API key management

## System Architecture
The system is built around a multi-agent orchestration pattern, featuring specialized AI agents for different aspects of gameplay.

### UI/UX Decisions
- **Character Management Panel**: Right-side slide-over panel for character management, accessible from Play Mode header.
- **Character Cards**: Two-column grid displaying Name, Class, Level, Race, and HP, with checkbox selection for live characters.
- **Party Display**: Live party displayed below the session card, showing selected characters with HP and level.
- **Loading Overlays**: Visual feedback for long-running operations (e.g., session closing, character import).
- **Banner System**: Pixel-perfect automated banner gradient generator for seamless header design.
- **Voice Output UI**: Opt-in play buttons on DM messages for TTS playback with real-time state syncing.
- **Voice Input UI**: Microphone button with pulsing animation for listening state and interim transcription display.

### Technical Implementations
- **Multi-Agent DM System**: A router agent classifies player input and dispatches to specialized agents (e.g., Narrative, Q&A Situation, Q&A Rules, Travel, Gameplay) for focused responses. Each specialist has access to relevant tools like lore, memory, and dice. This system uses `gpt-4o-mini` for cost efficiency.
- **Character Management**:
    - **D&D Beyond Integration**: Imports character data from D&D Beyond API, storing full JSON in a PostgreSQL database (`characters` table with JSONB column). Supports refreshing character data.
    - **PDF Character Import**: Parses D&D Beyond PDF character sheets using `pypdf` to extract character details and store them in the same database structure as D&D Beyond imports.
    - **Persistence**: Characters are stored in a PostgreSQL database and can be selected for active sessions.
- **Voice Input/Output (TTS/STT)**:
    - **TTS**: OpenAI TTS (`tts-1` model, `fable` voice) for DM narration, accessible via `/api/tts` endpoint. Speakable intents are configurable.
    - **STT**: Web Speech API integration for browser-native speech-to-text, allowing players to speak commands.
- **Session Management**: Automated session generation, including campaign outline substitution and post-session analysis. Uses `gpt-4o` for reliable JSON output during session planning.
- **Core AI Framework**: Utilizes OpenAI Agents SDK.
- **Web Framework**: Starlette/FastAPI for the backend web interface.
- **Asynchronous Operations**: `asyncio` for concurrent session handling.
- **Data Validation**: Pydantic for robust data models.

### Feature Specifications
- **Interactive D&D Sessions**: AI-driven DM manages turn-based gameplay, lore, and campaign memory.
- **Character Import**: Supports importing characters from D&D Beyond via URL/ID and by uploading D&D Beyond formatted PDF character sheets.
- **Voice Interaction**: Optional voice input (STT) for player commands and voice output (TTS) for DM narration.
- **Persistent Storage**: Campaigns, sessions, and character data are persisted, with character data stored in PostgreSQL.
- **Lore and Memory**: Utilizes OpenAI vector stores for semantic search of game lore and campaign-specific memories.
- **Dice Rolling**: Integrated dice rolling mechanics for gameplay resolution.
- **Extensible Architecture**: Designed for easy integration of new agents, tools, and prompts.

### System Design Choices
- **Directory Structure**:
    - `src/`: Main application code.
        - `game_engine.py`: Core game logic, campaign/session management, AI agents, and utility functions.
        - `library/`: Reusable modules (vectorstores, eval logging, session review).
        - `orchestration/`: Multi-agent router system for specialized DM responses.
        - `characters.py`: Character management (D&D Beyond import, PDF parsing).
        - `voice.py`: TTS/STT voice capabilities.
    - `config/`: Configuration files.
    - `mirror/`: Persistent local storage for campaigns, sessions, and memory.
    - `prompts/`: System prompts for AI agents.
    - `tests/unit/`: Unit tests for core game engine functions.
    - `run_server.py`: Web server entry point (Starlette/Uvicorn).
- **Environment Variables**: For sensitive configurations like OpenAI API keys.

### Recent Changes
- **December 2025**: Added Combat Readiness System (`src/library/combat_readiness.py`). Automatically evaluates combat plan validity after each turn based on NPCs present and hostile environment flag. Updates or clears combat plans as scene changes. Narrative and travel agents now set `hostile_environment` flag. 21 unit tests added.
- **December 2025**: Added retry logic for transient LLM failures (`src/library/retry.py`). Uses exponential backoff (1s→2s→4s, max 8s) with automatic retries for rate limits, timeouts, and server errors. All 6 `Runner.run` call sites wrapped. 23 unit tests added.
- **December 2025**: Added JSON Response Validation using OpenAI Structured Outputs. Router agent now uses `output_type=RouterIntent` for guaranteed valid JSON responses. Schema warmup routine pre-caches schemas at server startup to avoid first-request latency. Response models defined in `src/library/response_models.py`.
- **December 2025**: Added Token Budget Framework (`src/library/token_budget.py`) with per-agent context size limits (1K-8K tokens) using tiktoken. Enforced in `build_agent_context()` with automatic trimming and logging. Environment variable overrides available (e.g., `TOKEN_BUDGET_ROUTER=500`).
- **December 2025**: Consolidated `main.py` into `game_engine.py` - all game logic, utility functions, and models now live in `game_engine.py`. The legacy console runner (`main.py`) was deprecated and removed.

### Testing
- **Standards Document**: See `tests/TESTING.md` for complete testing standards and guidelines
- **Test Framework**: pytest with pytest-asyncio, pythonpath configured in `pyproject.toml`
- **Test Structure**: Unit tests under `tests/unit/` with logical grouping by functionality
- **Test Modules**:
    - `test_dice.py`: Dice rolling mechanics (roll_impl function)
    - `test_helpers.py`: Helper functions (merge_scene_patch, extract_update_payload, strip_json_block, clip_recap)
    - `test_memory.py`: Memory store operations (get_campaign_mem_store, upsert_memory_writes)
    - `test_models.py`: Pydantic model serialization (SceneState)
    - `test_narrative.py`: Narrative extraction (extract_narrative_from_runresult)
    - `test_orchestration.py`: Multi-agent routing (orchestrate_turn, build_agent_context)
    - `test_sessions.py`: Session lifecycle (load_session, list_sessions, get_active_session, close_session)
    - `test_campaigns.py`: Campaign management (load_campaign, list_campaigns, update_last_played)
    - `test_config.py`: Configuration and logging (get_available_worlds, jl_write)
    - `test_token_budget.py`: Token budget framework (count_tokens, trim_to_budget, enforce_budget)
    - `test_response_models.py`: Pydantic response models (RouterIntent, ScenePatch, MemoryWrite, DiceRollResult)
    - `test_retry.py`: Retry logic for transient LLM failures (run_with_retry, is_transient_error, exponential backoff)
    - `test_combat_readiness.py`: Combat plan validity checker (check_combat_plan_validity, get_npc_set, should_prepare_combat)
- **Design Decisions**:
    - Tests document actual game engine behavior (not theoretical specs)
    - Every test has a one-sentence docstring with function name and summary
    - Unit tests are deterministic; LLM calls are mocked
    - `extract_update_payload` requires markdown-fenced JSON (bare JSON returns None)
    - Multiple JSON blocks: extracts the last block (design choice)

## External Dependencies
- **OpenAI API**: Used for AI agents (DM responses, specialized agents), vector databases (lore, campaign memory), and Text-to-Speech (TTS). Requires `OPENAI_API_KEY_AGENT` and `OPENAI_API_KEY_VDB`.
- **PostgreSQL**: Primary database for storing character information, including full D&D Beyond JSON data.
- **D&D Beyond API**: For importing public character data directly from D&D Beyond.
- **`pypdf` library**: Used for parsing PDF character sheets for import.
- **Web Speech API**: Browser-native API used for Speech-to-Text (STT) functionality in the frontend.
- **Pillow (PIL Fork)**: Used for automated banner gradient generation in the UI.