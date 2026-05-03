"""
server/sockets/handlers.py
---------------------------
WebSocket event handlers.

Each handler receives:
  - websocket:    The FastAPI WebSocket for the player who sent the event
  - data:         The raw parsed dict from the client
  - manager:      The shared RoomManager instance
  - connections:  The shared ConnectionManager (tracks all open WebSockets)

Handlers call into the RoomManager, then broadcast results via the
ConnectionManager. They never touch game logic directly.

Event flow:
  Client sends JSON → main.py WebSocket endpoint receives it
  → handle_event() dispatches to the right handler
  → handler calls RoomManager
  → handler broadcasts updated state to all players in room
"""

from __future__ import annotations

import json
import logging
from fastapi import WebSocket

from server.rooms.room_manager import RoomManager
from server.shared.types import Card, Suit, Rank, TrumpMode, Player
from server.shared.events import (
    Event, parse_inbound,
    room_updated_msg, game_started_msg, state_updated_msg,
    trick_complete_msg, round_complete_msg, game_over_msg,
    error_msg, rooms_list_msg,
)
from server.shared.types import GamePhase
from server.game.scoring import round_score_summary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """
    Tracks all active WebSocket connections.

    Connections are keyed by player_id. One player → one WebSocket.
    Room membership is handled by the RoomManager — this class only
    knows about raw WebSocket connections.
    """

    def __init__(self) -> None:
        # player_id → WebSocket
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, player_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[player_id] = websocket
        logger.info(f"Player {player_id} connected.")

    def disconnect(self, player_id: str) -> None:
        self._connections.pop(player_id, None)
        logger.info(f"Player {player_id} disconnected.")

    async def send(self, player_id: str, message: dict) -> None:
        """Send a message to a single player. Silent if not connected."""
        ws = self._connections.get(player_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send to {player_id}: {e}")
                self.disconnect(player_id)

    async def broadcast_to_room(
        self,
        room_id: str,
        message: dict,
        manager: RoomManager,
        exclude: str | None = None,
    ) -> None:
        """
        Send `message` to every connected player in `room_id`.
        Optionally exclude one player_id (e.g. the sender).
        """
        try:
            room = manager.get_room(room_id)
        except KeyError:
            return
        for player in room.players:
            if player.id == exclude:
                continue
            await self.send(player.id, message)

    async def broadcast_state(
        self,
        room_id: str,
        manager: RoomManager,
        event_builder,        # callable(state, player_id) → dict
    ) -> None:
        """
        Send a personalised state message to every player in the room.
        Each player receives a view of the state with other hands hidden.
        """
        try:
            room = manager.get_room(room_id)
            engine = manager.get_engine(room_id)
        except KeyError:
            return
        if engine is None:
            return

        for player in room.players:
            if not player.connected:
                continue
            state_view = engine.get_state_for(player.id)
            msg = event_builder(state_view, player.id)
            await self.send(player.id, msg)


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def handle_event(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    """
    Route an incoming WebSocket message to the correct handler.

    Args:
        websocket:   The sender's WebSocket.
        player_id:   The sender's player_id (set at connection time).
        data:        Parsed JSON dict from the client.
        manager:     Shared RoomManager.
        connections: Shared ConnectionManager.
    """
    event_type = data.get("type")

    handlers = {
        Event.JOIN_ROOM:    _handle_join_room,
        Event.LEAVE_ROOM:   _handle_leave_room,
        Event.START_GAME:   _handle_start_game,
        Event.CHOOSE_TRUMP: _handle_choose_trump,
        Event.PLAY_CARD:    _handle_play_card,
        Event.LIST_ROOMS:   _handle_list_rooms,
        "add_bot":          _handle_add_bot,
    }

    handler = handlers.get(event_type)
    if handler is None:
        await connections.send(player_id, error_msg(
            f"Unknown event type: '{event_type}'",
            code="unknown_event",
        ))
        return

    try:
        await handler(websocket, player_id, data, manager, connections)
    except ValueError as e:
        await connections.send(player_id, error_msg(str(e), code="invalid_action"))
    except KeyError as e:
        await connections.send(player_id, error_msg(str(e), code="not_found"))
    except Exception as e:
        logger.exception(f"Unhandled error for player {player_id}: {e}")
        await connections.send(player_id, error_msg(
            "An internal error occurred.", code="internal_error"
        ))


# ---------------------------------------------------------------------------
# Individual event handlers
# ---------------------------------------------------------------------------

async def _handle_join_room(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    """
    Player joins an existing room.

    Flow:
      1. Parse room_id and player_name from data.
      2. Create a Player and join the room.
      3. Broadcast room_updated to everyone already in the room.
      4. Send the updated room back to the joiner.
    """
    room_id = data.get("room_id", "").strip().upper()
    player_name = data.get("player_name", f"Player_{player_id[:4]}")

    if not room_id:
        raise ValueError("room_id is required to join a room.")

    # Check if player is reconnecting to an active game
    existing_room_id = manager.find_player_room(player_id)
    if existing_room_id == room_id:
        room = manager.reconnect_player(room_id, player_id)
        await connections.broadcast_to_room(room_id, room_updated_msg(room), manager)

        # Re-send current game state if game is active
        engine = manager.get_engine(room_id)
        if engine:
            state_view = engine.get_state_for(player_id)
            await connections.send(player_id, state_updated_msg(state_view, player_id))
        return

    player = Player(id=player_id, name=player_name)
    room = manager.join_room(room_id, player)

    # Notify everyone in the room
    await connections.broadcast_to_room(
        room_id, room_updated_msg(room), manager
    )


async def _handle_leave_room(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    """Player leaves a room (or disconnects mid-game)."""
    room_id = data.get("room_id", "").strip().upper()
    if not room_id:
        raise ValueError("room_id is required.")

    room = manager.leave_room(room_id, player_id)
    await connections.broadcast_to_room(
        room_id, room_updated_msg(room), manager
    )

async def _handle_add_bot(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    room_id = data.get("room_id", "").strip().upper()
    bot_type = data.get("bot_type", "rule_based")

    if not room_id:
        raise ValueError("room_id is required.")

    room = manager.add_bot(room_id, bot_type)

    await connections.broadcast_to_room(
        room_id,
        room_updated_msg(room),
        manager,
    )

async def _handle_start_game(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    """
    Host starts the game.

    Flow:
      1. start_game() — deals cards, possibly auto-resolves bot trump.
      2. Broadcast game_started with personalised state to each player.
      3. If phase is already PLAYING (bot picked trump), also broadcast
         state_updated so clients render the playing board immediately.
    """
    room_id = data.get("room_id", "").strip().upper()
    if not room_id:
        raise ValueError("room_id is required.")

    state = manager.start_game(room_id)

    # Send personalised game_started to each player
    await connections.broadcast_state(
        room_id, manager,
        lambda s, pid: game_started_msg(s, pid),
    )


async def _handle_choose_trump(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    """
    Human player selects a trump mode.

    Flow:
      1. Parse trump_mode from data.
      2. choose_trump() — engine records the choice, moves to PLAYING.
      3. Broadcast personalised state_updated to all players.
    """
    room_id = data.get("room_id", "").strip().upper()
    trump_mode_str = data.get("trump_mode", "")

    if not room_id:
        raise ValueError("room_id is required.")

    try:
        trump_mode = TrumpMode(trump_mode_str)
    except ValueError:
        raise ValueError(
            f"Invalid trump mode '{trump_mode_str}'. "
            f"Valid modes: {[m.value for m in TrumpMode]}."
        )

    state = manager.choose_trump(room_id, player_id, trump_mode)

    await connections.broadcast_state(
        room_id, manager,
        lambda s, pid: state_updated_msg(s, pid),
    )


async def _handle_play_card(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    """
    Player plays a card.

    Flow:
      1. Parse card from suit + rank strings.
      2. play_card() — engine validates, applies move, advances bots.
      3. Determine what happened (trick complete? round over? game over?)
      4. Broadcast appropriate events to all players.
    """
    room_id = data.get("room_id", "").strip().upper()
    suit_str = data.get("card_suit", "")
    rank_str = data.get("card_rank", "")

    if not room_id:
        raise ValueError("room_id is required.")

    # Parse card
    try:
        suit = Suit(suit_str)
        rank = Rank(rank_str)
    except ValueError:
        raise ValueError(
            f"Invalid card: suit='{suit_str}' rank='{rank_str}'."
        )

    card = Card(suit=suit, rank=rank)

    # Snapshot completed tricks count before the play
    engine = manager.get_engine(room_id)
    if engine is None:
        raise KeyError(f"No active game in room '{room_id}'.")

    tricks_before = len(engine.state.completed_tricks)
    phase_before = engine.state.phase

    # Apply the play (also advances bots)
    state = manager.play_card(room_id, player_id, card)

    tricks_after = len(state.completed_tricks)
    trick_was_completed = tricks_after > tricks_before

    # --- Broadcast: trick completed ---
    if trick_was_completed:
        await connections.broadcast_state(
            room_id, manager,
            lambda s, pid: trick_complete_msg(s, pid),
        )

    # --- Broadcast: round ended ---
    if state.phase in (GamePhase.SCORING, GamePhase.FINISHED):
        summary = round_score_summary(state)
        if state.game_over:
            await connections.broadcast_to_room(
                room_id, game_over_msg(state, summary), manager
            )
        else:
            await connections.broadcast_to_room(
                room_id, round_complete_msg(state, summary), manager
            )
        return

    # --- Broadcast: normal state update ---
    await connections.broadcast_state(
        room_id, manager,
        lambda s, pid: state_updated_msg(s, pid),
    )


async def _handle_list_rooms(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    """Respond to the requesting player with the list of open rooms."""
    open_rooms = manager.list_open_rooms()
    await connections.send(player_id, rooms_list_msg(open_rooms))
