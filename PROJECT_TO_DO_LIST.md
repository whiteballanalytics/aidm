# D&D AI Dungeon Master - List of potential next steps for the project

**Date**: December 2025  

---

## New Work

### Minor UX Features
Features that almost exclusively involve minor changes to the UI with a small amount of associated backend functionality.

- **Delete campaign:** Either complete delete a campaign from local data within the Campaign Builder window or somehow archive it so that it is no longer visible to the user.
- **Better JSON reader:** For the "View details (DM Only)" buttons on the Campaign Builder and Session Manager windows, improve the interface so that the JSON is easier to navigate and extends to a deeper level. Also make sure that the one on the Session Manager tab opens with the same width as the one on Campaign Builder.
- **Dim brightness in World Review:** The colour scheme for the text field where the user can see World descriptions on the Campaing Builder tab is great. But as soon as a user selects a world it goes bright white, which we don't want.
- **Improve progress hold sign:** When the web app is doing a task and wants to freeze the experience for the user, usually while it is waiting for LLM API calls to complete, the text is a bit hard to read at the moment. We could improve this, maybe even provide an interesting DnD-related animation, such as a bubbling potion.
- **Improve "Close Session" message:** Improve the warning message that shows when a user clicks "Close Session" on the Session Manager tab. It should explain, very concisely, the implications of closing a session to the user - i.e. that they will no longer be able to return and progress play, they will need to start a new chat interface.
- **Review success/failure pop-ups:** There are a lot of these messages that appear in the interface - always temporarily - when a process completes successfully. For example, adding a character from DND Beyond or closing a session. Is this always necessary and can we make it more consistent when this is done and when it isn't.
- **Refine "How to play" copy and formatting:** Improve the instructions panel on the Play Mode tab.
- **Check for characters:** Check that the user has at least selected some characters in the Play Mode tab before allowing the user to interact via the chat interface.
- **Expand the input field:** Expand the text field when players can type text on the Play mode tab so that it can handle longer messages.

### Major Features
Features that require significant overhauls - usually both backend and frontend changes working in tandem.

- **Tools for subagents:** Teach subagents better how and when to use tools and functions. For example, teaching the qu_situation subagent when it might need to search memories.
- **Better combat initiation:** Currently, the DM rarely deploys the combat_designer subagent. This should happen whenever there is a possibility of a conflict in the near future, so that when the time comes, we have already thought about the abilities of the enemies/combatants. This could be a separate routine that runs every turn, to decide whether the existing combat notes still apply.
- **Improve opening readouts:** These are two short. I think we need to give two messages - one that sets the scene vividly and creatively. And then a shorter more concise one that explains exactly what has just happened and kicks the players into action.
- **Multiple buttons for sending messages:** Depending on what the user wants to do, perhaps they should have different buttons to press: one to meta-converse with the DM, one to act as a party, one to act as an individual party member. The latter could work where, if you click it, you then have to select the character you are acting as.
- **Function to retrieve character data:** Function to retrieve data from character sheets that can then be included as a tool for certain subagents that need it.
- **Character memory:** Work out how to build a memory system that is specific to any changes to a character that depart from the data stored on their character sheet. For example, hit point changes, conditions, new items etc. Allow users to export and handy guide so that they can easily update their character sheet in DnD Beyond.
- **Milestone detector routine:** Build into the multi-agent system the ability to detect when users hit one of the specified milestones in the session plan and give a congratulations note to the user. This could also detect when the DM should recommend that the user ends the session.

### New Epics
Vaguely defined ideas that need to be thought through more carefully, in terms of how they would actually be achieved.

- **Dialogue mode:** Option to enter a real-time dialogue with an NPC wihtin a session. Possibly via a completely new modal or screen. Or this could simply start with more real-time voice playback within the chat interface, to avoid the user having to wait ages for the system to process long messages.
- **Combat mode:** Different interface for combat situations, which can manage initiative, turns, and shows more visual information to players about the state of play.
- **Async agents:** Asynchronous agents that are constantly doing checks and managing the meta data of a campaign. This could include creating NPC records, or new items, or setting up encounters.
- **Multiplayer mode:** Enable multiple users to interact with the system at the same time. Start by enabling single-player for multiple users and gradually evolve to multiple players interacting within the same session.
- **Involve the user in dice rolls:** Restructure the gameplay subagent so that it sets the rules but allows players to do their own dice rolls and report back.
- **Rules retriever:** Routine to go and retireve DnD 5e rules from an official source without need LLM tokens.

### Technical Improvements
Purely architectural or engineering concerns. They may add more reliablity to the system or the quality of outputs but the don't add any genuinely new features.

