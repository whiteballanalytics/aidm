# Game engine module for D&D AI Dungeon Master
# Extracted from main.py to support both console and web interfaces

import asyncio
import os
import random
import re
import json
import time
import textwrap
from pathlib import Path
from typing import Any, Optional, Literal
from uuid import uuid4

# Third-party imports
from dotenv import load_dotenv
import openai
from openai import OpenAI
from agents import Agent, Runner, function_tool
from agents import set_tracing_export_api_key
from agents.tracing.setup import GLOBAL_TRACE_PROVIDER
from pydantic import BaseModel, Field

# Project-local imports
from library.vectorstores import LoreSearch, MemorySearch, get_campaign_mem_store
from library.session_tools import SessionReview
from library.prompts import load_prompt
from library.logginghooks import LocalRunLogger, jl_write

# Load environment
load_dotenv()

# Configuration constants
MEM_REGISTRY_PATH = "config/memorystores.json" # names of vector stores associated with each campaign
MEM_MIRROR_PATH = "mirror/mem_mirror"          # local cache of memories in the vector stores
CAMPAIGN_BASE_PATH = "mirror/campaigns"        # local store of campaign outlines
SESSIONS_BASE_PATH = "mirror/sessions"         # local store of generated sessions and play history

# How many recent turns to include in the DM recap (default 3)
RECENT_RECAP_TURNS = int(os.getenv("RECENT_RECAP_TURNS", "1000"))
# Optional word cap for the recent recap (0 = no word cap). Keep most recent words when trimming.
RECENT_RECAP_WORD_LIMIT = int(os.getenv("RECENT_RECAP_WORD_LIMIT", "4000"))

# Data models
class CampaignInfo(BaseModel):
    campaign_id: str
    name: str
    description: str
    world_collection: str
    created_at: str
    last_played: Optional[str] = None
    outline: str = ""

class SessionStatus(BaseModel):
    session_id: str
    campaign_id: str
    status: Literal["open", "complete"] = "open"
    created_at: str
    last_activity: str
    turn_count: int = 0
    summary: str = ""
    session_plan: dict = Field(default_factory=dict)

class SceneState(BaseModel):
    time_of_day: str
    region: str
    sub_region: str
    specific_location: str
    participants: list[str]
    exits: list[str]

# Initialize OpenAI client
def get_openai_client():
    agent_key = os.getenv("OPENAI_API_KEY_AGENT")
    if not agent_key:
        raise RuntimeError("OPENAI_API_KEY_AGENT not set in environment")
    
    openai.api_key = agent_key
    os.environ["OPENAI_API_KEY"] = agent_key
    client = OpenAI(api_key=agent_key)
    
    # Set up tracing
    try:
        set_tracing_export_api_key(agent_key)
        if GLOBAL_TRACE_PROVIDER and hasattr(GLOBAL_TRACE_PROVIDER, '_multi_processor'):
            GLOBAL_TRACE_PROVIDER._multi_processor.force_flush()
    except Exception:
        pass  # Tracing setup is optional
    
    return client

