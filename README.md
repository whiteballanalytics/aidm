# DnD AI Dungeon Master

This project is an interactive, turn-based Dungeons & Dragons session runner powered by OpenAI agents. It simulates a Dungeon Master (DM) that can manage lore, campaign memory, and gameplay mechanics, allowing players to experience dynamic storytelling and game logic.

So far the project only contains a back-end that can be run and uses must interact with the tool via the terminal, with text inputs. However, there are ambitions to build a front-end to make the experience more visual and user friendly.

---

## Features

- **Turn-based DnD sessions** with AI-driven Dungeon Master
- **Lore and memory search** using vector stores
- **Dice rolling** for game mechanics
- **Session and campaign management** with persistent storage
- **Extensible agent architecture** for new tools and prompts

---

## Installation & Setup

1. **Clone the repository:**
   ```sh
   git clone https://github.com/whiteballanalytics/aidm
   cd DnD
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   - Create a `.env` file in the root directory.
   - Add your OpenAI API key:
     ```
     OPENAI_API_KEY_AGENT = your-openai-api-key-for-agent-requests
     OPENAI_API_KEY_VDB = your-openai-api-key-vector-database-searches
     ```

4. **Directory structure:**
   - `src/` — Main application code
   - `library/` — Support modules (vectorstores, prompts, logging)
   - `config/` — Configuration files (e.g., memorystores.json) - these correspond to the names of vector stores on https://platform.openai.com/storage/vector_stores.
   - `mirror/` — Persistent storage for campaigns, sessions, and memory - these are currently locally stored to remember details about the campaigns you have personally intitiated / played

5. **Set up config:**
   - Create a `config/vectorstores.json` and pre-populate it with OpenAI vector stores that correspond to the lore of the world you want to work with.
   - Here is an example:
    {
        "world": {
            "Fiction": {
            "vector_store_id": "vs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            }
        }
    }

---

## Usage

Run the main application:

```sh
source venv/bin/activate
python src/main.py
```

- Follow the prompts to start a new campaign or continue an existing one.
- Interact with the Dungeon Master by typing your actions.
- Type `/quit` to exit the session.

---

## Configuration

- **Environment Variables:**  
  Set `OPENAI_API_KEY_AGENT` in your `.env` file.
  Set `OPENAI_API_KEY_VDB` in your `.env` file.
- **Config Files:**  
  - `config/memorystores.json` — Registry for OpenAI vector stores.
- **Persistent Storage:**  
  - `mirror/campaigns/` — Campaign outlines.
  - `mirror/sessions/` — Session logs.
  - `mirror/mem_mirror/` — Memory mirrors.

---

## Extensibility

- **Agents:**  
  Add new agents or tools in `library/` and register them in `main.py`.
- **Prompts:**  
  Customize system prompts in `library/prompts/`.
- **Memory & Lore:**  
  Extend vector store logic in `library/vectorstores.py`.

---

## Testing

- Add unit tests for core functions (dice roller, JSON extraction, scene merging) in a `tests/` directory.
- Use `pytest` or similar frameworks for automated testing.

---

## Contribution Guidelines

1. Fork the repository and create your branch.
2. Write clear, documented code and add tests where appropriate.
3. Submit a pull request with a description of your changes.
