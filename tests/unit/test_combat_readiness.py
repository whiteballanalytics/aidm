"""
Unit tests for the combat readiness checker.

Tests cover the check_combat_plan_validity function which determines
if the current combat plan is still valid given scene state changes.
"""

import pytest
from src.library.combat_readiness import (
    check_combat_plan_validity,
    get_npc_set,
    should_prepare_combat,
    CombatPlanStatus
)


class TestGetNpcSet:
    """Tests for the get_npc_set helper function."""

    def test_get_npc_set_normalizes_to_lowercase(self):
        """get_npc_set: converts NPC names to lowercase for comparison."""
        result = get_npc_set(["Goblin Chief", "ORC WARRIOR", "skeleton"])
        assert result == {"goblin chief", "orc warrior", "skeleton"}

    def test_get_npc_set_strips_whitespace(self):
        """get_npc_set: strips leading/trailing whitespace from names."""
        result = get_npc_set(["  Goblin  ", "Orc ", " Skeleton"])
        assert result == {"goblin", "orc", "skeleton"}

    def test_get_npc_set_filters_empty_strings(self):
        """get_npc_set: filters out empty strings from the set."""
        result = get_npc_set(["Goblin", "", "Orc", ""])
        assert result == {"goblin", "orc"}

    def test_get_npc_set_empty_list(self):
        """get_npc_set: returns empty set for empty input list."""
        result = get_npc_set([])
        assert result == set()


class TestCheckCombatPlanValidity:
    """Tests for the check_combat_plan_validity function."""

    def test_no_npcs_safe_environment_no_plan_keep(self):
        """check_combat_plan_validity: no NPCs + safe + no plan = keep (nothing needed)."""
        result = check_combat_plan_validity(
            participants=[],
            specific_location="Town Square",
            hostile_environment=False,
            combat_plan=None
        )
        assert result.action == "keep"

    def test_no_npcs_safe_environment_has_plan_clear(self):
        """check_combat_plan_validity: no NPCs + safe + has plan = clear the plan."""
        result = check_combat_plan_validity(
            participants=[],
            specific_location="Town Square",
            hostile_environment=False,
            combat_plan={"encounter_name": "Old Fight", "prepared_for_npcs": ["goblin"]}
        )
        assert result.action == "clear"

    def test_has_npcs_no_plan_needs_update(self):
        """check_combat_plan_validity: NPCs present + no plan = update needed."""
        result = check_combat_plan_validity(
            participants=["Goblin Scout", "Orc Guard"],
            specific_location="Dark Cave",
            hostile_environment=False,
            combat_plan=None
        )
        assert result.action == "update"
        assert "NPCs present" in result.reason

    def test_hostile_environment_no_npcs_no_plan_needs_update(self):
        """check_combat_plan_validity: hostile environment + no plan = update needed."""
        result = check_combat_plan_validity(
            participants=[],
            specific_location="Abandoned Dungeon",
            hostile_environment=True,
            combat_plan=None
        )
        assert result.action == "update"
        assert "hostile environment" in result.reason

    def test_hostile_environment_no_npcs_has_plan_keep(self):
        """check_combat_plan_validity: hostile + no NPCs + has plan = keep if location same."""
        result = check_combat_plan_validity(
            participants=[],
            specific_location="Abandoned Dungeon",
            hostile_environment=True,
            combat_plan={
                "encounter_name": "Trap Room",
                "prepared_for_npcs": [],
                "prepared_for_location": "Abandoned Dungeon"
            }
        )
        assert result.action == "keep"

    def test_new_npc_triggers_update(self):
        """check_combat_plan_validity: new NPC in scene triggers update."""
        result = check_combat_plan_validity(
            participants=["Goblin Scout", "Orc Chieftain"],
            specific_location="Dark Cave",
            hostile_environment=True,
            combat_plan={
                "encounter_name": "Cave Fight",
                "prepared_for_npcs": ["goblin scout"],
                "prepared_for_location": "Dark Cave"
            }
        )
        assert result.action == "update"
        assert "orc chieftain" in result.reason.lower()

    def test_location_change_triggers_update(self):
        """check_combat_plan_validity: location change triggers update."""
        result = check_combat_plan_validity(
            participants=["Goblin Scout"],
            specific_location="Underground River",
            hostile_environment=True,
            combat_plan={
                "encounter_name": "Cave Fight",
                "prepared_for_npcs": ["goblin scout"],
                "prepared_for_location": "Dark Cave Entrance"
            }
        )
        assert result.action == "update"
        assert "location changed" in result.reason.lower()

    def test_minor_npc_departure_keeps_plan(self):
        """check_combat_plan_validity: minor NPC departures don't trigger update."""
        result = check_combat_plan_validity(
            participants=["Orc Chief", "Orc Guard", "Orc Shaman"],
            specific_location="Orc Camp",
            hostile_environment=True,
            combat_plan={
                "encounter_name": "Orc Attack",
                "prepared_for_npcs": ["orc chief", "orc guard", "orc shaman", "orc scout"],
                "prepared_for_location": "Orc Camp"
            }
        )
        assert result.action == "keep"

    def test_significant_npc_departure_triggers_update(self):
        """check_combat_plan_validity: more than half NPCs leaving triggers update."""
        result = check_combat_plan_validity(
            participants=["Orc Chief"],
            specific_location="Orc Camp",
            hostile_environment=True,
            combat_plan={
                "encounter_name": "Orc Attack",
                "prepared_for_npcs": ["orc chief", "orc guard", "orc shaman", "orc scout"],
                "prepared_for_location": "Orc Camp"
            }
        )
        assert result.action == "update"

    def test_same_npcs_same_location_keeps_plan(self):
        """check_combat_plan_validity: matching NPCs and location = keep plan."""
        result = check_combat_plan_validity(
            participants=["Goblin Scout", "Goblin Archer"],
            specific_location="Forest Clearing",
            hostile_environment=True,
            combat_plan={
                "encounter_name": "Goblin Ambush",
                "prepared_for_npcs": ["goblin scout", "goblin archer"],
                "prepared_for_location": "Forest Clearing"
            }
        )
        assert result.action == "keep"

    def test_case_insensitive_npc_matching(self):
        """check_combat_plan_validity: NPC matching is case-insensitive."""
        result = check_combat_plan_validity(
            participants=["GOBLIN SCOUT", "goblin archer"],
            specific_location="Forest Clearing",
            hostile_environment=True,
            combat_plan={
                "encounter_name": "Goblin Ambush",
                "prepared_for_npcs": ["Goblin Scout", "Goblin Archer"],
                "prepared_for_location": "Forest Clearing"
            }
        )
        assert result.action == "keep"


