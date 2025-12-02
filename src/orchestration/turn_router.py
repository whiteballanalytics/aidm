"""
Multi-agent orchestration for DM responses.

This module routes player input to specialized agents based on intent classification.
"""

import json
import os
from typing import Optional, Dict, Any
from agents import Runner, Agent
from library.logginghooks import LocalRunLogger
from library.eval_logger import log_router_prompt
from src.game_engine import extract_update_payload, strip_json_block, extract_narrative_from_runresult


def build_agent_context(
    agent_type: str,
    session_context: Dict[str, Any],
    user_input: str
) -> str:
    """
    Build context tailored to each agent type.
    
    Different agents need different levels of context, for example:
    - router needs minimal context (recent recap only) to classify intent quickly
    - qa_situation may need more context to accurately understand the situation
    
    Args:
        agent_type: Type of agent requesting context (e.g., "router", "narrative_short")
        session_context: Dictionary containing various context objects
        user_input: The player's input text
    
    Returns:
        Formatted context string appropriate for the agent type
    """
    recent_recap = session_context.get("recent_recap", "")
    
    if agent_type == "router":
        # Router only needs recent recap to classify intent quickly
        return recent_recap or "(No recent history)"
    
    elif agent_type in ("narrative_short", "narrative_long"):
        # Narrative agents need full DM context
        return f"""{session_context}

Player: {user_input}"""
    
    elif agent_type == "qa_rules":
        # Rules QA agents need full DM context
        return f"""{session_context}

Player: {user_input}"""
    
    elif agent_type == "npc_dialogue":
        # NPC Dialogue needs full context to understand the NPC's personality and the scene
        return f"""{session_context}

Player: {user_input}"""
    
    elif agent_type == "combat_designer":
        # Combat Designer needs full context to design appropriate encounters
        return f"""{session_context}

Player: {user_input}"""
    
    elif agent_type == "qa_situation":
        # Situation QA agents need full DM context
        return f"""{session_context}

Player: {user_input}"""
    
    elif agent_type == "travel":
        # Travel agents need full DM context
        return f"""{session_context}

Player: {user_input}"""
    
    elif agent_type == "gameplay":
        # Gameplay agents need full DM context
        # Debatable - we should try to make this more efficient later
        return f"""{session_context}

Player: {user_input}"""
    
    else:
        # Default: return full DM context
        return f"""{session_context}

Player: {user_input}"""


async def orchestrate_turn(
    campaign_id: str,
    session_id: str,
    user_input: str,
    user_id: str,
    agents: Dict[str, Any],
    session_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Orchestrate a player turn using multi-agent routing.
    
    Args:
        campaign_id: Campaign identifier
        session_id: Session identifier
        user_input: Player's input text
        user_id: User identifier
        agents: Dictionary of all initialized agents
        session_context: Context including session_plan, scene_state, recent_recap
    
    Returns:
        Dict containing dm_response, scene_state updates, memory_writes, etc.
    """
    
    # Step 1: Route to appropriate agent
    router_agent = agents["router"]
    
    # Build router-specific context (minimal: only recent recap)
    router_context = build_agent_context("router", session_context, user_input)
    
    # Ask router to classify intent
    router_prompt = f"""Classify this player input:

{user_input}

Context (recent events):
{router_context}...
"""
    
    # Log full router prompt for eval capture (when enabled)
    log_router_prompt(router_prompt, user_input, session_id)
    
    try:
        router_result = await Runner.run(router_agent, router_prompt, hooks=LocalRunLogger())
    except Exception as e:
        # Fallback to narrative_short on router failure
        print(f"Router failed: {e}, defaulting to narrative_short")
        intent = "narrative_short"
        confidence = "low"
        note = "Router failed, defaulting to short narrative"
    else:
        # Parse router response
        router_text = (
            getattr(router_result, "final_output", None)
            or getattr(router_result, "output_text", None)
            or getattr(router_result, "content", None)
            or str(router_result)
        )
        
        # Router returns bare JSON (not fenced), so try direct parsing first
        router_data = None
        
        # Try to parse as direct JSON
        try:
            # Clean up the text and try to parse
            cleaned_text = router_text.strip()
            router_data = json.loads(cleaned_text)
        except json.JSONDecodeError:
            # Fallback to fenced block extraction if direct parsing fails
            router_data = extract_update_payload(router_text)
        
        # Log raw router output for debugging
        print(f"[ROUTER RAW OUTPUT] {router_text[:200]}...")
        
        if not router_data or "intent" not in router_data:
            # Fallback if router doesn't return valid JSON
            intent = "narrative_short"
            confidence = "low"
            note = f"Router returned invalid format (got: {router_text[:100]}), defaulting to short narrative"
        else:
            intent = router_data.get("intent", "narrative_short")
            confidence = router_data.get("confidence", "medium")
            note = router_data.get("note", "")
    
    # Log routing decision
    print(f"[ROUTER] Intent: {intent}, Confidence: {confidence}, Note: {note}")
    
    # Step 2: Select and run the appropriate specialist agent
    agent_map = {
        "narrative_short": agents.get("narrative_short"),
        "narrative_long": agents.get("narrative_long"),
        "qa_situation": agents.get("qa_situation"),
        "qa_rules": agents.get("qa_rules"),
        "npc_dialogue": agents.get("npc_dialogue"),
        "combat_designer": agents.get("combat_designer"),
        "travel": agents.get("travel"),
        "gameplay": agents.get("gameplay")
    }
    
    specialist_agent = agent_map.get(intent)
    if not specialist_agent:
        # Fallback to narrative_short if agent not found
        print(f"Agent for intent '{intent}' not found, using narrative_short")
        specialist_agent = agents["narrative_short"]
        intent = "narrative_short"
    
    # Build specialist-specific context based on agent type
    specialist_input = build_agent_context(intent, session_context, user_input)
    
    # Run specialist agent
    try:
        result = await Runner.run(specialist_agent, specialist_input, hooks=LocalRunLogger())
    except Exception as e:
        raise Exception(f"Error from {intent} agent: {e}")
    
    # Parse specialist response
    specialist_response_raw = (
        getattr(result, "final_output", None)
        or getattr(result, "output_text", None)
        or getattr(result, "content", None)
        or str(result)
    )
    
    # Extract narrative and update payload
    specialist_response_clean = extract_narrative_from_runresult(specialist_response_raw)
    update_payload = extract_update_payload(specialist_response_clean) or {}
    dm_response = strip_json_block(specialist_response_clean)
    
    # Return structured response
    return {
        "dm_response": dm_response,
        "update_payload": update_payload,
        "intent_used": intent,
        "routing_note": note
    }
