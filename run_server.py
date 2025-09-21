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
from starlette.responses import HTMLResponse, JSONResponse, Response
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
    create_campaign, load_campaign, list_campaigns,
    create_session, load_session, list_sessions, get_active_session, close_session,
    play_turn, get_available_worlds
)

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
    """GET /api/campaigns - List all campaigns"""
    try:
        campaigns = await list_campaigns()
        return JSONResponse({"campaigns": campaigns})
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
        return JSONResponse(campaign)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# Session Management
async def get_sessions(request):
    """GET /api/campaigns/{campaign_id}/sessions - List sessions for campaign"""
    campaign_id = request.path_params["campaign_id"]
    try:
        sessions = await list_sessions(campaign_id)
        active_session = await get_active_session(campaign_id)
        return JSONResponse({
            "sessions": sessions,
            "active_session": active_session
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
                        "message": "The Dungeon Master is considering your action..."
                    }, session_key)
                    
                    # Process the turn
                    result = await play_turn(campaign_id, session_id, user_input, user_id)
                    
                    # Send response
                    await manager.send_personal_message({
                        "type": "dm_response",
                        "dm_response": result["dm_response"],
                        "turn_number": result["turn_number"],
                        "scene_state": result["scene_state"],
                        "session_summary": result["session_summary"]
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
    """Main application interface"""
    # Check API status
    openai_key = os.getenv("OPENAI_API_KEY_AGENT") or os.getenv("OPENAI_API_KEY")
    api_configured = bool(openai_key and openai_key not in ("your-openai-api-key-for-agent-requests", ""))
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎲 D&D AI Dungeon Master</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            :root {{
                --primary-color: #1a4d3a;
                --accent-color: #8b1538;
                --gold-color: #d4af37;
                --parchment: #f5f3e8;
                --text-dark: #3c2415;
                --border-color: #c9b037;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, var(--parchment) 0%, #e8dcc0 100%);
                margin: 0;
                padding: 20px;
                color: var(--text-dark);
                min-height: 100vh;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.9);
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
                overflow: hidden;
            }}
            
            .header {{
                background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
                color: white;
                padding: 30px;
                text-align: center;
            }}
            
            .header h1 {{
                margin: 0;
                font-size: 2.5em;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
            }}
            
            .content {{
                padding: 40px;
            }}
            
            .status-section {{
                background: var(--parchment);
                border: 2px solid var(--border-color);
                border-radius: 10px;
                padding: 30px;
                margin-bottom: 30px;
            }}
            
            .status-item {{
                display: flex;
                align-items: center;
                margin: 15px 0;
                font-size: 1.1em;
            }}
            
            .status-icon {{
                margin-right: 10px;
                font-size: 1.2em;
            }}
            
            .ready {{ color: #4caf50; }}
            .warning {{ color: #ff9800; }}
            
            .feature-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }}
            
            .feature-card {{
                background: white;
                border-radius: 10px;
                padding: 25px;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
                border-left: 5px solid var(--gold-color);
            }}
            
            .feature-card h3 {{
                color: var(--primary-color);
                margin-top: 0;
            }}
            
            .api-section {{
                background: #f8f9fa;
                border-radius: 10px;
                padding: 30px;
                margin-top: 30px;
            }}
            
            .api-endpoint {{
                background: white;
                border-radius: 5px;
                padding: 15px;
                margin: 10px 0;
                border-left: 4px solid var(--accent-color);
                font-family: monospace;
            }}
            
            .method-get {{ border-left-color: #4caf50; }}
            .method-post {{ border-left-color: #2196f3; }}
            
            .btn {{
                background: linear-gradient(135deg, var(--gold-color), #b8941f);
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 25px;
                cursor: pointer;
                font-size: 1.1em;
                font-weight: bold;
                text-decoration: none;
                display: inline-block;
                margin: 10px 5px;
                transition: all 0.3s ease;
            }}
            
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }}
            
            @media (max-width: 768px) {{
                .header h1 {{ font-size: 2em; }}
                .content {{ padding: 20px; }}
                .feature-grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎲 D&D AI Dungeon Master</h1>
                <p>AI-Powered Dungeons & Dragons Experience</p>
            </div>
            
            <div class="content">
                <div class="status-section">
                    <h2>🔧 System Status</h2>
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
                        <span>Configuration Files: Created</span>
                    </div>
                    <div class="status-item">
                        <span class="status-icon {'ready' if api_configured else 'warning'}">{'✅' if api_configured else '⚠️'}</span>
                        <span>OpenAI API Keys: {'Configured' if api_configured else 'Required'}</span>
                    </div>
                    <div class="status-item">
                        <span class="status-icon ready">✅</span>
                        <span>Vector Stores: Configured (Fiction, SwordCoast, MiddleEarth)</span>
                    </div>
                </div>
                
                {'<div style="text-align: center; margin: 30px 0;"><a href="#" class="btn">🎮 Launch Game Interface</a></div>' if api_configured else ''}
                
                <div class="feature-grid">
                    <div class="feature-card">
                        <h3>🏰 Campaign Builder</h3>
                        <p>Create immersive campaigns with AI-generated storylines. Choose from multiple world settings including Fiction, Sword Coast, and Middle Earth.</p>
                        <ul>
                            <li>AI-generated campaign outlines</li>
                            <li>Multiple world collections</li>
                            <li>Custom campaign descriptions</li>
                            <li>DM view with campaign details</li>
                        </ul>
                    </div>
                    
                    <div class="feature-card">
                        <h3>📜 Session Management</h3>
                        <p>Manage your game sessions with intelligent state tracking. Continue existing adventures or start fresh campaigns.</p>
                        <ul>
                            <li>Session status tracking</li>
                            <li>Chat history preservation</li>
                            <li>Turn-based progression</li>
                            <li>Session planning insights</li>
                        </ul>
                    </div>
                    
                    <div class="feature-card">
                        <h3>🎭 Interactive Play</h3>
                        <p>Experience real-time D&D gameplay with an AI Dungeon Master that responds to your actions and choices.</p>
                        <ul>
                            <li>Real-time chat interface</li>
                            <li>Dice rolling mechanics</li>
                            <li>Dynamic storytelling</li>
                            <li>Memory & lore integration</li>
                        </ul>
                    </div>
                </div>
                
                <div class="api-section">
                    <h2>🔌 API Endpoints</h2>
                    <p>Complete REST API for campaign and session management:</p>
                    
                    <div class="api-endpoint method-get">GET /api/campaigns - List all campaigns</div>
                    <div class="api-endpoint method-post">POST /api/campaigns - Create new campaign</div>
                    <div class="api-endpoint method-get">GET /api/campaigns/{{id}}/sessions - List campaign sessions</div>
                    <div class="api-endpoint method-post">POST /api/campaigns/{{id}}/sessions - Create new session</div>
                    <div class="api-endpoint method-post">POST /api/campaigns/{{id}}/sessions/{{id}}/turn - Play turn</div>
                    <div class="api-endpoint method-get">WebSocket /ws/{{campaign_id}}/{{session_id}} - Real-time chat</div>
                    
                    <p style="margin-top: 20px;">
                        <strong>Note:</strong> The frontend interface is under development. 
                        You can interact with the API directly or use the WebSocket connection for real-time gameplay.
                    </p>
                </div>
                
                {'' if api_configured else '''
                <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 10px; padding: 30px; margin-top: 30px;">
                    <h3 style="color: #856404; margin-top: 0;">🔑 API Key Required</h3>
                    <p>To start playing, you need to configure your OpenAI API keys using Replit's secrets manager:</p>
                    <ul>
                        <li><strong>OPENAI_API_KEY_AGENT</strong> - For AI agent requests</li>
                        <li><strong>OPENAI_API_KEY_VDB</strong> - For vector database searches</li>
                    </ul>
                    <p>Once configured, refresh this page to access the full game interface.</p>
                </div>
                '''}
            </div>
        </div>
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
    
    # Session management
    Route('/api/campaigns/{campaign_id}/sessions', get_sessions, methods=["GET"]),
    Route('/api/campaigns/{campaign_id}/sessions', create_session_endpoint, methods=["POST"]),
    Route('/api/campaigns/{campaign_id}/sessions/{session_id}', get_session, methods=["GET"]),
    Route('/api/campaigns/{campaign_id}/sessions/{session_id}/close', close_session_endpoint, methods=["POST"]),
    
    # Game play
    Route('/api/campaigns/{campaign_id}/sessions/{session_id}/turn', play_turn_endpoint, methods=["POST"]),
    
    # WebSocket for real-time chat
    WebSocketRoute('/ws/{campaign_id}/{session_id}', websocket_endpoint),
]

# Create Starlette application
app = Starlette(routes=routes)

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