# Initialize agents and tools
def setup_agents_for_campaign(campaign_id: str, world_collection: str = "SwordCoast", campaign_outline: str = ""):
    """
    Initialize AI agents and tools for a D&D campaign.
    
    Args:
        campaign_id: Unique identifier for the campaign
        world_collection: Name of the world lore collection to use (default: "SwordCoast")
        campaign_outline: The full campaign outline JSON as a string
    
    Returns:
        Dictionary containing initialized agents (dm_agent, dm_new_session_agent, etc.)
    """
    client = get_openai_client()
    
    # System prompts - load from prompts/system/ directory
    dm_system_prompt = load_prompt("system", "dm_original.md")
    dm_new_session_prompt = load_prompt("system", "dm_new_session.md")
    dm_new_campaign_prompt = load_prompt("system", "dm_new_campaign.md")
    dm_post_session_prompt = load_prompt("system", "dm_post_session_analysis.md")

    # Replace {{}campaign-outline}} placeholder in dm_new_session.md with actual campaign outline text
    if campaign_outline:
        dm_new_session_prompt = dm_new_session_prompt.replace("{{campaign-outline}}", campaign_outline)
    else:
        dm_new_session_prompt = dm_new_session_prompt.replace("{{campaign-outline}}", "(No campaign outline available)")
    
    # Vector store for world lore
    lore = LoreSearch.set_lore(collection=world_collection)
    raw_lore_search_tool = lore.as_tool()
    
    # Lore search tool
    lore_agent = Agent(
        name="Lore Agent",
        instructions="Use file_search over the world/canon store and return concise snippets.",
        tools=[raw_lore_search_tool],
    )
    search_lore = lore_agent.as_tool(tool_name="searchLore", tool_description="Search world canon.")
    
    # Campaign memory tool
    mem_store_id = get_campaign_mem_store(client, campaign_id)
    mem = MemorySearch.from_id(
        campaign_id=campaign_id,
        vector_store_id=mem_store_id,
        client=client
    ).with_mirror(Path(MEM_MIRROR_PATH) / campaign_id)
    
    mem_agent = Agent(
        name="Memory Agent",
        instructions="Use file_search over the campaign memory store and return concise snippets.",
        tools=[mem.as_tool()],
    )
    search_memory = mem_agent.as_tool(tool_name="searchMemory", tool_description="Search campaign memory.")
    
    # Session review tool
    session_review = SessionReview.from_campaign(campaign_id)
    review_function = session_review.as_function()
    review_last_session = function_tool(name_override="ReviewLastSession")(review_function)
    
    # Dice roller
    def roll_impl(formula: str) -> dict:
        """
        Dice roller for game mechanics. It returns the full results of the dice.
        This helps in cases where a player might be allow to re-roll some dice.

        Args:
            formula: Dice roll formula as a string, e.g. "3d6+5".
                - Format: "<number of dice>d<dice sides>[+/-modifier]"
                - Examples: "2d20", "1d8-1", "4d6+3"
                - Do NOT use words or spelled-out numbers (e.g. "Three D6 plus five" is invalid).

        Returns:
            dict with keys: rolls (list of ints), mod (int), total (int), or error (str) if formula is invalid.
        """
        m = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", formula.replace(" ", ""))
        if not m:
            return {"error": "Bad formula"}
        n, sides, mod = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        rolls = [random.randint(1, sides) for _ in range(n)]
        total = sum(rolls) + mod
        return {"rolls": rolls, "mod": mod, "total": total}
    
    roll = function_tool(name_override="rollDice")(roll_impl)
    
    # ------------------------------------------------------------------------------
    # -- CREATE AGENTS
    # ------------------------------------------------------------------------------
    
    # Agent specifically for creating new campaigns
    dm_new_campaign_agent = Agent(
        name="New Campaign Preparation Agent",
        instructions=dm_new_campaign_prompt,
        tools=[search_lore],
        model="gpt-5"
    )
    
    # Agent specifically for new session preparation
    dm_new_session_agent = Agent(
        name="New Session Preparation Agent",
        instructions=dm_new_session_prompt,
        tools=[review_last_session, search_lore, search_memory],
        model="gpt-4o"
    )

    # Agent to analyse completed sessions
    dm_post_session_agent = Agent(
        name="Post-Session Analysis Agent",
        instructions=dm_post_session_prompt,
        tools=[],
        model="gpt-5"
    )

    # The turn-by-turn DM agent (legacy single-agent)
    dm_agent = Agent(
        name="The Dungeon Master",
        instructions=dm_system_prompt,
        tools=[search_lore, search_memory, roll],
        model="gpt-4o"
    )
    
    # ------------------------------------------------------------------------------
    # -- MULTI-AGENT SYSTEM (new router-based architecture)
    # ------------------------------------------------------------------------------
    
    # Load specialized agent prompts
    router_prompt = load_prompt("system", "dm_router.md")
    narrative_short_prompt = load_prompt("system", "dm_narrative_short.md")
    narrative_long_prompt = load_prompt("system", "dm_narrative_long.md")
    qa_situation_prompt = load_prompt("system", "dm_qa_situation.md")
    qa_rules_prompt = load_prompt("system", "dm_qa_rules.md")
    npc_dialogue_prompt = load_prompt("system", "dm_npc_dialogue.md")
    combat_designer_prompt = load_prompt("system", "dm_combat_designer.md")
    travel_prompt = load_prompt("system", "dm_travel.md")
    gameplay_prompt = load_prompt("system", "dm_gameplay.md")
    
    # Router agent (no tools, just classification)
    router_agent = Agent(
        name="DM Router",
        instructions=router_prompt,
        tools=[],
        model="gpt-4o-mini"
    )
    
    # Narrative agents (full tool access)
    narrative_short_agent = Agent(
        name="DM Narrative (Short)",
        instructions=narrative_short_prompt,
        tools=[search_lore, search_memory, roll],
        model="gpt-4o-mini"
    )
    
    narrative_long_agent = Agent(
        name="DM Narrative (Long)",
        instructions=narrative_long_prompt,
        tools=[search_lore, search_memory, roll],
        model="gpt-4o-mini"
    )
    
    # Q&A agents (limited tools)
    qa_situation_agent = Agent(
        name="DM Q&A (Situation)",
        instructions=qa_situation_prompt,
        tools=[search_memory],
        model="gpt-4o-mini"
    )
    
    qa_rules_agent = Agent(
        name="DM Q&A (Rules)",
        instructions=qa_rules_prompt,
        tools=[search_lore],
        model="gpt-4o-mini"
    )
    
    # NPC Dialogue agent (focused on NPC interactions and dialogue)
    npc_dialogue_agent = Agent(
        name="DM NPC Dialogue",
        instructions=npc_dialogue_prompt,
        tools=[search_lore, search_memory, roll],
        model="gpt-4o-mini"
    )
    
    # Combat Designer agent (designs and facilitates combat encounters)
    combat_designer_agent = Agent(
        name="DM Combat Designer",
        instructions=combat_designer_prompt,
        tools=[search_lore, search_memory, roll],
        model="gpt-4o-mini"
    )
    
    # Travel agent (full tool access)
    travel_agent = Agent(
        name="DM Travel",
        instructions=travel_prompt,
        tools=[search_lore, search_memory, roll],
        model="gpt-4o-mini"
    )
    
    # Gameplay agent (full tool access, handles all dice rolling)
    gameplay_agent = Agent(
        name="DM Gameplay",
        instructions=gameplay_prompt,
        tools=[search_lore, search_memory, roll],
        model="gpt-4o-mini"
    )
    
    return {
        "client": client,
        "dm_new_campaign_agent": dm_new_campaign_agent,
        "dm_new_session_agent": dm_new_session_agent,
        "dm_post_session_agent": dm_post_session_agent,
        "dm_agent": dm_agent,
        "memory_search": mem,
        # Multi-agent system
        "router": router_agent,
        "narrative_short": narrative_short_agent,
        "narrative_long": narrative_long_agent,
        "qa_situation": qa_situation_agent,
        "qa_rules": qa_rules_agent,
        "npc_dialogue": npc_dialogue_agent,
        "combat_designer": combat_designer_agent,
        "travel": travel_agent,
        "gameplay": gameplay_agent
    }

