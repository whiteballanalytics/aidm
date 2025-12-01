# World Ingestion Script

This script ingests world lore documents into OpenAI vector stores for semantic search during gameplay.

## How It Works

1. **Reads Document**: Loads a world lore document (DOCX, PDF, TXT, etc.)

2. **Creates Vector Store**: Sends the document to OpenAI's Files API and creates a searchable vector store

3. **Registers Store**: Records the vector store ID in `config/vectorstores.json` with metadata (description, features)

4. **Enables Lore Search**: DM agents can now query the world lore during session planning and gameplay