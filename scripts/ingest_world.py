import os, sys
import openai
import json
from pathlib import Path
from dotenv import load_dotenv
from library.vectorstores import add_to_vector_store

# Load environment
load_dotenv()

# Set API keys
client = openai.Client(api_key=os.getenv("OPENAI_API_KEY_VDB"))

# usage: python scripts/ingest_world.py <path/to/file> <store_name> [description] [features]
# e.g.,  python scripts/ingest_world.py raw_data/worlds/fiction_continent/fiction_continent_descriptions.docx Fiction "A versatile fantasy realm" "Flexible fantasy setting,Classic D&D elements"

def update_world_metadata(store_name, description=None, features=None):
    """Update world metadata in vectorstores.json"""
    config_path = Path("config/vectorstores.json")
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        config = {"world": {}}
    
    # Ensure the world entry exists
    if "world" not in config:
        config["world"] = {}
    if store_name not in config["world"]:
        config["world"][store_name] = {}
    
    # Update description if provided
    if description:
        config["world"][store_name]["description"] = description
    
    # Update features if provided (convert comma-separated string to list)
    if features:
        if isinstance(features, str):
            features_list = [f.strip() for f in features.split(',')]
        else:
            features_list = features
        config["world"][store_name]["features"] = features_list
    
    # Save updated config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

def main():
    if len(sys.argv) < 3:
        print("usage: python scripts/ingest_world.py <file> <store_name> [description] [features]")
        print("  features should be comma-separated if provided")
        print("e.g., python scripts/ingest_world.py data.docx MyWorld 'A fantasy realm' 'Magic,Dragons,Adventure'")
        raise SystemExit(2)

    file_path = sys.argv[1]
    store_name = sys.argv[2]
    description = sys.argv[3] if len(sys.argv) > 3 else None
    features = sys.argv[4] if len(sys.argv) > 4 else None

    # 1) Create (or find) a vector store
    vs = client.vector_stores.create(name=f"dnd_world_{store_name}")
    print("Vector store:", vs.id)

    # 2) Upload the file
    uploaded = client.files.create(file=open(file_path, "rb"), purpose="assistants")
    print("Uploaded file:", uploaded.id)

    # 3) Attach file to the vector store
    client.vector_stores.files.create(vector_store_id=vs.id, file_id=uploaded.id)
    print("Attached to store. Processing will happen automatically.")

    # 4) Update vector store mapping
    add_to_vector_store("world", store_name, vs.id)
    print(f"Saved mapping: {store_name} → {vs.id}")
    
    # 5) Update world metadata (description and features)
    if description or features:
        update_world_metadata(store_name, description, features)
        print(f"Updated metadata for {store_name}")
        if description:
            print(f"  Description: {description}")
        if features:
            print(f"  Features: {features}")

if __name__ == "__main__":
    main()