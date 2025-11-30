#!/usr/bin/env python3
"""
D&D AI Dungeon Master Web API and Interface
Provides REST API endpoints and WebSocket support for the frontend.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, Response, FileResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
import uvicorn

# Add src to path so we can import the game engine
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import game engine functions
from game_engine import (
    create_campaign, load_campaign, list_campaigns, update_last_played,
    create_session, load_session, list_sessions, get_active_session, close_session,
    play_turn, get_available_worlds
)
from main import strip_json_block
from game_engine import extract_narrative_from_runresult

# Import character management module
from characters import (
    import_character_from_dndbeyond,
    list_characters,
    get_character,
    get_character_json,
    delete_character,
)

# Import voice module
from voice import (
    get_voice_controller,
    OpenAITTSProvider,
    is_tts_enabled,
    is_intent_speakable,
)


def initialize_voice():
    """Initialize voice controller with TTS providers."""
    controller = get_voice_controller()
    openai_provider = OpenAITTSProvider(model="tts-1")
    controller.register_tts_provider("openai", openai_provider)
    return controller


voice_controller = initialize_voice()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_key: str):
        await websocket.accept()
        self.active_connections[session_key] = websocket
    
    def disconnect(self, session_key: str):
        if session_key in self.active_connections:
            del self.active_connections[session_key]
    
    async def send_personal_message(self, message: dict, session_key: str):
        if session_key in self.active_connections:
            websocket = self.active_connections[session_key]
            try:
                await websocket.send_json(message)
            except:
                # Connection is probably closed, remove it
                self.disconnect(session_key)

manager = ConnectionManager()


# API Endpoints

# Campaign Management
async def get_campaigns(request):
    """GET /api/campaigns - List campaign IDs only"""
    try:
        campaigns = await list_campaigns()
        
        # Add session counts to each campaign
        for campaign in campaigns:
            try:
                sessions = await list_sessions(campaign["campaign_id"])
                campaign["session_count"] = len(sessions) if sessions else 0
            except Exception:
                campaign["session_count"] = 0
        
        campaign_ids = [c["campaign_id"] for c in campaigns]
        return JSONResponse({"campaign_ids": campaign_ids})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def create_campaign_endpoint(request):
    """POST /api/campaigns - Create a new campaign"""
    try:
        data = await request.json()
        world_collection = data.get("world_collection", "SwordCoast")
        user_description = data.get("description", "")
        campaign_name = data.get("name", "")
        
        campaign = await create_campaign(world_collection, user_description, campaign_name)
        return JSONResponse(campaign, status_code=201)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def get_campaign(request):
    """GET /api/campaigns/{campaign_id} - Get specific campaign"""
    campaign_id = request.path_params["campaign_id"]
    try:
        campaign = await load_campaign(campaign_id)
        if not campaign:
            return JSONResponse({"error": "Campaign not found"}, status_code=404)
        
        # Add session count to campaign data
        try:
            sessions = await list_sessions(campaign_id)
            campaign["session_count"] = len(sessions) if sessions else 0
        except Exception:
            campaign["session_count"] = 0
            
        return JSONResponse(campaign)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def update_campaign_last_played(request):
    """PUT /api/campaigns/{campaign_id}/last_played - Update last played timestamp"""
    campaign_id = request.path_params["campaign_id"]
    try:
        success = await update_last_played(campaign_id)
        if not success:
            return JSONResponse({"error": "Campaign not found"}, status_code=404)
        return JSONResponse({"success": True, "message": "Last played timestamp updated"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# Session Management
async def get_sessions(request):
    """GET /api/campaigns/{campaign_id}/sessions - List session IDs only"""
    campaign_id = request.path_params["campaign_id"]
    try:
        sessions = await list_sessions(campaign_id)
        active_session = await get_active_session(campaign_id)
        session_ids = [s["session_id"] for s in sessions]
        active_id = active_session["session_id"] if active_session else None
        return JSONResponse({
            "session_ids": session_ids,
            "active_session_id": active_id
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def create_session_endpoint(request):
    """POST /api/campaigns/{campaign_id}/sessions - Create new session"""
    campaign_id = request.path_params["campaign_id"]
    try:
        session = await create_session(campaign_id)
        return JSONResponse(session, status_code=201)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def get_session(request):
    """GET /api/campaigns/{campaign_id}/sessions/{session_id} - Get specific session"""
    campaign_id = request.path_params["campaign_id"]
    session_id = request.path_params["session_id"]
    try:
        session = await load_session(campaign_id, session_id)
        if not session:
            return JSONResponse({"error": "Session not found"}, status_code=404)
        return JSONResponse(session)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def close_session_endpoint(request):
    """POST /api/campaigns/{campaign_id}/sessions/{session_id}/close - Close session"""
    campaign_id = request.path_params["campaign_id"]
    session_id = request.path_params["session_id"]
    try:
        session = await close_session(campaign_id, session_id)
        return JSONResponse(session)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# Game Play
async def play_turn_endpoint(request):
    """POST /api/campaigns/{campaign_id}/sessions/{session_id}/turn - Play a turn"""
    campaign_id = request.path_params["campaign_id"]
    session_id = request.path_params["session_id"]
    try:
        data = await request.json()
        user_input = data.get("input", "")
        user_id = data.get("user_id", "web_user")
        
        result = await play_turn(campaign_id, session_id, user_input, user_id)
        
        # Parse DM response to show only user-facing content (for REST fallback)
        clean_response = extract_narrative_from_runresult(result["dm_response"])
        result["dm_response"] = strip_json_block(clean_response)
        
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# Configuration
async def get_worlds(request):
    """GET /api/worlds - Get available world collections"""
    try:
        worlds = get_available_worlds()
        return JSONResponse({"worlds": worlds})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# WebSocket endpoint for real-time chat
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket /ws/{campaign_id}/{session_id} - Real-time game chat"""
    campaign_id = websocket.path_params["campaign_id"]
    session_id = websocket.path_params["session_id"]
    session_key = f"{campaign_id}_{session_id}"
    
    await manager.connect(websocket, session_key)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type", "")
            
            if message_type == "play_turn":
                user_input = data.get("input", "")
                user_id = data.get("user_id", "web_user")
                
                try:
                    # Send "thinking" status
                    await manager.send_personal_message({
                        "type": "dm_thinking",
                        "message": "The Dungeon Master is considering your action... this can take a few minutes"
                    }, session_key)
                    
                    # Process the turn
                    result = await play_turn(campaign_id, session_id, user_input, user_id)
                    
                    # Parse DM response to show only user-facing content
                    clean_response = extract_narrative_from_runresult(result["dm_response"])
                    parsed_dm_response = strip_json_block(clean_response)
                    
                    # Send response
                    await manager.send_personal_message({
                        "type": "dm_response",
                        "dm_response": parsed_dm_response,
                        "turn_number": result["turn_number"],
                        "scene_state": result["scene_state"],
                        "session_summary": result["session_summary"],
                        "intent_used": result.get("intent_used")
                    }, session_key)
                    
                except Exception as e:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": f"Error processing turn: {str(e)}"
                    }, session_key)
            
            elif message_type == "ping":
                await manager.send_personal_message({
                    "type": "pong"
                }, session_key)
                
    except WebSocketDisconnect:
        manager.disconnect(session_key)