- **Implement Token Budget Framework:** See ARCHITECTURE_REVIEW.md
- **Retry logic for transient LLM failures:** See ARCHITECTURE_REVIEW.md
- **Add JSON Response Validation:** See ARCHITECTURE_REVIEW.md
- **Comprehensive Game Logic Test Suite:** See ARCHITECTURE_REVIEW.md
- **Create Integration/Eval Tests for Multi-Agent Routing:** See ARCHITECTURE_REVIEW.md
- **Better Metrics Collection:** See ARCHITECTURE_REVIEW.md
- **Define Agent Response Types:** See ARCHITECTURE_REVIEW.md
Agent guardrails
- **Structured Validation / Agent Contracts:** See ARCHITECTURE_REVIEW.md
- **Agent guardrails:** More expansive use of the "guardrails" concpet in the Open AI Agents SDK
- **Create Agent Contracts Document:** See ARCHITECTURE_REVIEW.md
- **Error Handling Guide for developers:** See ARCHITECTURE_REVIEW.md
- **Context engineering runbook:** See ARCHITECTURE_REVIEW.md
- **Productionise:** Productionise into two environments - Dev and Prod.
- **Homegrown ML models and SLMs:** Build specialist AIs and self-host them to reduce overall AI token costs. 

---

## Current Plan

### Necessary for MVP (pre-productionise)
Minor UX Features      | Expand the input field
Major Features         | Better combat initiation
Major Features         | Improve opening readouts
Major Features         | Multiple buttons for sending messages
Technical Improvements | Retry logic for transient LLM failures
Technical Improvements | Add JSON Response Validation
Technical Improvements | Comprehensive Game Logic Test Suite
Technical Improvements | Create Integration/Eval Tests for Multi-Agent Routing
Technical Improvements | Better Metrics Collection
Technical Improvements | Error Handling Guide for developers
Technical Improvements | Context engineering runbook (plus research spike)

### Nice-to-have pre-production PRIORITY I
Minor UX Features      | Delete campaign
Minor UX Features      | Dim brightness in World Review
Minor UX Features      | Refine "How to play" copy and formatting
Minor UX Features      | Check for characters
Major Features         | Tools for subagents
Major Features         | Function to retrieve character data

### Nice-to-have pre-production PRIORITY II
Minor UX Features      | Better JSON reader
Minor UX Features      | Dim brightness in World Review
Minor UX Features      | Review success/failure pop-ups
Major Features         | Character memory
Major Features         | Milestone detector routine

### Productionise
Technical Improvements | Productionise

### Most likely next
New Epics              | Combat mode
New Epics              | Involve the user in dice rolls
New Epics              | Rules retriever
Technical Improvements | Implement Token Budget Framework
Technical Improvements | Define Agent Response Types
Technical Improvements | Structured Validation / Agent Contracts
Technical Improvements | Agent guardrails
Technical Improvements | Create Agent Contracts Document

### Unlikely to get to
New Epics              | Dialogue mode
New Epics              | Multiplayer mode
New Epics              | Async agents
Technical Improvements | Homegrown ML models and SLMs  

---

## Update 1.0

**Agent guardrails:** Added a suite of unit tests and provided testing best practice documentation. Still need to work on integration tests and evals.

**Dim brightness in World Review:** Done

**Expand the input field:** Tried but failed to implement successfully.

**Multiple buttons for sending messages:** Tried but failed to implement successfully.

---

## Update 1.1

### Completed items from roadmap:

**Implement Token Budget Framework:** ✅ DONE (was in "Most likely next")
- Created `src/library/token_budget.py` with a TokenBudget class
- Uses tiktoken (`cl100k_base` encoding) for accurate OpenAI token counting
- Provides per-agent budgets: router (1K), narrative_short (6K), narrative_long (8K), qa_rules (5K), qa_situation (5K), npc_dialogue (6K), combat_designer (8K), travel (6K), gameplay (7K)
- Automatically trims oversized context while preserving recent content (most relevant for D&D gameplay)
- Supports environment variable overrides (e.g., `TOKEN_BUDGET_ROUTER=500`)
- Logs warnings when context exceeds budget
- Integrated into `build_agent_context()` in `turn_router.py` with automatic enforcement
- Added 21 unit tests in `test_token_budget.py`

**Add JSON Response Validation:** ✅ DONE (was in "Necessary for MVP")
- Created `src/library/response_models.py` with Pydantic models: RouterIntent, ScenePatch, MemoryWrite, DiceRollResult
- Updated router agent in `game_engine.py` to use `output_type=RouterIntent` for guaranteed valid JSON responses (OpenAI Structured Outputs)
- Updated `turn_router.py` to handle structured RouterIntent objects directly (with fallback to legacy JSON parsing for backwards compatibility)
- Added schema warmup routine in `run_server.py` that pre-caches schemas at server startup to avoid 10-60s first-request latency
- Added 16 unit tests in `test_response_models.py` for model validation

**Comprehensive Game Logic Test Suite:** ✅ PARTIAL (was in "Necessary for MVP")
- Test suite expanded from 78 to 115 tests
- Added test modules for token_budget.py and response_models.py
- Still need integration tests and evals

### Test suite status:
All 115 unit tests pass.

### Next steps:
1. Monitor real session contexts post-deployment to tune per-agent budgets
2. Monitor production router logs to confirm structured outputs remain stable
3. Extend structured-output coverage to remaining agents (e.g., scene patch flows) when ready