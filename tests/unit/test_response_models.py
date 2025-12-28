"""
Unit tests for Pydantic response models used with structured outputs.

Tests validation, serialization, and field constraints for agent response models.
"""

import pytest
from pydantic import ValidationError
from src.library.response_models import (
    RouterIntent,
    ScenePatch,
    MemoryWrite,
    DiceRollResult,
)


class TestRouterIntent:
    """Tests for the RouterIntent response model."""
    
    def test_router_intent_valid_creation(self):
        """Tests RouterIntent: accepts valid intent with all fields."""
        intent = RouterIntent(
            intent="narrative_short",
            confidence="high",
            note="Player wants to explore"
        )
        assert intent.intent == "narrative_short"
        assert intent.confidence == "high"
        assert intent.note == "Player wants to explore"
    
    def test_router_intent_defaults(self):
        """Tests RouterIntent: uses default values for optional fields."""
        intent = RouterIntent(intent="qa_rules")
        assert intent.confidence == "medium"
        assert intent.note == ""
    
    def test_router_intent_all_valid_intents(self):
        """Tests RouterIntent: accepts all valid intent types."""
        valid_intents = [
            "narrative_short", "narrative_long", "qa_situation",
            "qa_rules", "npc_dialogue", "combat_designer",
            "travel", "gameplay"
        ]
        for intent_type in valid_intents:
            intent = RouterIntent(intent=intent_type)
            assert intent.intent == intent_type
    
    def test_router_intent_invalid_intent_rejected(self):
        """Tests RouterIntent: rejects invalid intent type."""
        with pytest.raises(ValidationError):
            RouterIntent(intent="invalid_intent")
    
    def test_router_intent_invalid_confidence_rejected(self):
        """Tests RouterIntent: rejects invalid confidence level."""
        with pytest.raises(ValidationError):
            RouterIntent(intent="narrative_short", confidence="very_high")
    
    def test_router_intent_serialization(self):
        """Tests RouterIntent: serializes to dict correctly."""
        intent = RouterIntent(
            intent="gameplay",
            confidence="low",
            note="Dice roll needed"
        )
        data = intent.model_dump()
        assert data["intent"] == "gameplay"
        assert data["confidence"] == "low"
        assert data["note"] == "Dice roll needed"


class TestScenePatch:
    """Tests for the ScenePatch response model."""
    
    def test_scene_patch_empty(self):
        """Tests ScenePatch: accepts empty patch with all None values."""
        patch = ScenePatch()
        assert patch.location is None
        assert patch.npcs_present is None
        assert patch.active_threats is None
    
    def test_scene_patch_partial_update(self):
        """Tests ScenePatch: accepts partial updates."""
        patch = ScenePatch(
            location="Tavern",
            npcs_present=["Barkeep", "Mysterious Stranger"]
        )
        assert patch.location == "Tavern"
        assert patch.npcs_present == ["Barkeep", "Mysterious Stranger"]
        assert patch.weather is None
    
    def test_scene_patch_time_of_day_valid(self):
        """Tests ScenePatch: accepts valid time_of_day values."""
        valid_times = ["dawn", "morning", "midday", "afternoon", "dusk", "evening", "night", "midnight"]
        for time in valid_times:
            patch = ScenePatch(time_of_day=time)
            assert patch.time_of_day == time
    
    def test_scene_patch_time_of_day_invalid(self):
        """Tests ScenePatch: rejects invalid time_of_day value."""
        with pytest.raises(ValidationError):
            ScenePatch(time_of_day="noon")
    
    def test_scene_patch_full_update(self):
        """Tests ScenePatch: accepts complete scene update."""
        patch = ScenePatch(
            location="Dragon's Lair",
            npcs_present=["Ancient Red Dragon"],
            active_threats=["Dragon breath", "Collapsing ceiling"],
            time_of_day="night",
            weather="Ash and smoke",
            mood="Terrifying",
            recent_events=["Party entered lair", "Dragon awoke"]
        )
        assert patch.location == "Dragon's Lair"
        assert len(patch.active_threats) == 2
        assert len(patch.recent_events) == 2


class TestMemoryWrite:
    """Tests for the MemoryWrite response model."""
    
    def test_memory_write_minimal(self):
        """Tests MemoryWrite: accepts minimal memory entry."""
        memory = MemoryWrite(content="Player saved the village")
        assert memory.content == "Player saved the village"
        assert memory.importance == "medium"
        assert memory.tags == []
    
    def test_memory_write_full(self):
        """Tests MemoryWrite: accepts memory with all fields."""
        memory = MemoryWrite(
            content="Player made a deal with the demon lord",
            importance="critical",
            tags=["demon", "pact", "plot"]
        )
        assert memory.importance == "critical"
        assert "demon" in memory.tags
    
    def test_memory_write_invalid_importance(self):
        """Tests MemoryWrite: rejects invalid importance level."""
        with pytest.raises(ValidationError):
            MemoryWrite(content="Test", importance="very_important")


class TestDiceRollResult:
    """Tests for the DiceRollResult response model."""
    
    def test_dice_roll_minimal(self):
        """Tests DiceRollResult: accepts minimal roll result."""
        roll = DiceRollResult(
            roll_type="attack",
            dice_expression="1d20+5",
            total=18
        )
        assert roll.roll_type == "attack"
        assert roll.total == 18
        assert roll.success is None
    
    def test_dice_roll_full(self):
        """Tests DiceRollResult: accepts complete roll result."""
        roll = DiceRollResult(
            roll_type="saving throw",
            dice_expression="1d20+3",
            total=15,
            individual_rolls=[12],
            success=True,
            narrative="You narrowly dodge the fireball!"
        )
        assert roll.success is True
        assert roll.individual_rolls == [12]
        assert "fireball" in roll.narrative
