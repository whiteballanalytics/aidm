# Standard library
import asyncio
import os
import random
import re
import json
import time
from pathlib import Path
from typing import Any, Literal

# Third-party: environment & OpenAI core
from dotenv import load_dotenv
import openai
from openai import OpenAI

# Third-party: OpenAI Agents SDK
from agents import Agent, Runner, function_tool
from agents import set_tracing_export_api_key
from agents.tracing.setup import GLOBAL_TRACE_PROVIDER

# Third-party: data validation
from pydantic import BaseModel, Field

# Project-local
from library.vectorstores import LoreSearch, MemorySearch, get_campaign_mem_store
from library.prompts import load_prompt
from library.logginghooks import LocalRunLogger, jl_write


# --- USER / CAMPAIGN (temporary hard-codes for testing) ---
USER_ID = "user_001"
CAMPAIGN_ID = "camp_016"
MEM_REGISTRY_PATH = "config/memorystores.json"
MEM_MIRROR_PATH = "mirror/mem_mirror"
CAMPAIGN_BASE_PATH = "mirror/campaigns"
SESSIONS_BASE_PATH = "mirror/sessions"

# Load environment
load_dotenv()

# Set OpenAI API key for the client
AGENT_KEY = os.getenv("OPENAI_API_KEY_AGENT")
if not AGENT_KEY:
    raise RuntimeError("OPENAI_API_KEY_AGENT not set in environment")

# Make sure every library that expects an OPENAI_API_KEY can see one
openai.api_key = AGENT_KEY
os.environ["OPENAI_API_KEY"] = AGENT_KEY
client = OpenAI(api_key=AGENT_KEY)

# Pass API key to tracing setup
set_tracing_export_api_key(AGENT_KEY)
# Forces tracing buffer to flush immediately
# i.e., it pushes any queued spans/events to the tracing backend now,
# instead of waiting for the background batch timer
GLOBAL_TRACE_PROVIDER._multi_processor.force_flush()


# ---- System Prompt for the Dungeon Master Agent ----
DM_SYSTEM_PROMPT = load_prompt("system", "dm_original.md")
DM_NEW_SESSION_PROMPT = load_prompt("system", "dm_new_session.md")
DM_NEW_CAMPAIGN_PROMPT = load_prompt("system", "dm_new_campaign.md")


# ---- Define Data Classes ----
# Used for short-term memory (scene state)
class SceneState(BaseModel):
    time_of_day: str
    region: str
    sub_region: str
    specific_location: str
    participants: list[str]
    exits: list[str]

# class EpisodicMemory(BaseModel):
#     type: Literal["event","preference","relationship","quest_update","lore_use"]
#     keys: list[str] = Field(default_factory=list, description="Entities for retrieval (NPCs, places, items)")
#     summary: str = Field(..., max_length=240, description="One-sentence fact or change to remember")


# ---- Vector store & memory backends (you provide these) ----
# Vector store for the world lore
lore = LoreSearch.set_lore(collection="SwordCoast")
raw_lore_search_tool = lore.as_tool()

lore_agent = Agent(
    name = "Lore Agent",
    instructions = "Use file_search over the world/canon store and return concise snippets.",
    tools = [raw_lore_search_tool],
)

search_lore = lore_agent.as_tool(tool_name="searchLore",  tool_description="Search world canon.")

# Long-term memory store
mem_store_id = get_campaign_mem_store(client, CAMPAIGN_ID)
mem = MemorySearch.from_id(
    campaign_id = CAMPAIGN_ID,
    vector_store_id = mem_store_id,
    client = client
).with_mirror(Path(MEM_MIRROR_PATH) / CAMPAIGN_ID)
raw_memory_search_tool = mem.as_tool()

mem_agent = Agent(
    name = "Memory Agent",
    instructions = "Use file_search over the campaign memory store and return concise snippets.",
    tools = [raw_memory_search_tool],
)

search_memory = mem_agent.as_tool(tool_name="searchMemory", tool_description="Search campaign memory.")


# ---- Core Agent Tools ----
def roll_impl(formula: str) -> dict:
    """
    Dice roller for game mechanics.

    Use this tool whenever a random outcome is needed
    (e.g., ability checks, saving throws, attack rolls, damage, initiative).
    Input a single dice expression using lowercase 'd' and an optional +/- modifier:

        <N>d<S>[+/-M]

    Examples:
        "1d20+3"   # ability check with proficiency
        "2d6"      # weapon damage
        "5d8-2"    # effect with penalty
        "3d4+0"    # explicit zero modifier is allowed
    """
    m = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", formula.replace(" ", ""))
    if not m:
        return {"error": "Bad formula"}
    n, sides, mod = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    rolls = [random.randint(1, sides) for _ in range(n)]
    total = sum(rolls) + mod
    return {"rolls": rolls, "mod": mod, "total": total}

