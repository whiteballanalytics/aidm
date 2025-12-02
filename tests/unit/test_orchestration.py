# tests/unit/test_orchestration.py
"""Unit tests for orchestration functions: orchestrate_turn and build_agent_context."""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from orchestration.turn_router import build_agent_context, orchestrate_turn


class TestBuildAgentContext:
    """Tests for build_agent_context function."""

    def test_build_context_router_returns_recent_recap(self):
        """Tests build_agent_context: router agent receives only recent_recap, not full session."""
        session_context = {
            "recent_recap": "The party entered the tavern.",
            "session_plan": {"beats": ["intro", "combat"]},
            "scene_state": {"location": "tavern"}
        }
        
        result = build_agent_context("router", session_context, "I look around")
        
        assert result == "The party entered the tavern."
        assert "session_plan" not in result
        assert "scene_state" not in result

    def test_build_context_router_empty_recap_returns_placeholder(self):
        """Tests build_agent_context: router with empty recap returns '(No recent history)'."""
        session_context = {"recent_recap": ""}
        
        result = build_agent_context("router", session_context, "Hello")
        
        assert result == "(No recent history)"

    def test_build_context_narrative_includes_player_input(self):
        """Tests build_agent_context: narrative agents receive full context with player input appended."""
        session_context = {"recent_recap": "The party rests."}
        
        result = build_agent_context("narrative_short", session_context, "I attack the goblin")
        
        assert "I attack the goblin" in result
        assert "Player:" in result

    def test_build_context_qa_rules_includes_player_input(self):
        """Tests build_agent_context: qa_rules agent receives full context with player input."""
        session_context = {"recent_recap": "Combat started."}
        
        result = build_agent_context("qa_rules", session_context, "Can I use sneak attack?")
        
        assert "Can I use sneak attack?" in result
        assert "Player:" in result

    def test_build_context_unknown_type_uses_default(self):
        """Tests build_agent_context: unknown agent type returns full context (default behavior)."""
        session_context = {"recent_recap": "Session ongoing."}
        
        result = build_agent_context("unknown_agent_xyz", session_context, "Test input")
        
        assert "Test input" in result
        assert "Player:" in result


class TestOrchestrateRouter:
    """Tests for orchestrate_turn router classification behavior."""

    @pytest.fixture
    def mock_agents(self):
        """Create mock agents dict for testing."""
        return {
            "router": MagicMock(),
            "narrative_short": MagicMock(),
            "narrative_long": MagicMock(),
            "qa_rules": MagicMock(),
            "qa_situation": MagicMock(),
            "travel": MagicMock(),
            "gameplay": MagicMock(),
        }

    @pytest.fixture
    def session_context(self):
        """Create sample session context for testing."""
        return {
            "recent_recap": "The party entered the dungeon.",
            "session_plan": {},
            "scene_state": {}
        }

    @pytest.mark.asyncio
    async def test_orchestrate_turn_routes_narrative_short(self, mock_agents, session_context):
        """Tests orchestrate_turn: routes to narrative_short agent when router returns that intent."""
        router_response = SimpleNamespace(final_output='{"intent": "narrative_short", "confidence": "high"}')
        specialist_response = SimpleNamespace(final_output="The goblin lunges at you!")
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "I attack", "user_001",
                mock_agents, session_context
            )
            
            assert result["intent_used"] == "narrative_short"
            assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_orchestrate_turn_routes_qa_rules(self, mock_agents, session_context):
        """Tests orchestrate_turn: routes to qa_rules agent when router classifies rules question."""
        router_response = SimpleNamespace(final_output='{"intent": "qa_rules", "confidence": "high"}')
        specialist_response = SimpleNamespace(final_output="Sneak attack requires advantage.")
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "How does sneak attack work?", "user_001",
                mock_agents, session_context
            )
            
            assert result["intent_used"] == "qa_rules"

    @pytest.mark.asyncio
    async def test_orchestrate_turn_routes_travel(self, mock_agents, session_context):
        """Tests orchestrate_turn: routes to travel agent for travel-related input."""
        router_response = SimpleNamespace(final_output='{"intent": "travel", "confidence": "high"}')
        specialist_response = SimpleNamespace(final_output="You travel north for two days.")
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "We travel to the next town", "user_001",
                mock_agents, session_context
            )
            
            assert result["intent_used"] == "travel"

    @pytest.mark.asyncio
    async def test_orchestrate_turn_routes_gameplay(self, mock_agents, session_context):
        """Tests orchestrate_turn: routes to gameplay agent for gameplay actions."""
        router_response = SimpleNamespace(final_output='{"intent": "gameplay", "confidence": "high"}')
        specialist_response = SimpleNamespace(final_output="Roll for initiative!")
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "I roll to pick the lock", "user_001",
                mock_agents, session_context
            )
            
            assert result["intent_used"] == "gameplay"

    @pytest.mark.asyncio
    async def test_orchestrate_turn_fallback_on_router_failure(self, mock_agents, session_context):
        """Tests orchestrate_turn: defaults to narrative_short when router raises exception."""
        specialist_response = SimpleNamespace(final_output="The story continues...")
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [Exception("Router crashed"), specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "What happens?", "user_001",
                mock_agents, session_context
            )
            
            assert result["intent_used"] == "narrative_short"


