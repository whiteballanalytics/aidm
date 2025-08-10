import json
from pathlib import Path

CONFIG_PATH = Path("config/vectorstores.json")

def add_to_vector_store(category: str, store_name: str, id: str):

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            data = {}
            
    data.setdefault(category, {})
    data[category][store_name] = {"vector_store_id": id}

    CONFIG_PATH.write_text(json.dumps(data, indent=2))