# logging_hooks.py
from dataclasses import asdict
from pathlib import Path
import json, time
from agents import RunHooks, Agent, Tool

# Local-machine specific path to log files
LOG_PATH = Path("logs/agents.log")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Helper function to write a custom log entry
def jl_write(record: dict):
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# Runs within the OpenAI Agents SDK and logs all relevant events via jl_write
class LocalRunLogger(RunHooks[object]):
    """
    Logs:
      - when an agent is called and finished
      - input/output tokens (incl. reasoning if available)
      - function/tool calls (name + duration)
      - handoffs (from->to)
      - end-to-end latency
    """
    def __init__(self):
        self._t0 = None
        self._tool_t0 = {}

    async def on_agent_start(self, ctx, agent: Agent):
        # ctx.usage holds *so-far* usage; it updates as the run progresses.
        # We'll record a starting snapshot and a wall clock.
        self._t0 = time.perf_counter()
        jl_write({
            "event": "agent_start",
            "agent": getattr(agent, "name", None),
            "model": getattr(agent, "model", None),
            "usage_so_far": {"input_tokens": ctx.usage.input_tokens, "output_tokens": ctx.usage.output_tokens},            "ts": time.time(),
        })

    async def on_tool_start(self, ctx, agent: Agent, tool: Tool):
        self._tool_t0[id(tool)] = time.perf_counter()
        jl_write({
            "event": "tool_start",
            "agent": getattr(agent, "name", None),
            "tool_type": type(tool).__name__,
            "tool_name": getattr(tool, "name", None),  # many Tool impls expose .name
            "usage_so_far": {"input_tokens": ctx.usage.input_tokens, "output_tokens": ctx.usage.output_tokens},
            "ts": time.time(),
        })

    async def on_tool_end(self, ctx, agent: Agent, tool: Tool, result: str):
        dt = None
        t0 = self._tool_t0.pop(id(tool), None)
        if t0 is not None:
            dt = time.perf_counter() - t0
        jl_write({
            "event": "tool_end",
            "agent": getattr(agent, "name", None),
            "tool_type": type(tool).__name__,
            "tool_name": getattr(tool, "name", None),
            "duration_s": dt,
            "result_preview": (result[:4000] + "…") if result and len(result) > 4000 else result,
            "usage_so_far": {"input_tokens": ctx.usage.input_tokens, "output_tokens": ctx.usage.output_tokens},            "ts": time.time(),
            "ts": time.time(),
        })

    async def on_handoff(self, ctx, from_agent: Agent, to_agent: Agent):
        jl_write({
            "event": "handoff",
            "from_agent": getattr(from_agent, "name", None),
            "to_agent": getattr(to_agent, "name", None),
            "usage_so_far": {"input_tokens": ctx.usage.input_tokens, "output_tokens": ctx.usage.output_tokens},            "ts": time.time(),
            "ts": time.time(),
        })

    async def on_agent_end(self, ctx, agent: Agent, output):
        dt = None
        if self._t0 is not None:
            dt = time.perf_counter() - self._t0
        # ctx.usage is the aggregate; result.usage (below) is authoritative at the very end.
        jl_write({
            "event": "agent_end",
            "agent": getattr(agent, "name", None),
            "duration_s": dt,
            "usage_so_far": {"input_tokens": ctx.usage.input_tokens, "output_tokens": ctx.usage.output_tokens},            "ts": time.time(),
            "ts": time.time(),
        })
