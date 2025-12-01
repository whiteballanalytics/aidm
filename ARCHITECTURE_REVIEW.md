# D&D AI Dungeon Master - Architecture & Engineering Review

**Date**: December 2025  
**Status**: Foundation-stage product with strong agent architecture; engineering practices need formalization.

---

## Executive Summary

This is a sophisticated AI-driven D&D session management system with a well-designed multi-agent routing layer. The agent architecture (router → specialist dispatch) is clean and extensible. However, the project lacks:

1. **Comprehensive test coverage** for critical game logic paths
2. **Context engineering discipline** (prompts embedded vs. centralized, inconsistent context sizing)
3. **Error recovery strategies** for LLM failures and edge cases
4. **Structured logging and observability** for production debugging
5. **Type safety and validation** across agent input/output boundaries
6. **Documentation of game rules and contract specifications**

Below are **specific, actionable recommendations** organized by engineering practice.

---

## 1. CONTEXT ENGINEERING & PROMPT MANAGEMENT

### Current State
- ✅ Multi-agent routing layer is clean (`build_agent_context()` in `turn_router.py`)
- ✅ Specialist agents have dedicated prompt files
- ❌ Context sizing is inconsistent:
  - `dm_input` capped at 500 chars in router (line ~131 `turn_router.py`)
  - `recent_recap` capped at 4000 words (`RECENT_RECAP_WORD_LIMIT` in `game_engine.py:38`)
  - No token-based trimming; unpredictable cost & reliability
  - `dm_context_blob()` sends full session plan + scene state (unbounded growth)

### Recommendations

**1.1 Implement Token Budget Framework**
Create a central token accounting system:

```python
# src/library/token_budget.py
import tiktoken

class TokenBudget:
    """
    Centralized token management across all agent contexts.
    Enforces hard limits per agent type to prevent cost explosion and timeouts.
    """
    
    # Token allocations per agent (tunable via env vars)
    BUDGETS = {
        "router": 300,              # Minimal: classify only
        "narrative_short": 2000,    # Moderate: brief responses
        "narrative_long": 3000,     # Rich: detailed descriptions
        "qa_rules": 1500,           # Rules lookup + context
        "qa_situation": 1500,       # Situation awareness
        "npc_dialogue": 2500,       # NPC personality + scene
        "combat_designer": 3500,    # Complex encounter design
        "gameplay": 2500,           # Dice rolls + mechanics
    }
    
    @staticmethod
    def encode(text: str, model: str = "gpt-4o-mini") -> list:
        """Get token count for text."""
        enc = tiktoken.encoding_for_model(model)
        return enc.encode(text)
    
    @staticmethod
    def trim_to_budget(text: str, max_tokens: int, model: str = "gpt-4o-mini") -> str:
        """
        Trim text to token budget, preserving most recent content.
        Use case: Keep final turns, drop early context.
        """
        enc = tiktoken.encoding_for_model(model)
        tokens = enc.encode(text)
        if len(tokens) <= max_tokens:
            return text
        # Keep most recent tokens
        trimmed = enc.decode(tokens[-max_tokens:])
        return trimmed
    
    @staticmethod
    def validate_context(agent_type: str, context: str, model: str = "gpt-4o-mini") -> tuple[bool, dict]:
        """
        Validate context fits within budget.
        Returns (is_valid, metadata).
        """
        budget = TokenBudget.BUDGETS.get(agent_type, 2000)
        tokens = TokenBudget.encode(context, model)
        token_count = len(tokens)
        
        return (token_count <= budget, {
            "agent_type": agent_type,
            "token_count": token_count,
            "budget": budget,
            "usage_percent": (token_count / budget) * 100,
        })
```

**1.2 Update `build_agent_context()` to enforce budgets**

```python
# src/orchestration/turn_router.py
from library.token_budget import TokenBudget

def build_agent_context(
    agent_type: str,
    session_context: Dict[str, Any],
    user_input: str
) -> str:
    """
    Build context tailored to each agent type.
    Enforces token budgets and logs when trimming occurs.
    """
    recent_recap = session_context.get("recent_recap", "")
    dm_input = session_context.get("dm_input", "")
    
    if agent_type == "router":
        context = recent_recap or "(No recent history)"
    elif agent_type in ("narrative_short", "narrative_long"):
        context = f"{dm_input}\n\nPlayer: {user_input}"
    # ... other cases ...
    else:
        context = f"{dm_input}\n\nPlayer: {user_input}"
    
    # ENFORCE TOKEN BUDGET
    is_valid, metadata = TokenBudget.validate_context(agent_type, context)
    if not is_valid:
        print(f"[WARNING] {agent_type} context exceeds budget: {metadata['usage_percent']:.1f}%")
        context = TokenBudget.trim_to_budget(context, TokenBudget.BUDGETS[agent_type])
        print(f"[INFO] Trimmed context to {metadata['budget']} tokens")
    
    return context
```

