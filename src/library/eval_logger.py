import os
import json
import time
from pathlib import Path

LOG_PATH = Path("logs/router_captures.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

def is_eval_logging_enabled() -> bool:
    return os.environ.get("EVAL_LOGGING_ENABLED", "").lower() in ("true", "1", "yes")

def log_router_prompt(router_prompt: str, user_input: str, session_id: str = None):
    if not is_eval_logging_enabled():
        return
    
    record = {
        "timestamp": time.time(),
        "session_id": session_id,
        "user_input": user_input,
        "router_prompt": router_prompt
    }
    
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass
