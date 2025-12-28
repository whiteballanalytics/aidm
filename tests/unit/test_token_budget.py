"""
Unit tests for the Token Budget Framework.

Tests the TokenBudget class which manages context sizes across agents.
"""

import os
import pytest
from unittest.mock import patch
from src.library.token_budget import TokenBudget


class TestCountTokens:
    """Tests for the count_tokens method."""
    
    def test_count_tokens_empty_string(self):
        """Tests count_tokens: returns 0 for empty string."""
        assert TokenBudget.count_tokens("") == 0
    
    def test_count_tokens_simple_text(self):
        """Tests count_tokens: returns positive count for simple text."""
        count = TokenBudget.count_tokens("Hello world")
        assert count > 0
        assert count < 10
    
    def test_count_tokens_longer_text(self):
        """Tests count_tokens: returns higher count for longer text."""
        short_count = TokenBudget.count_tokens("Hello")
        long_count = TokenBudget.count_tokens("Hello world, this is a longer sentence with more words.")
        assert long_count > short_count


class TestGetBudget:
    """Tests for the get_budget method."""
    
    def test_get_budget_known_agent(self):
        """Tests get_budget: returns defined budget for known agent type."""
        budget = TokenBudget.get_budget("router")
        assert budget == 1000
    
    def test_get_budget_unknown_agent(self):
        """Tests get_budget: returns default budget for unknown agent type."""
        budget = TokenBudget.get_budget("unknown_agent_type")
        assert budget == TokenBudget.DEFAULT_BUDGET
    
    def test_get_budget_env_override(self, monkeypatch):
        """Tests get_budget: environment variable overrides default budget."""
        monkeypatch.setenv("TOKEN_BUDGET_ROUTER", "500")
        budget = TokenBudget.get_budget("router")
        assert budget == 500
    
    def test_get_budget_invalid_env_uses_default(self, monkeypatch):
        """Tests get_budget: invalid environment variable falls back to default."""
        monkeypatch.setenv("TOKEN_BUDGET_ROUTER", "not_a_number")
        budget = TokenBudget.get_budget("router")
        assert budget == 1000


class TestTrimToBudget:
    """Tests for the trim_to_budget method."""
    
    def test_trim_to_budget_under_limit(self):
        """Tests trim_to_budget: returns original text when under limit."""
        text = "Short text"
        result = TokenBudget.trim_to_budget(text, 100)
        assert result == text
    
    def test_trim_to_budget_over_limit(self):
        """Tests trim_to_budget: trims text when over limit."""
        long_text = " ".join(["word"] * 1000)
        result = TokenBudget.trim_to_budget(long_text, 50)
        result_tokens = TokenBudget.count_tokens(result)
        assert result_tokens <= 50
    
    def test_trim_to_budget_preserves_end_by_default(self):
        """Tests trim_to_budget: preserves end of text by default."""
        text = "START " + " ".join(["middle"] * 100) + " END"
        result = TokenBudget.trim_to_budget(text, 20)
        assert "END" in result
    
    def test_trim_to_budget_preserve_beginning(self):
        """Tests trim_to_budget: can preserve beginning instead of end."""
        text = "START " + " ".join(["middle"] * 100) + " END"
        result = TokenBudget.trim_to_budget(text, 20, preserve_end=False)
        assert "START" in result
    
    def test_trim_to_budget_empty_string(self):
        """Tests trim_to_budget: handles empty string gracefully."""
        result = TokenBudget.trim_to_budget("", 100)
        assert result == ""


class TestValidateContext:
    """Tests for the validate_context method."""
    
    def test_validate_context_under_budget(self):
        """Tests validate_context: returns valid for context under budget."""
        is_valid, metadata = TokenBudget.validate_context("router", "Short text")
        assert is_valid is True
        assert metadata["over_budget_by"] == 0
        assert metadata["usage_percent"] < 100
    
    def test_validate_context_over_budget(self):
        """Tests validate_context: returns invalid for context over budget."""
        long_text = " ".join(["word"] * 5000)
        is_valid, metadata = TokenBudget.validate_context("router", long_text)
        assert is_valid is False
        assert metadata["over_budget_by"] > 0
        assert metadata["usage_percent"] > 100
    
    def test_validate_context_returns_metadata(self):
        """Tests validate_context: returns complete metadata dictionary."""
        is_valid, metadata = TokenBudget.validate_context("gameplay", "Test context")
        assert "agent_type" in metadata
        assert "token_count" in metadata
        assert "budget" in metadata
        assert "usage_percent" in metadata
        assert "over_budget_by" in metadata
        assert metadata["agent_type"] == "gameplay"


class TestEnforceBudget:
    """Tests for the enforce_budget method."""
    
    def test_enforce_budget_under_limit(self):
        """Tests enforce_budget: returns original context when under budget."""
        context = "Short context"
        result, metadata = TokenBudget.enforce_budget("router", context, log_trimming=False)
        assert result == context
        assert metadata["was_trimmed"] is False
    
    def test_enforce_budget_trims_when_over(self):
        """Tests enforce_budget: trims context when over budget."""
        long_context = " ".join(["word"] * 5000)
        result, metadata = TokenBudget.enforce_budget("router", long_context, log_trimming=False)
        assert len(result) < len(long_context)
        assert metadata["was_trimmed"] is True
    
    def test_enforce_budget_logs_trimming(self, capsys):
        """Tests enforce_budget: prints warning when trimming occurs."""
        long_context = " ".join(["word"] * 5000)
        TokenBudget.enforce_budget("router", long_context, log_trimming=True)
        captured = capsys.readouterr()
        assert "[TOKEN_BUDGET]" in captured.out
        assert "exceeded budget" in captured.out
    
    def test_enforce_budget_metadata_after_trim(self):
        """Tests enforce_budget: metadata reflects trimmed state."""
        long_context = " ".join(["word"] * 5000)
        result, metadata = TokenBudget.enforce_budget("router", long_context, log_trimming=False)
        assert metadata["was_trimmed"] is True
        assert "original_token_count" in metadata
        assert metadata["original_token_count"] > metadata["budget"]


class TestBudgetValues:
    """Tests for the default budget values."""
    
    def test_all_agent_types_have_budgets(self):
        """Tests BUDGETS: all expected agent types have defined budgets."""
        expected_agents = [
            "router", "narrative_short", "narrative_long", 
            "qa_rules", "qa_situation", "npc_dialogue",
            "combat_designer", "travel", "gameplay"
        ]
        for agent in expected_agents:
            assert agent in TokenBudget.BUDGETS
            assert TokenBudget.BUDGETS[agent] > 0
    
    def test_router_has_smallest_budget(self):
        """Tests BUDGETS: router has the smallest budget (minimal context needed)."""
        router_budget = TokenBudget.BUDGETS["router"]
        for agent, budget in TokenBudget.BUDGETS.items():
            if agent != "router":
                assert budget >= router_budget
