from pathlib import Path
import re

PROMPTS_DIR = Path("prompts")

def load_prompt(*parts: str) -> str:
    """Load a prompt file under prompts/, ignoring simple YAML front matter."""
    p = PROMPTS_DIR.joinpath(*parts)
    text = p.read_text(encoding="utf-8")
    # strip simple front matter if present
    return re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