# Campaign management functions
async def create_campaign(world_collection: str, user_description: str, campaign_name: Optional[str] = None) -> dict:
    """
    Create a new campaign with AI-generated content.
    Usually triggered in the campaign tab of the UI.
    """
    campaign_id = f"camp_{int(time.time())}"
    
    if not campaign_name:
        campaign_name = f"Campaign {campaign_id}"
    
    # Set up agents for this world
    agents = setup_agents_for_campaign(campaign_id, world_collection)
    dm_new_campaign_agent = agents["dm_new_campaign_agent"]
    
    # Generate campaign content
    try:
        result = await Runner.run(dm_new_campaign_agent, user_description, hooks=LocalRunLogger())
        jl_write({"event": "new_campaign_generated", "campaign_id": campaign_id, "ts": time.time()})
    except Exception as e:
        raise Exception(f"Error generating campaign: {e}")
    
    # Get campaign outline
    campaign_text = (
        getattr(result, "output_text", None)
        or getattr(result, "content", None)
        or str(result)
    )
    
    # Save campaign file
    campaign_dir = Path(CAMPAIGN_BASE_PATH)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    campaign_path = campaign_dir / f"{campaign_id}_outline.json"
    
    # Create campaign info
    campaign_info = {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,  # Keep user's campaign name
        "user_description": user_description,  # Keep user's original description
        "name": campaign_name,  # For backward compatibility
        "description": user_description,  # For backward compatibility
        "world_collection": world_collection,
        "creation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),  # For backward compatibility
        "last_played": None,
        "outline": campaign_text
    }
    
    # Save campaign locally
    campaign_path.write_text(json.dumps(campaign_info, indent=2), encoding="utf-8")
    
    # Logging for diagnostics / analytics
    jl_write({
        "event": "campaign_created",
        "campaign_id": campaign_id,
        "world_collection": world_collection,
        "ts": time.time()
    })
    
    return campaign_info

