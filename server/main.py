"""
server/main.py  (Phase 11 update)
----------------------------------
Adds:
  - LAN discovery router (/api/lan/...)
  - Optional UDP broadcast on startup
  - Sound/animation settings endpoint
  - Variant listing endpoint for lobby
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
from server.game.variants.registry import VARIANT_REGISTRY
from server.sockets.handlers import ConnectionManager, handle_event
from server.lan_discovery import router as lan_router, start_udp_broadcast

logger = logging.getLogger(__name__)

room_manager       = RoomManager()
connection_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Announce on LAN at startup (optional — comment out if not needed)
    try:
        start_udp_broadcast(port=4445)
    except Exception as e:
        logger.warning(f"UDP broadcast unavailable: {e}")
    logger.info("Jass server ready.")
    yield
    logger.info("Jass server shutting down.")


app = FastAPI(
    title="Jass",
    description="Swiss card game — web multiplayer",
    lifespan=lifespan,
)

app.include_router(lan_router)

app.mount("/static", StaticFiles(directory="client/static"), name="static")
templates = Jinja2Templates(directory="client/templates")


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    open_rooms = room_manager.list_open_rooms()
    return templates.TemplateResponse(
        request, "home.html", {"open_rooms": open_rooms}
    )


@app.get("/game/{room_id}", response_class=HTMLResponse)
async def game(request: Request, room_id: str):
    room_id = room_id.upper()
    try:
        room = room_manager.get_room(room_id)
    except KeyError:
        return HTMLResponse(f"Room '{room_id}' not found.", status_code=404)
    return templates.TemplateResponse(
        request, "game.html", {"room_id": room_id, "room": room}
    )


@app.get("/tutorial", response_class=HTMLResponse)
async def tutorial(request: Request):
    return templates.TemplateResponse(request, "tutorial.html", {})


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@app.post("/api/rooms")
async def create_room(variant: str = "schieber"):
    room = room_manager.create_room(variant_name=variant)
    return {"room_id": room.id, "variant": room.variant_name}


@app.get("/api/rooms")
async def list_rooms():
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
    room_id = room_id.upper()
    try:
        room = room_manager.get_room(room_id)
    except KeyError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found.")
    return {
        "id": room.id,
        "players": [
            {"id": p.id, "name": p.name, "is_bot": p.is_bot}
            for p in room.players
        ],
        "is_full": room.is_full,
        "is_active": room.is_active,
        "variant_name": room.variant_name,
    }


@app.get("/api/variants")
async def list_variants():
    """Return available game variants for the lobby picker."""
    return {
        "variants": [
            {"name": v.name, "display_name": v.display_name}
            for v in VARIANT_REGISTRY.values()
        ]
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
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
        room_id = room_manager.find_player_room(player_id)
        if room_id:
            try:
                room = room_manager.leave_room(room_id, player_id)
                await connection_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "room_updated",
                        "room": {
                            "id": room.id,
                            "players": [
                                {
                                    "id": p.id,
                                    "name": p.name,
                                    "connected": p.connected,
                                    "is_bot": p.is_bot,
                                }
                                for p in room.players
                            ],
                        },
                    },
                    room_manager,
                    exclude=player_id,
                )
            except Exception as e:
                logger.warning(f"Cleanup error for {player_id}: {e}")

    except Exception as e:
        logger.exception(f"WebSocket error for {player_id}: {e}")
        connection_manager.disconnect(player_id)


