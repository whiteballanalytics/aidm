"""
Pydantic response models for structured agent outputs.

These models are used with OpenAI's structured outputs feature to ensure
agents return valid, predictable JSON responses.
"""

from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RouterIntent(BaseModel):
    """
    Response model for the router agent's intent classification.
    
    The router classifies player input into specific intent categories
    to route to the appropriate specialist agent.
    """
    intent: Literal[
        "narrative_short",
        "narrative_long", 
        "qa_situation",
        "qa_rules",
        "npc_dialogue",
        "combat_designer",
        "travel",
        "gameplay"
    ] = Field(
        description="The classified intent type for routing to specialist agent"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="Confidence level in the classification"
    )
    note: str = Field(
        default="",
        description="Optional note explaining the classification decision"
    )


class ScenePatch(BaseModel):
    """
    Response model for scene state updates from specialist agents.
    
    Contains partial updates to the current scene state that should
    be merged with the existing state.
    """
    location: Optional[str] = Field(
        default=None,
        description="Updated location name if the scene location changed"
    )
    npcs_present: Optional[List[str]] = Field(
        default=None,
        description="List of NPC names currently present in the scene"
    )
    active_threats: Optional[List[str]] = Field(
        default=None,
        description="List of active threats or dangers in the scene"
    )
    time_of_day: Optional[Literal["dawn", "morning", "midday", "afternoon", "dusk", "evening", "night", "midnight"]] = Field(
        default=None,
        description="Current time of day if it changed"
    )
    weather: Optional[str] = Field(
        default=None,
        description="Current weather conditions if they changed"
    )
    mood: Optional[str] = Field(
        default=None,
        description="Overall mood or atmosphere of the scene"
    )
    recent_events: Optional[List[str]] = Field(
        default=None,
        description="Brief list of recent significant events"
    )
    hostile_environment: Optional[bool] = Field(
        default=None,
        description="Whether the current location is hostile territory (dungeon, enemy base, dangerous wilderness, etc.)"
    )
    combat_plan: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Prepared combat encounter plan for potential combat scenarios"
    )


class MemoryWrite(BaseModel):
    """
    Model for a single memory entry to be stored in the campaign memory.
    """
    content: str = Field(
        description="The memory content to store"
    )
    importance: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="How important this memory is for future recall"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing and searching the memory"
    )


class DiceRollResult(BaseModel):
    """
    Response model for dice roll outcomes.
    """
    roll_type: str = Field(
        description="Type of roll (e.g., 'attack', 'saving throw', 'skill check')"
    )
    dice_expression: str = Field(
        description="The dice expression rolled (e.g., '1d20+5')"
    )
    total: int = Field(
        description="The total result of the roll"
    )
    individual_rolls: List[int] = Field(
        default_factory=list,
        description="Individual die results before modifiers"
    )
    success: Optional[bool] = Field(
        default=None,
        description="Whether the roll was a success (if applicable)"
    )
    narrative: str = Field(
        default="",
        description="Narrative description of the roll outcome"
    )
