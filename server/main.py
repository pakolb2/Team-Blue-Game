"""
server/main.py
---------------
FastAPI application entry point.

Wires together:
  - RoomManager     (shared game state)
  - ConnectionManager (shared WebSocket registry)
  - WebSocket endpoint /ws/{player_id}
  - HTTP routes for Jinja2 templates (lobby, game, tutorial)
  - Static file serving

Run with:
    uvicorn server.main:app --reload

Or via VS Code launch.json (see .vscode/launch.json).
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from server.rooms.room_manager import RoomManager
from server.sockets.handlers import ConnectionManager, handle_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App-level singletons (created once, shared across all connections)
# ---------------------------------------------------------------------------

room_manager = RoomManager()
connection_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Jass server starting up.")
    yield
    logger.info("Jass server shutting down.")


app = FastAPI(
    title="Jass",
    description="Swiss card game — web multiplayer",
    lifespan=lifespan,
)

# Static files (CSS, JS, card images)
app.mount(
    "/static",
    StaticFiles(directory="client/static"),
    name="static",
)

# Jinja2 templates
templates = Jinja2Templates(directory="client/templates")


# ---------------------------------------------------------------------------
# HTTP routes — serve HTML pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Lobby page — create or join a room."""
    open_rooms = room_manager.list_open_rooms()
    return templates.TemplateResponse(
        request, "home.html",
        {"open_rooms": open_rooms},
    )


@app.get("/game/{room_id}", response_class=HTMLResponse)
async def game(request: Request, room_id: str):
    """Game board page."""
    room_id = room_id.upper()
    try:
        room = room_manager.get_room(room_id)
    except KeyError:
        return HTMLResponse(f"Room '{room_id}' not found.", status_code=404)
    return templates.TemplateResponse(
        request, "game.html",
        {"room_id": room_id, "room": room},
    )


@app.get("/tutorial", response_class=HTMLResponse)
async def tutorial(request: Request):
    """Tutorial page — step-by-step Jass rules guide."""
    return templates.TemplateResponse(
        request, "tutorial.html", {},
    )


# ---------------------------------------------------------------------------
# REST helpers (optional — useful for testing without a browser)
# ---------------------------------------------------------------------------

@app.post("/api/rooms")
async def create_room(variant: str = "schieber"):
    """Create a new room and return its ID."""
    room = room_manager.create_room(variant_name=variant)
    return {"room_id": room.id, "variant": room.variant_name}


@app.get("/api/rooms")
async def list_rooms():
    """List all open (joinable) rooms."""
    rooms = room_manager.list_open_rooms()
    return {
        "rooms": [
            {
                "id": r.id,
                "player_count": len(r.players),
                "max_players": r.max_players,
                "variant_name": r.variant_name,
            }
            for r in rooms
        ]
    }


@app.get("/api/rooms/{room_id}")
async def get_room(room_id: str):
    """Get details about a specific room."""
    room_id = room_id.upper()
    try:
        room = room_manager.get_room(room_id)
    except KeyError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found.")
    return {
        "id": room.id,
        "players": [{"id": p.id, "name": p.name, "is_bot": p.is_bot} for p in room.players],
        "is_full": room.is_full,
        "is_active": room.is_active,
        "variant_name": room.variant_name,
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    """
    Main WebSocket endpoint. Each player connects once with their player_id.

    Message format (JSON):
        { "type": "<event_name>", ...payload... }

    The player_id is set by the client (typically generated in the browser
    with crypto.randomUUID() on first visit and stored in localStorage).
    """
    await connection_manager.connect(player_id, websocket)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await connection_manager.send(
                    player_id,
                    {"type": "error", "message": "Invalid JSON."},
                )
                continue

            await handle_event(
                websocket=websocket,
                player_id=player_id,
                data=data,
                manager=room_manager,
                connections=connection_manager,
            )

    except WebSocketDisconnect:
        connection_manager.disconnect(player_id)

        # Mark player as disconnected in their room if game is active
        room_id = room_manager.find_player_room(player_id)
        if room_id:
            try:
                room = room_manager.leave_room(room_id, player_id)
                await connection_manager.broadcast_to_room(
                    room_id,
                    {"type": "room_updated", "room": {
                        "id": room.id,
                        "players": [
                            {"id": p.id, "name": p.name,
                             "connected": p.connected, "is_bot": p.is_bot}
                            for p in room.players
                        ],
                    }},
                    room_manager,
                    exclude=player_id,
                )
            except Exception as e:
                logger.warning(f"Error cleaning up disconnect for {player_id}: {e}")

    except Exception as e:
        logger.exception(f"WebSocket error for player {player_id}: {e}")
        connection_manager.disconnect(player_id)