# Wrap it as an Agents tool for the DM to use
roll = function_tool(name_override="rollDice")(roll_impl)

# @function_tool(name_override="commitMemory")
# def commit_memory(items: list[EpisodicMemory]) -> dict:
#     """
#     Persist long-term memory for this campaign.
#     The DM should call this whenever relationships change or notable facts occur.
#     """
#     mem.upsert_memory_writes(user_id=USER_ID, memory_writes=[i.model_dump() for i in items])
#     return {"saved": len(items)}


# ---- More functions for Memory ----
JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

def dm_context_blob(session_plan: dict[str, Any], scene_state: "SceneState", recent_recap: str) -> str:
    """Compose a small, model-friendly context preface."""
    return (
        "DM CONTEXT\n"
        "Session plan:\n" + json.dumps(session_plan, ensure_ascii=False) + "\n\n"
        "SceneState JSON:\n" + json.dumps(scene_state.model_dump(), ensure_ascii=False) + "\n\n"
        "Recent Recap (<=200 words):\n" + (recent_recap or "(none)") + "\n"
        "END CONTEXT\n"
    )

def extract_update_payload(dm_text: str) -> dict[str, Any] | None:
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

def merge_scene_patch(scene: "SceneState", patch: dict[str, Any]) -> "SceneState":
    """Shallow merge: if a top-level field is present in patch, replace it in the scene."""
    data = scene.model_dump()
    for k, v in patch.items():
        if v is not None:
            data[k] = v
    return SceneState(**data)

def clip_recap(prev: str, turn_summary: str, limit_chars: int = 4000) -> str:
    """Keep recap short and fresh."""
    rec = (prev + " " + (turn_summary or "")).strip()
    return rec[-limit_chars:] if len(rec) > limit_chars else rec


# ---- The Master Agent ----
dm_agent = Agent(
    name = "The Dungeon Master",
    instructions = DM_SYSTEM_PROMPT,
    tools = [search_lore, search_memory, roll]
)

dm_new_session_agent = Agent(
    name = "New Session Preparation Agent",
    instructions = DM_NEW_SESSION_PROMPT,
    tools = [search_lore, search_memory]
)

dm_new_campaign_agent = Agent(
    name = "New Campaign Preparation Agent",
    instructions = DM_NEW_CAMPAIGN_PROMPT,
    tools = [search_lore],
    model="gpt-5"
)


# ---- Looping ----
async def aio_input(prompt: str = "") -> str:
    # Runs blocking input() in a worker thread (Py 3.9+)
    return await asyncio.to_thread(input, prompt)

