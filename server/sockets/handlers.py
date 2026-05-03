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

import asyncio
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
from server.shared.timing import (
    BOT_ACTION_DELAY_SECONDS,
    TRICK_COMPLETE_PAUSE_SECONDS,
    ROUND_START_PAUSE_SECONDS,
    MAX_AUTOMATED_ACTIONS_PER_RUN,
)

logger = logging.getLogger(__name__)

# Rooms currently being advanced by the socket pacing loop. This prevents two
# concurrent client messages from starting duplicate bot loops for the same room.
_active_bot_runs: set[str] = set()


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
        Event.ADD_BOT:       _handle_add_bot,
        Event.MOVE_SEAT:     _handle_move_seat,
        Event.REQUEST_SWAP:  _handle_request_swap,
        Event.ACCEPT_SWAP:   _handle_accept_swap,
        "swap_players":     _handle_swap_players,
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




def room_update_with_swaps(manager: RoomManager, room_id: str, room) -> dict:
    return room_updated_msg(room, manager.get_swap_requests(room_id))

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
        await connections.broadcast_to_room(room_id, room_update_with_swaps(manager, room_id, room), manager)

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
        room_id, room_update_with_swaps(manager, room_id, room), manager
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
        room_id, room_update_with_swaps(manager, room_id, room), manager
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
    seat_index = data.get("seat_index")
    if seat_index is not None:
        seat_index = int(seat_index)

    if not room_id:
        raise ValueError("room_id is required.")

    room = manager.add_bot(room_id, bot_type, seat_index=seat_index)

    await connections.broadcast_to_room(
        room_id,
        room_update_with_swaps(manager, room_id, room),
        manager,
    )