async def homepage(request):
    """Main application interface - redirect to game interface"""
    # Check API status
    openai_key = os.getenv("OPENAI_API_KEY_AGENT") or os.getenv("OPENAI_API_KEY")
    api_configured = bool(openai_key and openai_key not in ("your-openai-api-key-for-agent-requests", ""))
    
    if api_configured:
        # Serve the game interface
        game_html_path = Path(__file__).parent / "static" / "html" / "game.html"
        with open(game_html_path, 'r') as f:
            html = f.read()
        return HTMLResponse(html)
    else:
        # Show configuration page
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>🎲 D&D AI Dungeon Master - Setup Required</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link rel="stylesheet" href="/static/css/style.css">
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎲 D&D AI Dungeon Master</h1>
                    <p>AI-Powered Dungeons & Dragons Experience</p>
                </div>
                
                <div class="main-content">
                    <div class="alert alert-warning">
                        <h3>🔑 API Key Configuration Required</h3>
                        <p>To start playing, you need to configure your OpenAI API keys using Replit's secrets manager:</p>
                        <ul>
                            <li><strong>OPENAI_API_KEY_AGENT</strong> - For AI agent requests</li>
                            <li><strong>OPENAI_API_KEY_VDB</strong> - For vector database searches</li>
                        </ul>
                        <p>Once configured, refresh this page to access the full game interface.</p>
                    </div>
                    
                    <div class="card">
                        <h3>System Status</h3>
                        <div class="status-item">
                            <span class="status-icon ready">✅</span>
                            <span>Python Environment: Ready</span>
                        </div>
                        <div class="status-item">
                            <span class="status-icon ready">✅</span>
                            <span>Dependencies: Installed</span>
                        </div>
                        <div class="status-item">
                            <span class="status-icon ready">✅</span>
                            <span>Frontend: Built and Ready</span>
                        </div>
                        <div class="status-item">
                            <span class="status-icon ready">✅</span>
                            <span>Vector Stores: Configured</span>
                        </div>
                        <div class="status-item">
                            <span class="status-icon warning">⚠️</span>
                            <span>OpenAI API Keys: Required</span>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(html)

async def tts_endpoint(request):
    """POST /api/tts - Generate speech from text"""
    try:
        if not is_tts_enabled():
            return JSONResponse(
                {"error": "TTS is not enabled. Set VOICE_TTS_ENABLED=true"},
                status_code=503
            )
        
        data = await request.json()
        text = data.get("text", "")
        intent = data.get("intent")
        
        if not text:
            return JSONResponse({"error": "Text is required"}, status_code=400)
        
        if not is_intent_speakable(intent):
            return JSONResponse(
                {"error": f"Intent '{intent}' is not configured for TTS"},
                status_code=400
            )
        
        audio_data = await voice_controller.synthesize_full(
            text=text,
            intent=intent
        )
        
        if not audio_data:
            return JSONResponse(
                {"error": "Failed to synthesize speech"},
                status_code=500
            )
        
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


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