**Why this matters:**
- Prevents runaway token costs (GPT-4o-mini @ $0.15/1M input tokens adds up fast)
- Predictable LLM latency (fewer tokens = faster inference)
- Auditable context sizing for debugging "why did the agent miss information?"

---

## 2. ERROR RECOVERY & FALLBACK STRATEGIES

### Current State
- ✅ Router has basic fallback (line ~146 in `turn_router.py`)
- ❌ No retry logic for transient LLM failures
- ❌ No graceful degradation if vector store search fails
- ❌ No handling of malformed JSON responses (agent outputs corrupt data)
- ❌ No circuit breaker for cascading LLM failures

### Recommendations

**2.1 Implement Structured Error Recovery**

```python
# src/library/error_recovery.py
from enum import Enum
from typing import Optional, Callable, TypeVar, Awaitable

class ErrorSeverity(Enum):
    RECOVERABLE = "recoverable"      # Retry or fallback
    DEGRADED = "degraded"             # Use cached/simplified response
    FATAL = "fatal"                   # Abort turn, notify user

class LLMErrorContext:
    """Context for LLM errors with metadata for logging/debugging."""
    def __init__(self, agent_type: str, error: Exception, attempt: int, max_attempts: int):
        self.agent_type = agent_type
        self.error = error
        self.attempt = attempt
        self.max_attempts = max_attempts
        self.error_type = type(error).__name__
        self.should_retry = attempt < max_attempts and self._is_transient()
    
    def _is_transient(self) -> bool:
        """Detect transient vs. permanent errors."""
        transient_patterns = [
            "timeout",
            "ConnectionError",
            "RateLimitError",
            "APIConnectionError",
        ]
        return any(p in self.error_type for p in transient_patterns)


async def run_agent_with_fallback(
    agent,
    context: str,
    agent_type: str,
    fallback_response: Optional[str] = None,
    max_retries: int = 3,
) -> dict:
    """
    Run an agent with exponential backoff retry + fallback.
    Returns dict with (response, severity, recovered_from_error).
    """
    from library.logginghooks import jl_write
    import asyncio
    
    for attempt in range(max_retries):
        try:
            result = await Runner.run(agent, context, hooks=LocalRunLogger())
            return {
                "response": result,
                "severity": ErrorSeverity.RECOVERABLE,
                "error": None,
                "recovered": False,
            }
        
        except Exception as e:
            error_ctx = LLMErrorContext(agent_type, e, attempt + 1, max_retries)
            
            # Log error with context
            jl_write({
                "event": "agent_error",
                "agent_type": agent_type,
                "error_type": error_ctx.error_type,
                "attempt": attempt + 1,
                "max_attempts": max_retries,
                "should_retry": error_ctx.should_retry,
                "error_message": str(e)[:200],
            })
            
            if error_ctx.should_retry:
                # Exponential backoff
                wait_seconds = 2 ** attempt
                print(f"[RETRY] {agent_type} attempt {attempt + 1}/{max_retries}, waiting {wait_seconds}s")
                await asyncio.sleep(wait_seconds)
                continue
            
            # Non-transient error or max retries exceeded
            if fallback_response:
                print(f"[FALLBACK] Using fallback response for {agent_type}")
                return {
                    "response": fallback_response,
                    "severity": ErrorSeverity.DEGRADED,
                    "error": str(e),
                    "recovered": True,
                }
            
            # Give up
            return {
                "response": None,
                "severity": ErrorSeverity.FATAL,
                "error": str(e),
                "recovered": False,
            }
    
    # Should not reach here, but handle it
    return {
        "response": fallback_response or "An unexpected error occurred.",
        "severity": ErrorSeverity.DEGRADED if fallback_response else ErrorSeverity.FATAL,
        "error": "Max retries exceeded",
        "recovered": bool(fallback_response),
    }
```

**2.2 Add JSON Response Validation**