async def _handle_move_seat(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    room_id = data.get("room_id", "").strip().upper()
    target_seat = data.get("seat_index")

    if not room_id or target_seat is None:
        raise ValueError("room_id and seat_index are required.")

    room = manager.move_player_to_seat(room_id, player_id, int(target_seat))
    await connections.broadcast_to_room(
        room_id,
        room_update_with_swaps(manager, room_id, room),
        manager,
    )


async def _handle_request_swap(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    room_id = data.get("room_id", "").strip().upper()
    target_player_id = data.get("target_player_id")

    if not room_id or not target_player_id:
        raise ValueError("room_id and target_player_id are required.")

    room = manager.request_swap(room_id, player_id, target_player_id)
    await connections.broadcast_to_room(
        room_id,
        room_update_with_swaps(manager, room_id, room),
        manager,
    )


async def _handle_accept_swap(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    room_id = data.get("room_id", "").strip().upper()
    requester_id = data.get("requester_player_id")

    if not room_id or not requester_id:
        raise ValueError("room_id and requester_player_id are required.")

    room = manager.accept_swap(room_id, player_id, requester_id)
    await connections.broadcast_to_room(
        room_id,
        room_update_with_swaps(manager, room_id, room),
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

    The initial state is sent immediately. If a bot is already the active player
    after dealing and optional bot trump selection, bot cards are then paced
    through the same one-action-at-a-time loop as normal play.
    """
    room_id = data.get("room_id", "").strip().upper()
    if not room_id:
        raise ValueError("room_id is required.")

    manager.start_game(room_id)

    await connections.broadcast_state(
        room_id, manager,
        lambda s, pid: game_started_msg(s, pid),
    )
    await _run_bot_turns_with_delay(room_id, manager, connections)


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

    manager.choose_trump(room_id, player_id, trump_mode)

    await connections.broadcast_state(
        room_id, manager,
        lambda s, pid: state_updated_msg(s, pid),
    )
    await _run_bot_turns_with_delay(room_id, manager, connections)


async def _handle_play_card(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    """
    Player plays one card, broadcasts that exact action, then paces any
    following bot turns one card at a time.
    """
    room_id = data.get("room_id", "").strip().upper()
    suit_str = data.get("card_suit", "")
    rank_str = data.get("card_rank", "")

    if not room_id:
        raise ValueError("room_id is required.")

    try:
        suit = Suit(suit_str)
        rank = Rank(rank_str)
    except ValueError:
        raise ValueError(
            f"Invalid card: suit='{suit_str}' rank='{rank_str}'."
        )

    engine = manager.get_engine(room_id)
    if engine is None:
        raise KeyError(f"No active game in room '{room_id}'.")

    tricks_before = len(engine.state.completed_tricks)
    manager.play_card(room_id, player_id, Card(suit=suit, rank=rank))

    should_continue = await _broadcast_after_card_action(
        room_id, manager, connections, tricks_before
    )
    if should_continue:
        await _run_bot_turns_with_delay(room_id, manager, connections)


async def _sleep_if_needed(delay_seconds: float) -> None:
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)


async def _broadcast_after_card_action(
    room_id: str,
    manager: RoomManager,
    connections: ConnectionManager,
    completed_tricks_before: int,
) -> bool:
    """
    Broadcast the visible result of one card play.

    Returns True when automatic play may continue, and False when the game is
    finished or the room no longer has an active engine.
    """
    engine = manager.get_engine(room_id)
    if engine is None:
        return False

    state = engine.state
    trick_completed = len(state.completed_tricks) > completed_tricks_before

    if trick_completed:
        await connections.broadcast_state(
            room_id, manager,
            lambda s, pid: trick_complete_msg(s, pid),
        )
        await _sleep_if_needed(TRICK_COMPLETE_PAUSE_SECONDS)

    if state.phase in (GamePhase.SCORING, GamePhase.FINISHED):
        summary = round_score_summary(state)
        if state.game_over:
            await connections.broadcast_to_room(
                room_id, game_over_msg(state, summary), manager
            )
            return False

        await connections.broadcast_to_room(
            room_id,
            round_complete_msg(
                state,
                summary,
                next_round_delay_seconds=ROUND_START_PAUSE_SECONDS,
            ),
            manager,
        )
        await _sleep_if_needed(ROUND_START_PAUSE_SECONDS)

        manager.start_next_round(room_id)
        await connections.broadcast_state(
            room_id, manager,
            lambda s, pid: state_updated_msg(s, pid),
        )
        return True

    if not trick_completed:
        await connections.broadcast_state(
            room_id, manager,
            lambda s, pid: state_updated_msg(s, pid),
        )

    return True


async def _run_bot_turns_with_delay(
    room_id: str,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    """
    Advance bot turns one visible action at a time until a human must act,
    the round/game ends, or a safety limit is reached.
    """
    if room_id in _active_bot_runs:
        return

    _active_bot_runs.add(room_id)
    try:
        for _ in range(MAX_AUTOMATED_ACTIONS_PER_RUN):
            engine = manager.get_engine(room_id)
            if engine is None:
                return

            state = engine.state
            if state.phase != GamePhase.PLAYING or not state.current_player_id:
                return
            if not manager.is_bot(room_id, state.current_player_id):
                return

            await _sleep_if_needed(BOT_ACTION_DELAY_SECONDS)

            engine = manager.get_engine(room_id)
            if engine is None:
                return
            tricks_before = len(engine.state.completed_tricks)
            state_after = manager.play_one_bot_card(room_id)
            if state_after is None:
                return

            should_continue = await _broadcast_after_card_action(
                room_id, manager, connections, tricks_before
            )
            if not should_continue:
                return

        logger.warning(
            "Stopped automated bot run for room %s after %s actions.",
            room_id,
            MAX_AUTOMATED_ACTIONS_PER_RUN,
        )
    finally:
        _active_bot_runs.discard(room_id)


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

async def _handle_swap_players(
    websocket: WebSocket,
    player_id: str,
    data: dict,
    manager: RoomManager,
    connections: ConnectionManager,
) -> None:
    room_id = data.get("room_id", "").strip().upper()
    player_a = data.get("player_a_id")
    player_b = data.get("player_b_id")

    if not room_id or not player_a or not player_b:
        raise ValueError("room_id, player_a_id, and player_b_id are required.")

    room = manager.swap_players(room_id, player_a, player_b)

    await connections.broadcast_to_room(
        room_id,
        room_update_with_swaps(manager, room_id, room),
        manager,
    )