# Character Management Endpoints
async def import_dndbeyond_character_endpoint(request):
    """POST /api/characters/import/dndbeyond - Import a character from D&D Beyond"""
    import traceback
    try:
        data = await request.json()
        dndbeyond_id = data.get("dndbeyond_id", "").strip()
        campaign_id = data.get("campaign_id")
        
        if not dndbeyond_id:
            return JSONResponse({"error": "dndbeyond_id is required"}, status_code=400)
        
        # Extract numeric ID from URL if full URL was provided
        if "dndbeyond.com" in dndbeyond_id:
            # Extract ID from URL like https://www.dndbeyond.com/characters/115183470
            import re
            match = re.search(r'/characters/(\d+)', dndbeyond_id)
            if match:
                dndbeyond_id = match.group(1)
            else:
                return JSONResponse({"error": "Could not extract character ID from URL"}, status_code=400)
        
        print(f"Importing character from D&D Beyond: {dndbeyond_id}")
        character = await import_character_from_dndbeyond(dndbeyond_id, campaign_id)
        print(f"Successfully imported character: {character.get('name', 'Unknown')}")
        return JSONResponse(character, status_code=201)
        
    except ValueError as e:
        print(f"ValueError importing character: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        print(f"Error importing character: {e}")
        traceback.print_exc()
        error_msg = str(e)
        if "404" in error_msg or "Not Found" in error_msg:
            return JSONResponse({"error": "Character not found. Make sure the character is public on D&D Beyond."}, status_code=404)
        return JSONResponse({"error": f"Failed to import character: {error_msg}"}, status_code=500)


async def get_characters_endpoint(request):
    """GET /api/characters - List all characters"""
    try:
        campaign_id = request.query_params.get("campaign_id")
        characters = await list_characters(campaign_id)
        return JSONResponse({"characters": characters})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def get_character_endpoint(request):
    """GET /api/characters/{character_id} - Get a specific character"""
    character_id = request.path_params["character_id"]
    try:
        character = await get_character(character_id)
        if not character:
            return JSONResponse({"error": "Character not found"}, status_code=404)
        return JSONResponse(character)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def get_character_full_json_endpoint(request):
    """GET /api/characters/{character_id}/json - Get the full D&D Beyond JSON"""
    character_id = request.path_params["character_id"]
    try:
        character_json = await get_character_json(character_id)
        if not character_json:
            return JSONResponse({"error": "Character not found"}, status_code=404)
        return JSONResponse(character_json)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def delete_character_endpoint(request):
    """DELETE /api/characters/{character_id} - Delete a character"""
    character_id = request.path_params["character_id"]
    try:
        deleted = await delete_character(character_id)
        if not deleted:
            return JSONResponse({"error": "Character not found"}, status_code=404)
        return JSONResponse({"success": True, "message": "Character deleted"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Routes configuration
routes = [
    # Main interface
    Route('/', homepage),
    Route('/status', status),
    
    # API endpoints
    Route('/api/worlds', get_worlds, methods=["GET"]),
    
    # Campaign management
    Route('/api/campaigns', get_campaigns, methods=["GET"]),
    Route('/api/campaigns', create_campaign_endpoint, methods=["POST"]),
    Route('/api/campaigns/{campaign_id}', get_campaign, methods=["GET"]),
    Route('/api/campaigns/{campaign_id}/last_played', update_campaign_last_played, methods=["PUT"]),
    
    # Session management
    Route('/api/campaigns/{campaign_id}/sessions', get_sessions, methods=["GET"]),
    Route('/api/campaigns/{campaign_id}/sessions', create_session_endpoint, methods=["POST"]),
    Route('/api/campaigns/{campaign_id}/sessions/{session_id}', get_session, methods=["GET"]),
    Route('/api/campaigns/{campaign_id}/sessions/{session_id}/close', close_session_endpoint, methods=["POST"]),
    
    # Game play
    Route('/api/campaigns/{campaign_id}/sessions/{session_id}/turn', play_turn_endpoint, methods=["POST"]),
    
    # Voice/TTS
    Route('/api/tts', tts_endpoint, methods=["POST"]),
    
    # Character management
    Route('/api/characters', get_characters_endpoint, methods=["GET"]),
    Route('/api/characters/import/dndbeyond', import_dndbeyond_character_endpoint, methods=["POST"]),
    Route('/api/characters/{character_id}', get_character_endpoint, methods=["GET"]),
    Route('/api/characters/{character_id}', delete_character_endpoint, methods=["DELETE"]),
    Route('/api/characters/{character_id}/json', get_character_full_json_endpoint, methods=["GET"]),
    
    # WebSocket for real-time chat
    WebSocketRoute('/ws/{campaign_id}/{session_id}', websocket_endpoint),
]

# Create Starlette application
app = Starlette(routes=routes)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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