```python
# src/library/response_validation.py
from typing import Optional, Dict, Any
import json

class ResponseValidator:
    """
    Validate agent JSON responses against expected schemas.
    Prevents silent failures when agents return malformed data.
    """
    
    # Define expected schemas per agent type
    SCHEMAS = {
        "router": {
            "required": ["intent", "confidence"],
            "optional": ["note"],
            "valid_intents": ["narrative_short", "narrative_long", "qa_rules", 
                            "qa_situation", "npc_dialogue", "combat_designer", 
                            "travel", "gameplay"],
        },
        "gameplay": {
            "required": ["scene_state_patch", "turn_summary"],
            "optional": ["memory_writes", "dice_results"],
        },
        "npc_dialogue": {
            "required": ["dialogue"],
            "optional": ["character_state", "emotion_indicators"],
        },
        "combat_designer": {
            "required": ["encounter_name", "encounter_summary", "opponents"],
            "optional": ["scene_state_patch", "difficulty_rationale"],
        },
    }
    
    @staticmethod
    def validate(agent_type: str, response_text: str) -> tuple[bool, Optional[Dict], str]:
        """
        Validate response JSON.
        Returns (is_valid, parsed_json, error_message).
        """
        # Extract JSON from response
        parsed = ResponseValidator._extract_json(response_text)
        if parsed is None:
            return (False, None, "No JSON found in response")
        
        schema = ResponseValidator.SCHEMAS.get(agent_type)
        if not schema:
            # No schema defined; assume valid
            return (True, parsed, "")
        
        # Check required fields
        for field in schema.get("required", []):
            if field not in parsed:
                return (False, parsed, f"Missing required field: {field}")
        
        # Validate enum fields if applicable
        if agent_type == "router" and "intent" in parsed:
            if parsed["intent"] not in schema["valid_intents"]:
                return (False, parsed, f"Invalid intent: {parsed['intent']}")
        
        return (True, parsed, "")
    
    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """Extract JSON from text (fenced or bare)."""
        import re
        
        # Try fenced JSON first
        fenced_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if fenced_match:
            try:
                return json.loads(fenced_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try bare JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        return None
```

**Why this matters:**
- **Prevents silent failures**: Missing fields caught immediately, not 3 turns later
- **Improves observability**: Know which agents are flaky and why
- **Enables safe fallbacks**: Only use fallbacks when you understand what went wrong

---

## 3. UNIT TEST COVERAGE FOR GAME LOGIC

### Current State
- ✅ Basic tests exist (`test_roll.py`, `test_memory_search.py`)
- ❌ **Zero tests for critical game logic**:
  - `play_turn()` — the core gameplay loop
  - `build_agent_context()` — context routing
  - `orchestrate_turn()` — multi-agent dispatch
  - Scene state merging
  - Session persistence & recovery

### Recommendations

**3.1 Create Comprehensive Game Logic Test Suite**

