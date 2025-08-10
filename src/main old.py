import asyncio
import os
from dotenv import load_dotenv
import openai
from agents import Agent, Runner, SQLiteSession, function_tool, InputGuardrail, GuardrailFunctionOutput
from agents import set_tracing_export_api_key
from agents.tracing.setup import GLOBAL_TRACE_PROVIDER
from pydantic import BaseModel
import random

# Load environment
load_dotenv()

# Set API keys
openai.api_key = os.getenv("OPENAI_API_KEY")
set_tracing_export_api_key = os.getenv("OPENAI_API_KEY")

GLOBAL_TRACE_PROVIDER._multi_processor.force_flush()

session = SQLiteSession("dnd_campaign_001")

class GuardrailOutput(BaseModel):
    is_dnd: bool
    reasoning: str

class RollDiceInput(BaseModel):
    sides: int = 20

dnd_gameplay_guardrail_agent = Agent(
    name = "Guardrail check",
    instructions = "Check if the user is saying something that makes sense in the context of a game of Dungeons and Dragons.",
    output_type = GuardrailOutput
)

@function_tool
def roll_dice(sides: int = 20) -> int:
    """Rolls a dice with the specified number of sides. Default is a D20."""
    return random.randint(1, sides)

@function_tool
def get_next_action() -> str:
    """Prompts the player for their next action in the game."""
    return input("What do you want to do next? ")

@function_tool
async def do_saving_throw():
    """Perform a saving throw and print the result."""
    result = await Runner.run(savingthrow_agent, "Run a saving throw for the player.")
    print("\n[Saving Throw Result]")
    print(result.final_output)
    return result.final_output

@function_tool
async def narrate_story():
    """Create a narrative update and print it."""
    result = await Runner.run(narrative_agent, "Describe the next part of the story.")
    print("\n[Story Update]")
    print(result.final_output)
    return result.final_output

savingthrow_agent = Agent(
    name = "Saving throw agent",
    handoff_description = "Specialist agent for doing saving throws if a player tries to do something non-trivial",
    instructions = """
    You simulate saving throws as per standard DnD 5e rule.
    Decide an appropriate Difficulty Class (DC) and then role a dice to see whether the player passes.
    """,
    tools = [roll_dice]
)

narrative_agent = Agent(
    name = "Narrative agent",
    handoff_description = "Narrative agent for describing events",
    instructions = """
    You create narrative descriptions that explain what happens next in the game.
    Reply with creative language in 1 paragraph or less.
    Take into account the actions the player has taken and their success on saving throws.
    """
)

async def dnd_gameplay_guardrail(ctx, agent, input_data):
    result = await Runner.run(dnd_gameplay_guardrail_agent, input_data, context=ctx.context)
    final_output = result.final_output_as(GuardrailOutput)
    return GuardrailFunctionOutput(
        output_info = final_output,
        tripwire_triggered = not final_output.is_dnd
    )

dm_agent = Agent(
    name = "The Dungeon Master",
    instructions = """
    You must decide which agent to hand off to, based on what the user has said.
    The user is a player in a game of Dungeons and Dragons and you are acting as the DM.
    If players say that they want to end the session then you have finished.
    """,
    tools = [get_next_action, do_saving_throw, narrate_story],
    input_guardrails = [
        InputGuardrail(guardrail_function=dnd_gameplay_guardrail)
    ]
)

async def main():
    esc = 0
    while esc == 0:
        user_input = input()
        result = await Runner.run(dm_agent, user_input)

if __name__ == "__main__":
    asyncio.run(main())