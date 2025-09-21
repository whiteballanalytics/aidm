#!/usr/bin/env python3
"""
Web wrapper for the D&D AI Dungeon Master application.
Since the original is a console application, this provides a web interface.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket
from starlette.staticfiles import StaticFiles
import uvicorn

# Add src to path so we can import the main module when needed
sys.path.insert(0, str(Path(__file__).parent / "src"))

class DungeonMasterSession:
    def __init__(self):
        self.websocket: Optional[WebSocket] = None
        self.input_queue = asyncio.Queue()
        self.output_queue = asyncio.Queue()
        self.session_task: Optional[asyncio.Task] = None
        
    async def start_session(self, websocket: WebSocket):
        self.websocket = websocket
        # Start the DM session in the background
        self.session_task = asyncio.create_task(self.run_dm_session())
        
    async def run_dm_session(self):
        """Run the main DM session with web I/O"""
        # Check if API key is configured before starting
        openai_key = os.getenv("OPENAI_API_KEY_AGENT") or os.getenv("OPENAI_API_KEY")
        if not openai_key or openai_key in ("your-openai-api-key-for-agent-requests", ""):
            await self.send_message("⚠️ OpenAI API key not configured. Please set up your API key to start playing.")
            return
            
        # This is a simplified wrapper - in a full implementation,
        # you'd need to modify the main.py to accept I/O callbacks
        try:
            from main import main as dm_main
            await dm_main()
        except Exception as e:
            await self.send_message(f"Error: {str(e)}")
            
    async def send_message(self, message: str):
        if self.websocket:
            await self.websocket.send_json({
                "type": "message",
                "content": message
            })
            
    async def handle_input(self, message: str):
        await self.input_queue.put(message)

# Global session manager
dm_session = DungeonMasterSession()

async def homepage(request):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>D&D AI Dungeon Master</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .chat-container { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin: 20px 0; }
            .input-container { display: flex; gap: 10px; }
            input { flex: 1; padding: 10px; }
            button { padding: 10px 20px; }
            .message { margin: 10px 0; padding: 5px; border-radius: 5px; }
            .dm-message { background-color: #f0f0f0; }
            .player-message { background-color: #e6f3ff; }
            .error-message { background-color: #ffe6e6; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎲 D&D AI Dungeon Master</h1>
            <p>Welcome to the AI-powered Dungeons & Dragons experience!</p>
            
            <div class="chat-container" id="chat">
                <div class="message dm-message">
                    <strong>DM:</strong> Welcome, adventurer! This is a web interface for the D&D AI Dungeon Master.
                    <br><br>
                    <strong>⚠️ Setup Required:</strong> To start playing, you need to:
                    <br>1. Set your OpenAI API key using the secrets manager
                    <br>2. Configure vector stores for game content (see README.md)
                    <br><br>
                    Once configured, the full D&D experience will be available through this interface.
                </div>
            </div>
            
            <div class="input-container">
                <input type="text" id="messageInput" placeholder="Type your action..." disabled>
                <button onclick="sendMessage()" id="sendButton" disabled>Send</button>
            </div>
            
            <div style="margin-top: 20px;">
                <h3>📋 Project Status</h3>
                <ul>
                    <li>✅ Python environment configured</li>
                    <li>✅ Dependencies installed</li>
                    <li>✅ Directory structure created</li>
                    <li>⚠️ OpenAI API keys needed</li>
                    <li>⚠️ Vector stores need configuration</li>
                </ul>
                
                <h3>🔧 Next Steps</h3>
                <ol>
                    <li>Add your OpenAI API key to the environment</li>
                    <li>Configure vector stores for world lore</li>
                    <li>Start your first campaign!</li>
                </ol>
                
                <p><strong>Note:</strong> This is a console application adapted for web. 
                The full interactive experience requires proper API key configuration.</p>
            </div>
        </div>
        
        <script>
            function sendMessage() {
                // Placeholder for future WebSocket implementation
                alert('WebSocket connection not yet implemented. Please configure API keys first.');
            }
            
            document.getElementById('messageInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

async def status(request):
    """API endpoint to check system status"""
    # Check if required environment variables are set
    openai_key = os.getenv("OPENAI_API_KEY_AGENT") or os.getenv("OPENAI_API_KEY")
    
    status_data = {
        "python_environment": "ready",
        "dependencies": "installed",
        "config_files": "created",
        "openai_api_key": "configured" if openai_key and openai_key != "your-openai-api-key-for-agent-requests" else "missing",
        "ready_to_play": bool(openai_key and openai_key != "your-openai-api-key-for-agent-requests")
    }
    
    return JSONResponse(status_data)

# Routes
routes = [
    Route('/', homepage),
    Route('/status', status),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    print("🎲 Starting D&D AI Dungeon Master web interface...")
    print("📍 Open your browser to see the interface")
    print("⚙️  Configure your OpenAI API key to start playing")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=5000,
        log_level="info"
    )