class TestShouldPrepareCombat:
    """Tests for the should_prepare_combat helper function."""

    def test_no_threat_no_plan_returns_false(self):
        """should_prepare_combat: no NPCs + safe + no plan = False."""
        result = should_prepare_combat(
            participants=[],
            hostile_environment=False,
            combat_plan=None
        )
        assert result is False

    def test_npcs_no_plan_returns_true(self):
        """should_prepare_combat: NPCs + no plan = True."""
        result = should_prepare_combat(
            participants=["Goblin"],
            hostile_environment=False,
            combat_plan=None
        )
        assert result is True

    def test_hostile_no_plan_returns_true(self):
        """should_prepare_combat: hostile + no plan = True."""
        result = should_prepare_combat(
            participants=[],
            hostile_environment=True,
            combat_plan=None
        )
        assert result is True

    def test_npcs_with_plan_returns_false(self):
        """should_prepare_combat: NPCs + has plan = False."""
        result = should_prepare_combat(
            participants=["Goblin"],
            hostile_environment=False,
            combat_plan={"encounter_name": "Test"}
        )
        assert result is False


class TestCombatPlanStatusModel:
    """Tests for the CombatPlanStatus Pydantic model."""

    def test_status_model_serializes(self):
        """CombatPlanStatus: model serializes to dict correctly."""
        status = CombatPlanStatus(action="update", reason="New NPCs detected")
        data = status.model_dump()
        assert data["action"] == "update"
        assert data["reason"] == "New NPCs detected"

    def test_status_model_valid_actions(self):
        """CombatPlanStatus: accepts all valid action types."""
        keep = CombatPlanStatus(action="keep", reason="Test")
        clear = CombatPlanStatus(action="clear", reason="Test")
        update = CombatPlanStatus(action="update", reason="Test")
        assert keep.action == "keep"
        assert clear.action == "clear"
        assert update.action == "update"
