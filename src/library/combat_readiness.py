"""
Combat readiness checker for the D&D AI Dungeon Master.

This module evaluates whether the current combat plan is still valid
given the current scene state, and determines if an update is needed.
"""

import logging
from typing import Optional, Literal
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CombatPlanStatus(BaseModel):
    """Result of combat plan validity check."""
    action: Literal["keep", "clear", "update"]
    reason: str


def get_npc_set(participants: list[str]) -> set[str]:
    """Extract NPC names from participants list, normalized to lowercase."""
    return {p.lower().strip() for p in participants if p}


def check_combat_plan_validity(
    participants: list[str],
    specific_location: str,
    hostile_environment: bool,
    combat_plan: Optional[dict]
) -> CombatPlanStatus:
    """
    Check if the current combat plan is still valid for the scene.
    
    Decision logic:
    1. No NPCs AND not hostile environment → clear plan (no combat possible)
    2. No existing plan AND (NPCs present OR hostile) → update needed
    3. Existing plan but NPCs changed → update needed
    4. Existing plan but location significantly changed → update needed
    5. Otherwise → keep current plan
    
    Args:
        participants: List of NPCs/entities currently in the scene
        specific_location: Current location name
        hostile_environment: Whether the environment is hostile
        combat_plan: Existing combat plan dict (or None)
    
    Returns:
        CombatPlanStatus with action ("keep", "clear", "update") and reason
    """
    has_npcs = len(participants) > 0
    has_plan = combat_plan is not None
    
    if not has_npcs and not hostile_environment:
        if has_plan:
            logger.info("Clearing combat plan: no NPCs and safe environment")
            return CombatPlanStatus(
                action="clear",
                reason="No NPCs present and environment is not hostile"
            )
        return CombatPlanStatus(
            action="keep",
            reason="No plan needed - no NPCs and safe environment"
        )
    
    if not has_plan:
        reason = []
        if has_npcs:
            reason.append(f"NPCs present: {participants[:3]}")
        if hostile_environment:
            reason.append("hostile environment")
        logger.info(f"Combat plan update needed: {', '.join(reason)}")
        return CombatPlanStatus(
            action="update",
            reason=f"No combat plan exists but {' and '.join(reason)}"
        )
    
    plan_npcs = get_npc_set(combat_plan.get("prepared_for_npcs", []))
    plan_location = combat_plan.get("prepared_for_location", "")
    current_npcs = get_npc_set(participants)
    
    new_npcs = current_npcs - plan_npcs
    if new_npcs:
        logger.info(f"Combat plan update needed: new NPCs detected: {new_npcs}")
        return CombatPlanStatus(
            action="update",
            reason=f"New NPCs entered the scene: {list(new_npcs)[:3]}"
        )
    
    left_npcs = plan_npcs - current_npcs
    if left_npcs and len(left_npcs) > len(plan_npcs) // 2:
        logger.info(f"Combat plan update needed: significant NPCs left: {left_npcs}")
        return CombatPlanStatus(
            action="update",
            reason=f"Significant NPCs left the scene: {list(left_npcs)[:3]}"
        )
    
    if plan_location and specific_location:
        if plan_location.lower() != specific_location.lower():
            logger.info(f"Combat plan update needed: location changed from '{plan_location}' to '{specific_location}'")
            return CombatPlanStatus(
                action="update",
                reason=f"Location changed from '{plan_location}' to '{specific_location}'"
            )
    
    return CombatPlanStatus(
        action="keep",
        reason="Combat plan still valid for current NPCs and location"
    )


def should_prepare_combat(
    participants: list[str],
    hostile_environment: bool,
    combat_plan: Optional[dict]
) -> bool:
    """
    Simple check: should we trigger combat_designer?
    
    Returns True if:
    - There are NPCs or we're in hostile territory
    - AND we don't have a valid plan
    """
    has_threat = len(participants) > 0 or hostile_environment
    has_plan = combat_plan is not None
    return has_threat and not has_plan