```python
# tests/test_game_engine.py
import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import asyncio

from src.game_engine import (
    SceneState,
    merge_scene_patch,
    dm_context_blob,
    extract_update_payload,
    strip_json_block,
)


class TestSceneStateMerging:
    """Test scene state mutations, the foundation of gameplay continuity."""
    
    def test_merge_scene_patch_updates_all_fields(self):
        """Verify that merge_scene_patch applies patches correctly."""
        initial = SceneState(
            time_of_day="morning",
            region="Waterdeep",
            sub_region="Dock Ward",
            specific_location="The Crying Gull tavern",
            participants=["Barkeep Jim", "Player"],
            exits=["North: street", "South: docks"],
        )
        
        patch = {
            "time_of_day": "evening",
            "participants": ["Barkeep Jim", "Player", "Hooded Figure"],
        }
        
        result = merge_scene_patch(initial, patch)
        
        assert result.time_of_day == "evening"  # Updated
        assert result.participants == ["Barkeep Jim", "Player", "Hooded Figure"]  # Updated
        assert result.region == "Waterdeep"  # Unchanged
        assert result.exits == ["North: street", "South: docks"]  # Unchanged
    
    def test_merge_ignores_none_values(self):
        """Verify None values in patch don't overwrite scene state."""
        initial = SceneState(
            time_of_day="morning",
            region="Waterdeep",
            sub_region="Dock Ward",
            specific_location="Tavern",
            participants=["Alice"],
            exits=["North"],
        )
        
        patch = {"time_of_day": None, "region": "Neverwinter"}
        result = merge_scene_patch(initial, patch)
        
        assert result.time_of_day == "morning"  # Unchanged (was None)
        assert result.region == "Neverwinter"  # Updated


class TestResponseParsing:
    """Test parsing of agent responses (JSON extraction + narrative stripping)."""
    
    def test_extract_update_payload_from_fenced_json(self):
        """Extract JSON from triple-backtick fence."""
        response = """The goblin lunges at you!

```json
{
  "scene_state_patch": {"participants": ["Goblin", "Player"]},
  "turn_summary": "Combat begins"
}
```
"""
        payload = extract_update_payload(response)
        assert payload is not None
        assert payload["scene_state_patch"]["participants"] == ["Goblin", "Player"]
    
    def test_extract_update_payload_from_bare_json(self):
        """Extract bare JSON (no fencing)."""
        response = '{"turn_summary": "Action taken", "memory_writes": []}'
        payload = extract_update_payload(response)
        assert payload["turn_summary"] == "Action taken"
    
    def test_strip_json_block_leaves_narrative(self):
        """Verify narrative is preserved after JSON removal."""
        response = """The scene unfolds dramatically...

```json
{"turn_summary": "Action"}
```

More narrative here."""
        narrative = strip_json_block(response)
        assert "The scene unfolds" in narrative
        assert "More narrative here" in narrative
        assert "json" not in narrative.lower()
    
    def test_malformed_json_returns_none(self):
        """Gracefully handle invalid JSON."""
        response = '{"bad json": invalid}'
        payload = extract_update_payload(response)
        assert payload is None


class TestContextBuilding:
    """Test agent context routing (ensures right info to right agent)."""
    
    def test_router_receives_minimal_context(self):
        """Router should only get recent recap, not full DM context."""
        from src.orchestration.turn_router import build_agent_context
        
        session_context = {
            "recent_recap": "Last two turns: Player opened door, found key.",
            "dm_input": "MASSIVE DM CONTEXT WITH FULL SCENE STATE...",  # Should be ignored
            "scene_state": {},
        }
        
        context = build_agent_context("router", session_context, "I attack the goblin")
        
        assert "Last two turns" in context
        assert "MASSIVE DM CONTEXT" not in context  # Trimmed for router
    
    def test_narrative_agent_receives_full_context(self):
        """Narrative agents should get scene state + player input."""
        from src.orchestration.turn_router import build_agent_context
        
        session_context = {
            "recent_recap": "Recent events...",
            "dm_input": "You are in a tavern. The bar is crowded.",
            "scene_state": {"time_of_day": "evening"},
        }
        
        context = build_agent_context("narrative_long", session_context, "I look around")
        
        assert "You are in a tavern" in context
        assert "I look around" in context


class TestSessionPersistence:
    """Test session save/load cycles (critical for continuation)."""
    
    @pytest.mark.asyncio
    async def test_session_survives_save_load_cycle(self, tmp_path):
        """Verify session can be saved and reloaded without data loss."""
        from src.game_engine import load_session, create_session
        
        # Create mock session
        session_data = {
            "session_id": "test_123",
            "campaign_id": "camp_001",
            "turn_count": 5,
            "chat_history": [
                {"turn_number": 1, "user_input": "I open the door"},
                {"turn_number": 2, "user_input": "I attack"},
            ],
            "session_plan": {"session_title": "Test Session"},
        }
        
        # Save
        session_path = tmp_path / "test_session.json"
        session_path.write_text(json.dumps(session_data))
        
        # Load
        loaded = json.loads(session_path.read_text())
        
        assert loaded["turn_count"] == 5
        assert len(loaded["chat_history"]) == 2
        assert loaded["session_plan"]["session_title"] == "Test Session"


class TestTurnPlayback:
    """Test the core gameplay loop (play_turn)."""
    
    @pytest.mark.asyncio
    async def test_play_turn_updates_session_state(self):
        """Verify play_turn increments turn count and adds to history."""
        # Mock dependencies
        mock_session = {
            "session_id": "s_001",
            "campaign_id": "c_001",
            "turn_count": 0,
            "chat_history": [],
            "status": "open",
            "session_plan": {},
        }
        
        mock_campaign = {
            "campaign_id": "c_001",
            "world_collection": "SwordCoast",
        }
        
        with patch("src.game_engine.load_session", new_callable=AsyncMock) as mock_load_session, \
             patch("src.game_engine.load_campaign", new_callable=AsyncMock) as mock_load_campaign, \
             patch("src.game_engine.setup_agents_for_campaign") as mock_setup:
            
            mock_load_session.return_value = mock_session
            mock_load_campaign.return_value = mock_campaign
            
            # Mock agent response
            mock_agent = AsyncMock()
            mock_agent.return_value = Mock(
                final_output="The goblin attacks you!\n```json\n{\"turn_summary\": \"Combat turn 1\"}\n```"
            )
            
            mock_setup.return_value = {
                "dm_agent": mock_agent,
                "memory_search": Mock(),
            }
            
            # Note: This test is simplified; full integration test requires more mocking
            # The key is that turn_count and chat_history should be updated