class TestOrchestrateJsonParsing:
    """Tests for orchestrate_turn JSON parsing behavior."""

    @pytest.fixture
    def mock_agents(self):
        return {
            "router": MagicMock(),
            "narrative_short": MagicMock(),
        }

    @pytest.fixture
    def session_context(self):
        return {"recent_recap": "Session ongoing."}

    @pytest.mark.asyncio
    async def test_orchestrate_turn_parses_bare_json(self, mock_agents, session_context):
        """Tests orchestrate_turn: correctly parses bare JSON (no markdown fences) from router."""
        router_response = SimpleNamespace(final_output='{"intent": "narrative_short", "confidence": "high"}')
        specialist_response = SimpleNamespace(final_output="Narrative response.")
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "Test", "user_001",
                mock_agents, session_context
            )
            
            assert result["intent_used"] == "narrative_short"

    @pytest.mark.asyncio
    async def test_orchestrate_turn_parses_fenced_json(self, mock_agents, session_context):
        """Tests orchestrate_turn: correctly parses fenced JSON from router as fallback."""
        router_response = SimpleNamespace(
            final_output='Some preamble\n```json\n{"intent": "qa_rules", "confidence": "medium"}\n```'
        )
        mock_agents["qa_rules"] = MagicMock()
        specialist_response = SimpleNamespace(final_output="Rules answer.")
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "Rules question", "user_001",
                mock_agents, session_context
            )
            
            assert result["intent_used"] == "qa_rules"

    @pytest.mark.asyncio
    async def test_orchestrate_turn_fallback_on_invalid_json(self, mock_agents, session_context):
        """Tests orchestrate_turn: defaults to narrative_short when router returns invalid JSON."""
        router_response = SimpleNamespace(final_output="I don't understand, here's some text")
        specialist_response = SimpleNamespace(final_output="Default response.")
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "Test", "user_001",
                mock_agents, session_context
            )
            
            assert result["intent_used"] == "narrative_short"


class TestOrchestrateResponse:
    """Tests for orchestrate_turn response structure."""

    @pytest.fixture
    def mock_agents(self):
        return {
            "router": MagicMock(),
            "narrative_short": MagicMock(),
        }

    @pytest.fixture
    def session_context(self):
        return {"recent_recap": ""}

    @pytest.mark.asyncio
    async def test_orchestrate_turn_returns_intent_used(self, mock_agents, session_context):
        """Tests orchestrate_turn: returned dict includes intent_used field."""
        router_response = SimpleNamespace(final_output='{"intent": "narrative_short"}')
        specialist_response = SimpleNamespace(final_output="Response text.")
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "Test", "user_001",
                mock_agents, session_context
            )
            
            assert "intent_used" in result
            assert "dm_response" in result

    @pytest.mark.asyncio
    async def test_orchestrate_turn_extracts_scene_patch(self, mock_agents, session_context):
        """Tests orchestrate_turn: extracts scene_state_patch from specialist response."""
        router_response = SimpleNamespace(final_output='{"intent": "narrative_short"}')
        specialist_response = SimpleNamespace(
            final_output='You enter the cave.\n```json\n{"scene_state_patch": {"location": "cave"}}\n```'
        )
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "I enter the cave", "user_001",
                mock_agents, session_context
            )
            
            assert "update_payload" in result
            assert result["update_payload"].get("scene_state_patch", {}).get("location") == "cave"

    @pytest.mark.asyncio
    async def test_orchestrate_turn_strips_json_from_dm_response(self, mock_agents, session_context):
        """Tests orchestrate_turn: JSON block is stripped from dm_response."""
        router_response = SimpleNamespace(final_output='{"intent": "narrative_short"}')
        specialist_response = SimpleNamespace(
            final_output='You see a dragon!\n```json\n{"turn_summary": "dragon appeared"}\n```'
        )
        
        with patch("orchestration.turn_router.Runner.run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [router_response, specialist_response]
            
            result = await orchestrate_turn(
                "camp_001", "sess_001", "I look around", "user_001",
                mock_agents, session_context
            )
            
            assert "You see a dragon!" in result["dm_response"]
            assert "```json" not in result["dm_response"]
