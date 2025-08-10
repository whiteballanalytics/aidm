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

# usage: python scripts/ingest_world.py <path/to/file> <store_name>
# e.g.,  python scripts/ingest_world.py raw_data/worlds/fiction_continent/fiction_continent_descriptions.docx Fiction

def main():
    if len(sys.argv) < 3:
        print("usage: python scripts/ingest_world.py <file> <store_name>")
        raise SystemExit(2)

    file_path = sys.argv[1]
    store_name = sys.argv[2]

    # 1) Create (or find) a vector store
    vs = client.vector_stores.create(name=f"dnd_world_{store_name}")
    print("Vector store:", vs.id)

    # 2) Upload the file
    uploaded = client.files.create(file=open(file_path, "rb"), purpose="assistants")
    print("Uploaded file:", uploaded.id)

    # 3) Attach file to the vector store
    client.vector_stores.files.create(vector_store_id=vs.id, file_id=uploaded.id)
    print("Attached to store. Processing will happen automatically.")

    # 4) Update vector store
    add_to_vector_store("world", store_name, vs.id)
    print(f"Saved mapping: {store_name} → {vs.id}")

if __name__ == "__main__":
    main()