```

**3.2 Create Integration Tests for Multi-Agent Routing**

```python
# tests/test_orchestration.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
from src.orchestration.turn_router import orchestrate_turn, build_agent_context


class TestMultiAgentRouting:
    """Test that router correctly classifies intents and dispatches to specialists."""
    
    @pytest.mark.asyncio
    async def test_router_routes_narrative_input_to_narrative_agent(self):
        """Verify 'look around' goes to narrative_short, not gameplay."""
        
        # Mock router response
        router_response = Mock(
            final_output=json.dumps({
                "intent": "narrative_short",
                "confidence": "high",
                "note": "Simple observation"
            })
        )
        
        agents = {
            "router": AsyncMock(return_value=router_response),
            "narrative_short": AsyncMock(return_value=Mock(final_output="You see...")),
            "gameplay": Mock(),  # Should NOT be called
        }
        
        session_context = {
            "dm_input": "You are in a tavern",
            "recent_recap": "Just arrived",
        }
        
        with patch("src.orchestration.turn_router.Runner") as mock_runner:
            mock_runner.run = AsyncMock()
            mock_runner.run.side_effect = [router_response, Mock(final_output="You see...")]
            
            # This is a simplified version; actual test would be more complete
            # The key assertion: narrative_short should be called, not gameplay
```

**Why this matters:**
- **Catches regressions**: If `play_turn()` stops updating `turn_count`, tests fail immediately
- **Documents expected behavior**: Tests are executable specs
- **Enables refactoring**: Safe to optimize without breaking gameplay

---

## 4. STRUCTURED LOGGING & OBSERVABILITY

### Current State
- ✅ Basic logging exists (`logginghooks.py`)
- ❌ No structured logging (JSON events for ELK/DataDog)
- ❌ No metrics (latency, token usage, error rates)
- ❌ Router decisions not logged in queryable format

### Recommendations

**4.1 Structured Event Logging**

```python
# src/library/event_logger.py
import json
import time
from dataclasses import asdict, dataclass
from typing import Optional, Any
from datetime import datetime


@dataclass
class GameEvent:
    """Structured event for D&D gameplay."""
    event_type: str  # "turn_start", "agent_dispatch", "turn_end", "error", etc.
    timestamp: float
    campaign_id: str
    session_id: str
    turn_number: Optional[int] = None
    agent_type: Optional[str] = None
    player_input: Optional[str] = None  # First 500 chars only
    dm_response_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    error_type: Optional[str] = None
    severity: Optional[str] = None  # "info", "warning", "error"
    metadata: Optional[dict] = None
    
    def to_json(self) -> str:
        """Serialize to JSON for logging backends."""
        data = asdict(self)
        data['timestamp_iso'] = datetime.utcfromtimestamp(data['timestamp']).isoformat()
        return json.dumps(data, default=str)


class StructuredLogger:
    """
    Log events in structured format (JSON lines).
    Compatible with ELK, DataDog, CloudWatch, etc.
    """
    
    def __init__(self, logfile: str = "logs/game_events.jsonl"):
        self.logfile = logfile
        Path(logfile).parent.mkdir(parents=True, exist_ok=True)
    
    def log_event(self, event: GameEvent):
        """Append structured event to log."""
        with open(self.logfile, "a") as f:
            f.write(event.to_json() + "\n")
    
    def log_turn_start(self, campaign_id: str, session_id: str, turn_number: int, player_input: str):
        """Log the start of a gameplay turn."""
        event = GameEvent(
            event_type="turn_start",
            timestamp=time.time(),
            campaign_id=campaign_id,
            session_id=session_id,
            turn_number=turn_number,
            player_input=player_input[:500],
            severity="info",
        )
        self.log_event(event)
    
    def log_agent_dispatch(self, campaign_id: str, session_id: str, agent_type: str, context_tokens: int):
        """Log when an agent is called."""
        event = GameEvent(
            event_type="agent_dispatch",
            timestamp=time.time(),
            campaign_id=campaign_id,
            session_id=session_id,
            agent_type=agent_type,
            metadata={"context_tokens": context_tokens},
            severity="info",
        )
        self.log_event(event)
    
    def log_turn_error(self, campaign_id: str, session_id: str, turn_number: int, 
                       error_type: str, error_message: str):
        """Log an error during turn processing."""
        event = GameEvent(
            event_type="turn_error",
            timestamp=time.time(),
            campaign_id=campaign_id,
            session_id=session_id,
            turn_number=turn_number,
            error_type=error_type,
            metadata={"error_message": error_message[:200]},
            severity="error",
        )
        self.log_event(event)