async def load_campaign(campaign_id: str) -> Optional[dict]:
    """Load an existing campaign."""
    campaign_path = Path(CAMPAIGN_BASE_PATH) / f"{campaign_id}_outline.json"
    
    if not campaign_path.exists():
        return None
    
    try:
        campaign_data = json.loads(campaign_path.read_text(encoding="utf-8"))
        return campaign_data
    except (json.JSONDecodeError, IOError):
        return None

async def list_campaigns() -> list[dict]:
    """List all available campaigns."""
    campaign_dir = Path(CAMPAIGN_BASE_PATH)
    campaigns = []
    
    if not campaign_dir.exists():
        return campaigns
    
    for campaign_file in campaign_dir.glob("*_outline.json"):
        try:
            campaign_data = json.loads(campaign_file.read_text(encoding="utf-8"))
            campaigns.append(campaign_data)
        except (json.JSONDecodeError, IOError):
            continue
    
    # Sort by creation date, newest first
    campaigns.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return campaigns

async def update_last_played(campaign_id: str) -> bool:
    """Update the last_played timestamp for a campaign."""
    campaign_path = Path(CAMPAIGN_BASE_PATH) / f"{campaign_id}_outline.json"
    
    if not campaign_path.exists():
        return False
    
    try:
        # Load existing campaign data
        campaign_data = json.loads(campaign_path.read_text(encoding="utf-8"))
        
        # Update last_played timestamp
        campaign_data["last_played"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Save updated campaign data
        campaign_path.write_text(json.dumps(campaign_data, indent=2), encoding="utf-8")
        
        # Logging for diagnostics / analytics
        jl_write({
            "event": "campaign_last_played_updated",
            "campaign_id": campaign_id,
            "ts": time.time()
        })
        
        return True
    except (json.JSONDecodeError, IOError):
        return False

# Session management functions
async def create_session(campaign_id: str) -> dict:
    """
    Create a new game session for a campaign.
    Usually triggered in the sessions tab of the UI.
    """
    campaign = await load_campaign(campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")
    
    # Check for existing open session
    active_session = await get_active_session(campaign_id)
    if active_session:
        raise ValueError(f"Campaign {campaign_id} already has an open session: {active_session['session_id']}")
    
    session_id = str(int(time.time()))
    world_collection = campaign.get("world_collection", "SwordCoast")
    campaign_outline = campaign.get("outline", "")
    
    # Pass campaign_outline to setup_agents_for_campaign() so it can substitute the {{campaign-outline}} placeholder in dm_new_session.md prompt template
    agents = setup_agents_for_campaign(campaign_id, world_collection, campaign_outline)
    dm_new_session_agent = agents["dm_new_session_agent"]
    
    # Build session planning prompt
    # The campaign outline is already embedded within the agent we are about to call
    session_request = f"Plan the next session for this campaign."
    
    # Generate session content
    try:
        result = await Runner.run(dm_new_session_agent, session_request, hooks=LocalRunLogger())
    except Exception as e:
        raise Exception(f"Error generating session: {e}")
    
    # Retrieve the session plan as text
    session_text = (
        getattr(result, "final_output", None)  # RunResult.final_output contains the agent's text output
        or getattr(result, "output_text", None)  # Fallback for other result types
        or getattr(result, "content", None)
        or str(result)
    )
    
    # Extract JSON from session text using the helper function
    session_plan = extract_update_payload(session_text) or {}
    
    # Check JSON for key elements
    required_keys = ['session_title', 'beats']
    missing_keys = [key for key in required_keys if key not in session_plan]
    
    if not session_plan or missing_keys:
        # Log the failure for debugging
        jl_write({
            "event": "session_plan_extraction_failed",
            "campaign_id": campaign_id,
            "session_id": session_id,
            "has_data": bool(session_plan),
            "output_length": len(session_text),
            "missing_keys": missing_keys,
            "ts": time.time()
        })
        
        # Raise descriptive exception with debugging info
        error_details = []
        if not session_plan:
            error_details.append("no data extracted from agent output")
        else:
            error_details.append(f"missing required keys: {', '.join(missing_keys)}")
        
        error_details.append(f"extracted_data={'yes' if session_plan else 'no'}")
        error_details.append(f"output_length={len(session_text)}")
        
        raise Exception(
            f"Session plan extraction/validation failed: {'; '.join(error_details)}"
        )
    
    # Generate structured JSON containing session info, plus metadata
    # This will be saved as the session file and used as a persistent file ongoing
    session_info = {
        "session_id": session_id,
        "campaign_id": campaign_id,
        "status": "open",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_activity": time.strftime("%Y-%m-%d %H:%M:%S"),
        "turn_count": 0,
        "summary": "Session just started",
        "session_plan": session_plan,  # All session planning data (beats, NPCs, locations, etc.)
        "chat_history": []  # Player/DM conversation history populated during gameplay
    }
    
    # Save session file
    session_dir = Path(SESSIONS_BASE_PATH) / campaign_id
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / f"{session_id}_session.json"
    session_path.write_text(json.dumps(session_info, indent=2), encoding="utf-8")
    
    jl_write({
        "event": "session_created",
        "campaign_id": campaign_id,
        "session_id": session_id,
        "ts": time.time()
    })
    
    return session_info

async def load_session(campaign_id: str, session_id: str) -> Optional[dict]:
    """Load an existing session."""
    session_path = Path(SESSIONS_BASE_PATH) / campaign_id / f"{session_id}_session.json"
    
    if not session_path.exists():
        return None
    
    try:
        session_data = json.loads(session_path.read_text(encoding="utf-8"))
        return session_data
    except (json.JSONDecodeError, IOError):
        return None

async def list_sessions(campaign_id: str) -> list[dict]:
    """List all sessions for a campaign with status."""
    session_dir = Path(SESSIONS_BASE_PATH) / campaign_id
    sessions = []
    
    if not session_dir.exists():
        return sessions
    
    for session_file in session_dir.glob("*_session.json"):
        try:
            session_data = json.loads(session_file.read_text(encoding="utf-8"))
            # Ensure status field exists (for backward compatibility)
            if "status" not in session_data:
                session_data["status"] = "complete"  # Default old sessions to complete
            sessions.append(session_data)
        except (json.JSONDecodeError, IOError):
            continue
    
    # Sort by creation date, newest first
    sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return sessions

async def get_active_session(campaign_id: str) -> Optional[dict]:
    """Get the currently active (open) session for a campaign."""
    sessions = await list_sessions(campaign_id)
    for session in sessions:
        if session.get("status") == "open":
            return session
    return None

async def generate_post_session_analysis(campaign_id: str, session: dict) -> str:
    """Generate post-session analysis comparing planned vs actual events."""
    try:
        # Get campaign info for world collection
        campaign = await load_campaign(campaign_id)
        if not campaign:
            return "Campaign not found - unable to generate analysis."
        
        world_collection = campaign.get("world_collection", "SwordCoast")
        campaign_outline = campaign.get("outline", "")
        
        # Set up agents with campaign outline
        agents = setup_agents_for_campaign(campaign_id, world_collection, campaign_outline)
        post_session_agent = agents["dm_post_session_agent"]
        
        # Build analysis input
        session_plan = session.get("session_plan", {})
        chat_history = session.get("chat_history", [])
        
        # Format chat history for analysis
        transcript = []
        for turn in chat_history:
            player_input = turn.get("user_input", "")
            dm_response = turn.get("dm_response", "")
            transcript.append(f"Player: {player_input}")
            transcript.append(f"DM: {dm_response}")
            transcript.append("")
        
        transcript_text = "\n".join(transcript)
        
        # Build prompt for analysis with campaign context
        analysis_request = textwrap.dedent(f"""
        # Campaign Overview
        The following is the complete campaign outline that provides the overall narrative arc:
        {campaign_outline}
        ---
        # Session Plan (INTENDED)
        ```json
        {json.dumps(session_plan, indent=2)}
        ```
        ---
        # Session Transcript (ACTUAL)
        {transcript_text}
        ---
        Please provide a structured post-session analysis following the format specified in your instructions.
        Use the campaign overview to assess whether this session moved the players toward the campaign's intended goals.
        """).strip()
        
        # Run analysis agent
        result = await Runner.run(post_session_agent, analysis_request)
        
        # Extract analysis from result
        analysis = result.final_output if hasattr(result, 'final_output') else str(result)
        
        jl_write({
            "event": "post_session_analysis_generated",
            "campaign_id": campaign_id,
            "session_id": session.get("session_id"),
            "ts": time.time()
        })
        
        return analysis
    
    except Exception as e:
        jl_write({
            "event": "post_session_analysis_error",
            "campaign_id": campaign_id,
            "session_id": session.get("session_id"),
            "error": str(e),
            "ts": time.time()
        })
        return f"Error generating analysis: {str(e)}"

async def close_session(campaign_id: str, session_id: str) -> dict:
    """Mark a session as complete and generate post-session analysis."""
    session = await load_session(campaign_id, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    # Generate post-session analysis
    post_session_analysis = await generate_post_session_analysis(campaign_id, session)
    
    # Update session with analysis and status
    session["status"] = "complete"
    session["last_activity"] = time.strftime("%Y-%m-%d %H:%M:%S")
    session["post_session_analysis"] = post_session_analysis
    
    # Save updated session
    session_path = Path(SESSIONS_BASE_PATH) / campaign_id / f"{session_id}_session.json"
    session_path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    
    jl_write({
        "event": "session_closed",
        "campaign_id": campaign_id,
        "session_id": session_id,
        "ts": time.time()
    })
    
    return session

# Game play functions
async def play_turn(campaign_id: str, session_id: str, user_input: str, user_id: str = "web_user") -> dict:
    """Process a single turn of gameplay."""

    # Load session and campaign
    session = await load_session(campaign_id, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    if session.get("status") != "open":
        raise ValueError(f"Session {session_id} is not open for play")
    
    campaign = await load_campaign(campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")
    
    world_collection = campaign.get("world_collection", "SwordCoast")
    
    # Check if multi-agent DM is enabled
    use_multi_agent = os.getenv("USE_MULTI_AGENT_DM", "false").lower() == "true"
    
    # Set up agents and game state
    agents = setup_agents_for_campaign(campaign_id, world_collection)
    dm_agent = agents["dm_agent"]
    memory_search = agents["memory_search"]
    
    # Build current scene state
    scene_state = SceneState(
        time_of_day="unknown",
        region="unknown",
        sub_region="unknown",
        specific_location="unknown",
        participants=["unknown"],
        exits=["unknown"]
    )
    
    # Apply initial scene if this is the first turn
    if session["turn_count"] == 0:
        session_plan = session.get("session_plan", {})
        # Get initial scene state patch from session plan
        initial_scene = session_plan.get("initial_scene_state_patch", {}) or session.get("initial_scene_state", {})
        scene_state = merge_scene_patch(scene_state, initial_scene)
    
    # Get recent context from chat history (configurable via RECENT_RECAP_TURNS and RECENT_RECAP_WORD_LIMIT)
    chat_history = session.get("chat_history", [])
    recent_recap = ""
    if len(chat_history) > 0:
        # Determine how many turns to include (if RECENT_RECAP_TURNS <= 0, include all)
        num_turns = RECENT_RECAP_TURNS if RECENT_RECAP_TURNS > 0 else len(chat_history)
        recent_turns = chat_history[-num_turns:] if len(chat_history) >= num_turns else chat_history
        recent_recap = " ".join([
            f"Player: {turn.get('user_input', '')} DM: {turn.get('dm_response', '')}"
            for turn in recent_turns
        ])
        # Optionally trim to a maximum number of words, keeping the most recent words
        if RECENT_RECAP_WORD_LIMIT and RECENT_RECAP_WORD_LIMIT > 0:
            words = recent_recap.split()
            if len(words) > RECENT_RECAP_WORD_LIMIT:
                recent_recap = " ".join(words[-RECENT_RECAP_WORD_LIMIT:])
    
    # Build context for the DM
    session_plan = session.get("session_plan", {})
    context = dm_context_blob(session_plan, scene_state, recent_recap)
    dm_input = f"{context}\nPlayer: {user_input}"
    
    # Get DM response - use multi-agent orchestrator or legacy single agent
    intent_used = None  # Track which agent was used (for frontend display)
    
    if use_multi_agent:
        # Import orchestrator (lazy import to avoid circular dependencies)
        from src.orchestration.turn_router import orchestrate_turn
        
        # Build session context for orchestrator
        session_context = {
            "session_plan": session_plan,
            "scene_state": scene_state,
            "recent_recap": recent_recap,
            "dm_input": dm_input
        }
        
        # Route through multi-agent orchestrator
        try:
            orchestrator_result = await orchestrate_turn(
                campaign_id=campaign_id,
                session_id=session_id,
                user_input=user_input,
                user_id=user_id,
                agents=agents,
                session_context=session_context
            )
            
            dm_response = orchestrator_result["dm_response"]
            update_payload = orchestrator_result["update_payload"]
            intent_used = orchestrator_result.get("intent_used")
            
            # Log which agent was used
            jl_write({
                "event": "multi_agent_routing",
                "intent": intent_used,
                "note": orchestrator_result.get("routing_note"),
                "campaign_id": campaign_id,
                "session_id": session_id,
                "ts": time.time()
            })
            
        except Exception as e:
            raise Exception(f"Error from multi-agent orchestrator: {e}")
    else:
        # Legacy single-agent path
        try:
            result = await Runner.run(dm_agent, dm_input, hooks=LocalRunLogger())
        except Exception as e:
            raise Exception(f"Error getting DM response: {e}")
        
        dm_response_raw = (
            getattr(result, "output_text", None)
            or getattr(result, "content", None)
            or str(result)
        )
        
        # Parse DM response and updates
        # First extract narrative from RunResult format if needed
        dm_response_clean = extract_narrative_from_runresult(dm_response_raw)
        
        # Then strip any JSON blocks
        update_payload = extract_update_payload(dm_response_clean) or {}
        dm_response = strip_json_block(dm_response_clean)
        
        # Set default intent for single-agent responses
        intent_used = "narrative_long"
    
    # Update scene state if provided
    scene_patch = update_payload.get("scene_state_patch", {})
    if scene_patch:
        scene_state = merge_scene_patch(scene_state, scene_patch)
    
    # Update session memory
    memory_writes = update_payload.get("memory_writes", [])
    if memory_writes:
        memory_search.upsert_memory_writes(user_id=user_id, memory_writes=memory_writes)
    
    # Create turn record
    turn_record = {
        "turn_number": session["turn_count"] + 1,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "user_input": user_input,
        "dm_response": dm_response,
        "scene_state": scene_state.model_dump(),
        "memory_writes": memory_writes,
        "turn_summary": update_payload.get("turn_summary", ""),
        "intent_used": intent_used
    }
    
    # Update session
    session["turn_count"] += 1
    session["last_activity"] = time.strftime("%Y-%m-%d %H:%M:%S")
    session["chat_history"].append(turn_record)
    
    # Update summary
    if update_payload.get("turn_summary"):
        session["summary"] = update_payload["turn_summary"]
    
    # Save updated session
    session_path = Path(SESSIONS_BASE_PATH) / campaign_id / f"{session_id}_session.json"
    session_path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    
    jl_write({
        "event": "turn_played",
        "campaign_id": campaign_id,
        "session_id": session_id,
        "turn_number": session["turn_count"],
        "ts": time.time()
    })
    
    return {
        "dm_response": dm_response,
        "turn_number": session["turn_count"],
        "scene_state": scene_state.model_dump(),
        "session_summary": session["summary"],
        "intent_used": intent_used
    }

# Utility functions (from main.py)
JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

def dm_context_blob(session_plan: dict[str, Any], scene_state: SceneState, recent_recap: str) -> str:
    """Compose a small, model-friendly context preface."""
    return (
        "DM CONTEXT\n"
        "Session plan:\n" + json.dumps(session_plan, ensure_ascii=False) + "\n\n"
        "SceneState JSON:\n" + json.dumps(scene_state.model_dump(), ensure_ascii=False) + "\n\n"
        "Recent Recap:\n" + (recent_recap or "(none)") + "\n"
        "END CONTEXT\n"
    )

def extract_update_payload(dm_text: str) -> Optional[dict[str, Any]]:
    """Pull the last ```json ... ``` block from the DM's reply."""
    matches = list(JSON_BLOCK_RE.finditer(dm_text))
    if not matches:
        return None
    raw = matches[-1].group(1)
    try:
        return json.loads(raw)
    except Exception:
        return None

def strip_json_block(dm_text: str) -> str:
    """Remove the trailing JSON block so only narration is shown to the player."""
    return JSON_BLOCK_RE.sub("", dm_text).rstrip()

def extract_narrative_from_runresult(text: str) -> str:
    """Extract just the narrative content from RunResult format."""
    if not text or not isinstance(text, str):
        return text
    
    # Check if this is a RunResult format
    if text.startswith("RunResult:") and "Final output (str):" in text:
        import re
        
        # Use regex to extract content after "Final output (str):" 
        # and stop at RunResult metadata (whether inline or on new lines)
        pattern = r"Final output \(str\):\s*(.*?)(?:\s*-\s*\d+\s+(?:new item\(s\)|raw response\(s\)|input guardrail result\(s\)|output guardrail result\(s\))|(?:\s*\(See `RunResult`)|$)"
        
        match = re.search(pattern, text, re.DOTALL)
        if match:
            narrative_content = match.group(1).strip()
            
            # Additional cleanup: remove any trailing metadata that might not be caught
            # Look for patterns like "- 1 new item(s)" at the end
            cleanup_patterns = [
                r'\s*-\s*\d+\s+new item\(s\).*$',
                r'\s*-\s*\d+\s+raw response\(s\).*$', 
                r'\s*-\s*\d+\s+input guardrail result\(s\).*$',
                r'\s*-\s*\d+\s+output guardrail result\(s\).*$',
                r'\s*\(See `RunResult`.*$'
            ]
            
            for cleanup_pattern in cleanup_patterns:
                narrative_content = re.sub(cleanup_pattern, '', narrative_content, flags=re.DOTALL)
            
            return narrative_content.strip()
    
    # If not RunResult format, return as-is
    return text

def merge_scene_patch(scene: SceneState, patch: dict[str, Any]) -> SceneState:
    """Shallow merge: if a top-level field is present in patch, replace it in the scene."""
    data = scene.model_dump()
    for k, v in patch.items():
        if v is not None:
            data[k] = v
    return SceneState(**data)

# Available worlds function
def get_available_worlds() -> dict:
    """Get list of available world collections from config."""
    try:
        config_path = Path("config/vectorstores.json")
        if config_path.exists():
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
            return config_data.get("world", {})
        return {}
    except (json.JSONDecodeError, IOError):
        return {}