async def main():
    
    # Check if the campaign exists yet
    campaign_path = Path(CAMPAIGN_BASE_PATH) / f"{CAMPAIGN_ID}_outline.json"

    if campaign_path.exists():
        print(f"Campaign '{CAMPAIGN_ID}' exists.")
        print(f"Continuing campaign...")
        jl_write({"event": "campaign_found", "campaign_id": CAMPAIGN_ID, "ts": time.time()})
    else:
        print(f"Campaign '{CAMPAIGN_ID}' not found.")
        print(f"Initialising new campaign...")
        user_text = (await aio_input("I would love guidance - do you have any ideas for the new campaign?: ")).strip()
        
        # Run the New Campaign agent.
        try:
            ns_result = await Runner.run(dm_new_campaign_agent, user_text, hooks=LocalRunLogger())
            jl_write({"event": "new_campaign_generated", "campaign_id": CAMPAIGN_ID, "ts": time.time()})
        except KeyboardInterrupt:
            print("\n[Interrupted]")
        except Exception as e:
            print(f"\n[Error from New Campaign agent] {e}")

        # Get the New Campaign agent's output
        ns_text = (
            getattr(ns_result, "output_text", None)
            or getattr(ns_result, "content", None)
            or str(ns_result)
        )
        campaign_dir = Path(CAMPAIGN_BASE_PATH)
        campaign_dir.mkdir(parents=True, exist_ok=True)
        campaign_path = campaign_dir / f"{CAMPAIGN_ID}_outline.json"
        campaign_path.write_text(ns_text, encoding="utf-8")

    # Run the New Session agent.
    try:
        ns_result = await Runner.run(dm_new_session_agent, "Create a new session", hooks=LocalRunLogger())
    except KeyboardInterrupt:
        print("\n[Interrupted]")
    except Exception as e:
        print(f"\n[Error from New Session agent] {e}")

    # Get the New Session agent's output
    ns_text = (
        getattr(ns_result, "output_text", None)
        or getattr(ns_result, "content", None)
        or str(ns_result)
    )

    # Parse the JSON block from the New Session agent's output
    new_session_json = extract_update_payload(ns_text) or {}

    # Save the JSON block to a new session file in mirror/sessions
    session_dir = Path(SESSIONS_BASE_PATH) / CAMPAIGN_ID
    session_dir.mkdir(parents=True, exist_ok=True)
    session_id = int(time.time())
    session_path = session_dir / f"{session_id}_new_session.json"
    session_path.write_text(
        json.dumps(new_session_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Pull structured pieces (fallbacks keep it robust)
    session_plan  = new_session_json.get("session_plan", {})
    initial_scene = new_session_json.get("initial_scene_state_patch", {})

    # Get the read-aloud text from the New Session JSON
    read_aloud = new_session_json["session_plan"]["opening_read_aloud"]
    
    print("\n=== Dungeon Master — turn-based session ===")
    print("Type '/quit' to exit.\n")

    if read_aloud:
        print("\n=== Session Read-Aloud ===\n")
        print(read_aloud.strip())
        print("\n==========================\n")
    jl_write({"event": "session_start", "campaign_id": CAMPAIGN_ID, "session_id": session_id, "read_aloud": read_aloud,"ts": time.time()})

    # Seed the session with an opening line from the player
    user_text = (await aio_input("You: ")).strip()
    if not user_text:
        user_text = "(The player hesitates, looking around.)"
    if user_text.lower() in ("/quit", "quit", "exit", "/exit"):
        print("Goodbye, adventurer.")
    jl_write({"event": "user_input", "campaign_id": CAMPAIGN_ID, "session_id": session_id, "user_input": user_text, "ts": time.time()})

    # Short-term memory state
    scene_state = SceneState(
        time_of_day = "unknown",
        region = "unknown",
        sub_region = "unknown",
        specific_location = "unknown",
        participants = ["unknown"],
        exits = ["unknown"]
    )
    scene_state = merge_scene_patch(scene_state, initial_scene)
    recent_recap = ""

    while True:
        # Build the turn's input with context
        preface = dm_context_blob(session_plan, scene_state, recent_recap)
        user_text_in = f"{preface}\nPlayer: {user_text}"
        jl_write({"event": "dm_agent_input", "campaign_id": CAMPAIGN_ID, "session_id": session_id, "dm_agent_input": user_text_in, "ts": time.time()})


        # Hand one turn to the agent. Runner should orchestrate tool calls internally.
        try:
            result = await Runner.run(dm_agent, user_text_in, hooks=LocalRunLogger())
        except KeyboardInterrupt:
            print("\n[Interrupted]")
            break
        except Exception as e:
            print(f"\n[Error from agent] {e}")
            # keep the loop responsive
            user_text = await aio_input("\nYou: ")
            if user_text.strip().lower() in ("/quit", "quit", "exit", "/exit"):
                break
            continue

        # Show the agent's raw output
        dm_text = (
            getattr(result, "output_text", None)
            or getattr(result, "content", None)
            or str(result)
        )

        # Parse and merge short-term memory updates
        payload = extract_update_payload(dm_text) or {}
        patch = payload.get("scene_state_patch") or {}
        if patch:
            scene_state = merge_scene_patch(scene_state, patch)

        turn_summary = payload.get("turn_summary") or ""
        recent_recap = clip_recap(recent_recap, turn_summary)

        mem.upsert_memory_writes(user_id=USER_ID, memory_writes=payload.get("memory_writes", []))

        # Show the narration part only (strip the JSON block)
        print(f"\nDM:\n{strip_json_block(dm_text)}\n")
        jl_write({"event": "dm_narration", "campaign_id": CAMPAIGN_ID, "session_id": session_id, "dm_narration": strip_json_block(dm_text), "ts": time.time()})

        user_text = (await aio_input("You: ")).strip()
        if not user_text:
            user_text = "(The player hesitates, looking around.)"
        if user_text.lower() in ("/quit", "quit", "exit", "/exit"):
            print("Goodbye, adventurer.")
            break
        jl_write({"event": "user_input", "campaign_id": CAMPAIGN_ID, "session_id": session_id, "user_input": user_text, "ts": time.time()})
    
    jl_write({"event": "session_end", "campaign_id": CAMPAIGN_ID, "session_id": session_id, "user_input": user_text, "ts": time.time()})

if __name__ == "__main__":
    asyncio.run(main())