# Usage in orchestrate_turn:
logger = StructuredLogger()

async def orchestrate_turn_instrumented(...):
    start_time = time.time()
    logger.log_turn_start(campaign_id, session_id, turn_number, user_input)
    
    try:
        # Route and dispatch
        result = await orchestrate_turn(...)
        
        latency_ms = (time.time() - start_time) * 1000
        logger.log_event(GameEvent(
            event_type="turn_end",
            timestamp=time.time(),
            campaign_id=campaign_id,
            session_id=session_id,
            latency_ms=latency_ms,
            severity="info",
        ))
        
        return result
    
    except Exception as e:
        logger.log_turn_error(campaign_id, session_id, turn_number, type(e).__name__, str(e))
        raise
```

**4.2 Metrics Collection**

```python
# src/library/metrics.py
from dataclasses import dataclass
from typing import Dict
import time


@dataclass
class AgentMetrics:
    """Track performance metrics per agent type."""
    agent_type: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    avg_tokens_in: float = 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.calls if self.calls > 0 else 0
    
    @property
    def success_rate(self) -> float:
        return (self.successes / self.calls * 100) if self.calls > 0 else 0


class MetricsCollector:
    """Collect and report metrics for operational awareness."""
    
    def __init__(self):
        self.agent_metrics: Dict[str, AgentMetrics] = {}
    
    def record_agent_call(self, agent_type: str, latency_ms: float, tokens_in: int, success: bool):
        """Record an agent call."""
        if agent_type not in self.agent_metrics:
            self.agent_metrics[agent_type] = AgentMetrics(agent_type=agent_type)
        
        metrics = self.agent_metrics[agent_type]
        metrics.calls += 1
        metrics.total_latency_ms += latency_ms
        metrics.avg_tokens_in = (metrics.avg_tokens_in * (metrics.calls - 1) + tokens_in) / metrics.calls
        
        if success:
            metrics.successes += 1
        else:
            metrics.failures += 1
    
    def report(self) -> str:
        """Human-readable metrics report."""
        lines = []
        for agent_type, metrics in self.agent_metrics.items():
            lines.append(f"{agent_type:20} | Calls: {metrics.calls:3} | "
                        f"Success: {metrics.success_rate:5.1f}% | "
                        f"Avg Latency: {metrics.avg_latency_ms:6.0f}ms | "
                        f"Avg Tokens: {metrics.avg_tokens_in:6.0f}")
        return "\n".join(lines)
```

**Why this matters:**
- **Operational debugging**: Query logs to understand "why did agent X fail on turn 42?"
- **Performance tracking**: Identify slow agents, optimize
- **Cost tracking**: Measure actual token usage vs. budget

---

## 5. TYPE SAFETY & VALIDATION

### Current State
- ✅ Pydantic models for `SceneState`, `CampaignInfo`, `SessionStatus`
- ❌ Agent responses (JSON payloads) are untyped/unvalidated
- ❌ No validation at agent input boundaries
- ❌ No enforcement of "agent contracts"

### Recommendations

**5.1 Define Agent Response Types**

```python
# src/library/agent_contracts.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal


class RouterResponse(BaseModel):
    """Contract for router agent JSON output."""
    intent: Literal[
        "narrative_short", "narrative_long", "qa_situation", "qa_rules",
        "npc_dialogue", "combat_designer", "travel", "gameplay"
    ]
    confidence: Literal["high", "medium", "low"]
    note: Optional[str] = None
    
    @validator("intent")
    def validate_intent(cls, v):
        if not v:
            raise ValueError("intent must be one of: narrative_short, narrative_long, ...")
        return v


