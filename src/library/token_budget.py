"""
Token Budget Framework for managing context sizes across agents.

This module provides centralized token management to:
- Prevent runaway API costs
- Ensure predictable LLM latency
- Enable auditable context sizing for debugging
"""

import os
import tiktoken
from typing import Tuple, Dict, Any


class TokenBudget:
    """
    Centralized token management across all agent contexts.
    Enforces hard limits per agent type to prevent cost explosion and timeouts.
    """
    
    BUDGETS: Dict[str, int] = {
        "router": 1000,
        "narrative_short": 6000,
        "narrative_long": 8000,
        "qa_rules": 5000,
        "qa_situation": 5000,
        "npc_dialogue": 6000,
        "combat_designer": 8000,
        "travel": 6000,
        "gameplay": 7000,
    }
    
    DEFAULT_BUDGET = 6000
    
    _encoder_cache: Dict[str, Any] = {}
    
    @classmethod
    def get_budget(cls, agent_type: str) -> int:
        """
        Get the token budget for an agent type.
        
        Checks for environment variable override first (e.g., TOKEN_BUDGET_ROUTER=500),
        then falls back to the default budget for that agent type.
        """
        env_key = f"TOKEN_BUDGET_{agent_type.upper()}"
        env_value = os.environ.get(env_key)
        if env_value:
            try:
                return int(env_value)
            except ValueError:
                pass
        return cls.BUDGETS.get(agent_type, cls.DEFAULT_BUDGET)
    
    @classmethod
    def _get_encoder(cls, model: str = "gpt-4o-mini") -> Any:
        """Get or create a cached encoder for the model."""
        if model not in cls._encoder_cache:
            try:
                cls._encoder_cache[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                cls._encoder_cache[model] = tiktoken.get_encoding("cl100k_base")
        return cls._encoder_cache[model]
    
    @classmethod
    def count_tokens(cls, text: str, model: str = "gpt-4o-mini") -> int:
        """
        Count the number of tokens in a text string.
        
        Args:
            text: The text to count tokens for
            model: The model to use for tokenization (default: gpt-4o-mini)
        
        Returns:
            Number of tokens in the text
        """
        if not text:
            return 0
        encoder = cls._get_encoder(model)
        return len(encoder.encode(text))
    
    @classmethod
    def trim_to_budget(
        cls, 
        text: str, 
        max_tokens: int, 
        model: str = "gpt-4o-mini",
        preserve_end: bool = True
    ) -> str:
        """
        Trim text to fit within a token budget.
        
        By default, preserves the end of the text (most recent content),
        which is typically more relevant for D&D gameplay context.
        
        Args:
            text: The text to trim
            max_tokens: Maximum number of tokens allowed
            model: The model to use for tokenization
            preserve_end: If True, keep the end of text; if False, keep the beginning
        
        Returns:
            Trimmed text that fits within the budget
        """
        if not text:
            return text
        
        encoder = cls._get_encoder(model)
        tokens = encoder.encode(text)
        
        if len(tokens) <= max_tokens:
            return text
        
        if preserve_end:
            trimmed_tokens = tokens[-max_tokens:]
        else:
            trimmed_tokens = tokens[:max_tokens]
        
        return encoder.decode(trimmed_tokens)
    
    @classmethod
    def validate_context(
        cls, 
        agent_type: str, 
        context: str, 
        model: str = "gpt-4o-mini"
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate that context fits within the budget for an agent type.
        
        Args:
            agent_type: The type of agent (e.g., "router", "gameplay")
            context: The context string to validate
            model: The model to use for tokenization
        
        Returns:
            Tuple of (is_valid, metadata_dict) where metadata includes:
            - agent_type: The agent type checked
            - token_count: Actual token count
            - budget: The budget limit
            - usage_percent: Percentage of budget used
            - over_budget_by: Number of tokens over budget (0 if within budget)
        """
        budget = cls.get_budget(agent_type)
        token_count = cls.count_tokens(context, model)
        
        is_valid = token_count <= budget
        over_budget_by = max(0, token_count - budget)
        
        return (is_valid, {
            "agent_type": agent_type,
            "token_count": token_count,
            "budget": budget,
            "usage_percent": (token_count / budget) * 100 if budget > 0 else 0,
            "over_budget_by": over_budget_by,
        })
    
    @classmethod
    def enforce_budget(
        cls,
        agent_type: str,
        context: str,
        model: str = "gpt-4o-mini",
        log_trimming: bool = True
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Enforce token budget on context, trimming if necessary.
        
        This is the main entry point for context budget enforcement.
        It validates the context and trims it if over budget.
        
        Args:
            agent_type: The type of agent
            context: The context string
            model: The model to use for tokenization
            log_trimming: Whether to print a warning when trimming occurs
        
        Returns:
            Tuple of (possibly_trimmed_context, metadata_dict)
        """
        is_valid, metadata = cls.validate_context(agent_type, context, model)
        
        if is_valid:
            metadata["was_trimmed"] = False
            return (context, metadata)
        
        budget = cls.get_budget(agent_type)
        trimmed_context = cls.trim_to_budget(context, budget, model)
        
        if log_trimming:
            print(f"[TOKEN_BUDGET] {agent_type} context exceeded budget: "
                  f"{metadata['token_count']} tokens > {budget} budget "
                  f"({metadata['usage_percent']:.1f}%). Trimmed to fit.")
        
        metadata["was_trimmed"] = True
        metadata["original_token_count"] = metadata["token_count"]
        metadata["token_count"] = budget
        metadata["usage_percent"] = 100.0
        
        return (trimmed_context, metadata)