class GameplayResponse(BaseModel):
    """Contract for gameplay agent JSON output."""
    scene_state_patch: dict
    turn_summary: str
    memory_writes: Optional[List[dict]] = []
    dice_results: Optional[dict] = None


class NPCDialogueResponse(BaseModel):
    """Contract for NPC dialogue agent JSON output."""
    dialogue: str  # The NPC's spoken words
    character_emotion: Optional[str] = None
    scene_state_patch: Optional[dict] = None


class CombatDesignerResponse(BaseModel):
    """Contract for combat designer agent JSON output."""
    encounter_name: str
    encounter_summary: str
    encounter_role: Literal["filler", "attrition", "main_set_piece", "boss"]
    target_difficulty: Literal["Easy", "Medium", "Hard", "Deadly"]
    difficulty_rationale: str
    battlefield_description: str
    tactics: str
    opponents: List[dict] = Field(..., description="List of enemy stat blocks")
    scene_state_patch: Optional[dict] = None


# Map agent types to response schemas
AGENT_RESPONSE_SCHEMAS = {
    "router": RouterResponse,
    "gameplay": GameplayResponse,
    "npc_dialogue": NPCDialogueResponse,
    "combat_designer": CombatDesignerResponse,
}


def validate_agent_response(agent_type: str, response_json: dict) -> tuple[bool, Optional[BaseModel], str]:
    """
    Validate agent response against its contract.
    Returns (is_valid, validated_model, error_message).
    """
    schema_class = AGENT_RESPONSE_SCHEMAS.get(agent_type)
    
    if not schema_class:
        # No schema defined for this agent type
        return (True, None, "")
    
    try:
        model = schema_class(**response_json)
        return (True, model, "")
    except Exception as e:
        return (False, None, str(e))
```

**5.2 Enforce Validation at Dispatch Boundary**

```python
# In orchestrate_turn():

async def orchestrate_turn(...):
    # ... router calls ...
    
    # VALIDATE router response against contract
    is_valid, router_model, error_msg = validate_agent_response("router", router_data)
    if not is_valid:
        print(f"[ERROR] Router response invalid: {error_msg}")
        # Fallback to narrative_short
        intent = "narrative_short"
    else:
        intent = router_model.intent
    
    # ... specialist calls ...
    
    # VALIDATE specialist response
    is_valid, specialist_model, error_msg = validate_agent_response(intent, update_payload)
    if not is_valid:
        print(f"[ERROR] {intent} response invalid: {error_msg}")
        # Use fallback response or re-raise
```

**Why this matters:**
- **Catch contract violations early**: If agent forgets to include `turn_summary`, caught immediately
- **IDE support**: Type hints enable autocomplete in client code
- **Self-documenting**: Response format is explicit, not buried in prompts

---

## 6. DOCUMENTATION & CONTRACTS

### Current State
- ✅ Good prompts (`prompts/system/*.md`) define agent roles
- ✅ `replit.md` and `README.md` exist
- ❌ No **agent contract documentation** (what input → output mapping?)
- ❌ No **error handling guide** for developers
- ❌ No **context engineering runbook**
- ❌ No **troubleshooting guide** for DMs

### Recommendations

**6.1 Create Agent Contracts Document**

```markdown
# Agent Contracts

This document specifies the input → output contract for each agent.
Use this to validate agent responses and understand expected behavior.

## Router Agent

**Input Format:**
```
Classify this player input:

{user_input}

Context (recent events):
{recent_recap}...
```

**Expected JSON Output:**
```json
{
  "intent": "narrative_short | narrative_long | qa_rules | qa_situation | npc_dialogue | combat_designer | travel | gameplay",
  "confidence": "high | medium | low",
  "note": "Optional explanation"
}
```

**Success Criteria:**
- Intent is one of the 8 valid values
- Confidence is high/medium/low
- Router correctly distinguishes e.g. "What is the time?" (qa_situation) vs. "I wait for nightfall" (narrative_short)

## Gameplay Agent

**Input Format:**
Full DM context (scene state, session plan) + user action

**Expected JSON Output:**
```json
{
  "scene_state_patch": {
    "participants": ["..."],
    "time_of_day": "..."
  },
  "turn_summary": "One sentence summary of what happened",
  "memory_writes": [
    {"type": "event", "keys": [...], "summary": "..."}
  ]
}
```

**Success Criteria:**
- scene_state_patch contains valid updates (no nulls, no extra fields)
- turn_summary is 1-2 sentences, action-focused
- memory_writes are relevant to the turn
```

**6.2 Create Operational Runbook**

```markdown
# Context Engineering Runbook

## Problem: Agent responses are too short or too long

### Check token budget
1. Enable logging: `ENABLE_TOKEN_LOGGING=true`
2. Look at logs for agent type in question
3. Check if context_tokens > budget

### Solution options
- Reduce RECENT_RECAP_TURNS (fewer turns = smaller recap)
- Reduce RECENT_RECAP_WORD_LIMIT
- Disable certain tools for that agent
- Increase agent's token budget (affects cost)

## Problem: Agent routing is wrong (narrative_short when should be gameplay)

### Debug router decision
1. Check logs for `[ROUTER]` line
2. Look at "intent_used" vs. "confidence"
3. If confidence=low, router was unsure

### Solution
- Check router prompt (`dm_router.md`) for guidance on that input type
- Add example to router prompt if ambiguous
- Test router in isolation with that input

## Problem: Agent fails with "Max retries exceeded"

### Likely causes
- API quota exceeded
- Network connectivity issue
- Agent prompt too complex for model

### Fix
- Check OpenAI API status
- Simplify agent prompt (remove examples if too long)
- Increase max_retries in `error_recovery.py`
```

**Why this matters:**
- **Reduces support burden**: DMs/devs can self-serve troubleshooting
- **Prevents guess-and-check**: Runbook provides systematic approach
- **Captures institutional knowledge**: Future maintainers understand design decisions

---

## 7. DEPENDENCY MANAGEMENT & BUILD REPRODUCIBILITY

### Current State
- ✅ `requirements.txt` exists
- ❌ Pinned versions missing (latest versions always fetched)
- ❌ No lock file (dependency resolution varies by environment)
- ❌ No build/test CI pipeline
- ❌ No development vs. production dependency split

### Recommendations

**7.1 Pin Dependencies**

```
# requirements-prod.txt (current requirements.txt)
openai==1.99.6
openai-agents==0.2.5
pydantic==2.11.7
starlette==0.47.2
uvicorn==0.35.0
python-dotenv==1.1.1
tiktoken==0.7.0  # For token counting
```

```
# requirements-dev.txt (new)
-r requirements-prod.txt
pytest==8.0.0
pytest-asyncio==0.24.0
pytest-cov==5.0.0
pytest-mock==3.14.0
black==24.1.0
mypy==1.9.0
```

**7.2 Add CI/CD Pipeline**

```yaml
# .github/workflows/test.yml
name: Test & Lint

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/ --cov=src --cov-report=term-missing
      - run: black --check src/
      - run: mypy src/
```

**Why this matters:**
- **Reproducibility**: Everyone gets same dependency versions
- **Automation**: Catch regressions before merging
- **Quality gates**: Black/mypy run automatically

---

## SUMMARY TABLE: Implementation Priority

| Area | Priority | Effort | Impact | Owner |
|------|----------|--------|--------|-------|
| **Token budgeting** | P0 | 2h | Prevents cost explosion | Backend |
| **Response validation** | P0 | 3h | Catches agent failures early | Backend |
| **Unit tests (game logic)** | P0 | 8h | Prevents regressions | QA/Backend |
| **Error recovery** | P1 | 4h | Improves reliability | Backend |
| **Structured logging** | P1 | 4h | Enables debugging | DevOps |
| **Type safety (contracts)** | P1 | 3h | Reduces integration bugs | Backend |
| **Documentation** | P2 | 3h | Reduces support burden | Tech Lead |
| **CI/CD pipeline** | P2 | 2h | Automates quality checks | DevOps |

---

## SUMMARY: What To Do First

1. **This week**: Implement token budgeting (`TokenBudget` class) + response validation (`ResponseValidator`). These prevent catastrophic failures (runaway tokens, corrupt game state).

2. **Next week**: Add unit tests for `play_turn()`, `build_agent_context()`, scene merging. These catch regressions as you refactor.

3. **Next sprint**: Structured logging + error recovery. These enable production debugging and reliability.

4. **Ongoing**: Documentation & CI/CD. Low effort, high payoff over time.

---

**Questions?** The recommendations above are specific to an AI-driven game engine. Key theme: **context engineering discipline** (tokens, validation, error handling) is more critical than traditional code quality for LLM-based systems.
