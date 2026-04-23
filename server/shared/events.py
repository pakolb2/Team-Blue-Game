"""
server/shared/events.py
------------------------
WebSocket event name constants and message envelope models.

Every message between client and server follows the same envelope:
    { "type": "<event_name>", ...payload fields... }

This file defines:
  - Event  — string constants for every event type (avoids typos)
  - Pydantic models for every inbound and outbound message

The JS client (client/static/js/socket.js) uses the same event name
strings, so any change here must be mirrored there.

Inbound (Client → Server):
    join_room       player wants to join a room
    leave_room      player leaving
    start_game      host starts the game
    choose_trump    player picks a trump mode
    play_card       player plays a card
    list_rooms      player requests open room list

Outbound (Server → Client):
    room_updated    room player list changed
    game_started    game has begun (initial state)
    state_updated   game state changed after an action
    trick_complete  a trick was just finished (before next lead)
    round_complete  a round ended — includes round scores
    game_over       game finished — final scores and winner
    error           something went wrong
    rooms_list      response to list_rooms request
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel

from server.shared.types import (
    Card, GameState, Room, TrumpMode, TeamId, TeamScore,
)


# ---------------------------------------------------------------------------
# Event name constants
# ---------------------------------------------------------------------------

class Event:
    """String constants for all WebSocket event types."""

    # Client → Server
    JOIN_ROOM    = "join_room"
    LEAVE_ROOM   = "leave_room"
    START_GAME   = "start_game"
    CHOOSE_TRUMP = "choose_trump"
    PLAY_CARD    = "play_card"
    LIST_ROOMS   = "list_rooms"

    # Server → Client
    ROOM_UPDATED    = "room_updated"
    GAME_STARTED    = "game_started"
    STATE_UPDATED   = "state_updated"
    TRICK_COMPLETE  = "trick_complete"
    ROUND_COMPLETE  = "round_complete"
    GAME_OVER       = "game_over"
    ERROR           = "error"
    ROOMS_LIST      = "rooms_list"


# ---------------------------------------------------------------------------
# Inbound message models (Client → Server)
# ---------------------------------------------------------------------------

class JoinRoomMessage(BaseModel):
    type: str = Event.JOIN_ROOM
    room_id: str
    player_id: str
    player_name: str


class LeaveRoomMessage(BaseModel):
    type: str = Event.LEAVE_ROOM
    room_id: str
    player_id: str


class StartGameMessage(BaseModel):
    type: str = Event.START_GAME
    room_id: str
    player_id: str          # must be the room host (first to join)


class ChooseTrumpMessage(BaseModel):
    type: str = Event.CHOOSE_TRUMP
    room_id: str
    player_id: str
    trump_mode: str         # TrumpMode value string, e.g. "Eichel"


class PlayCardMessage(BaseModel):
    type: str = Event.PLAY_CARD
    room_id: str
    player_id: str
    card_suit: str          # Suit value string, e.g. "Rose"
    card_rank: str          # Rank value string, e.g. "A"


class ListRoomsMessage(BaseModel):
    type: str = Event.LIST_ROOMS


# ---------------------------------------------------------------------------
# Outbound message builders (Server → Client)
# ---------------------------------------------------------------------------

def room_updated_msg(room: Room) -> dict:
    """Broadcast when a player joins or leaves a room."""
    return {
        "type": Event.ROOM_UPDATED,
        "room": {
            "id": room.id,
            "players": [
                {"id": p.id, "name": p.name, "is_bot": p.is_bot,
                 "connected": p.connected}
                for p in room.players
            ],
            "is_full": room.is_full,
            "is_active": room.is_active,
            "variant_name": room.variant_name,
            "max_players": room.max_players,
        },
    }


def game_started_msg(state: GameState, for_player_id: str) -> dict:
    """
    Sent to every player when the game starts.
    Each player receives a personalised view (only their own hand visible).
    """
    return {
        "type": Event.GAME_STARTED,
        "state": _serialise_state(state, for_player_id),
    }


def state_updated_msg(state: GameState, for_player_id: str) -> dict:
    """
    Sent after every action (play_card, choose_trump).
    The main message the client uses to re-render the board.
    """
    return {
        "type": Event.STATE_UPDATED,
        "state": _serialise_state(state, for_player_id),
    }


def trick_complete_msg(state: GameState, for_player_id: str) -> dict:
    """
    Sent after a trick is resolved, before the next lead.
    Includes the completed trick for animation purposes.
    """
    last_trick = state.completed_tricks[-1] if state.completed_tricks else None
    return {
        "type": Event.TRICK_COMPLETE,
        "trick": _serialise_trick(last_trick) if last_trick else None,
        "winner_id": last_trick.winner_id if last_trick else None,
        "points": last_trick.points if last_trick else 0,
        "state": _serialise_state(state, for_player_id),
    }


def round_complete_msg(state: GameState, summary: dict) -> dict:
    """
    Broadcast when a full round (9 tricks) ends.
    Includes the round score summary for the scoreboard.
    """
    return {
        "type": Event.ROUND_COMPLETE,
        "scores": summary,
        "round_number": state.round_number,
        "game_over": state.game_over,
    }


def game_over_msg(state: GameState, summary: dict) -> dict:
    """Broadcast when the game is finished."""
    return {
        "type": Event.GAME_OVER,
        "winner": state.winner.value if state.winner else None,
        "scores": summary,
        "final_totals": {
            team.value: ts.total
            for team, ts in state.scores.items()
        },
    }


def error_msg(message: str, code: str = "error") -> dict:
    """Sent to a single client when their action fails."""
    return {
        "type": Event.ERROR,
        "code": code,
        "message": message,
    }


def rooms_list_msg(rooms: list[Room]) -> dict:
    """Response to a list_rooms request."""
    return {
        "type": Event.ROOMS_LIST,
        "rooms": [
            {
                "id": r.id,
                "player_count": len(r.players),
                "max_players": r.max_players,
                "is_active": r.is_active,
                "variant_name": r.variant_name,
            }
            for r in rooms
        ],
    }


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _serialise_state(state: GameState, for_player_id: str) -> dict:
    """
    Convert a GameState to a JSON-safe dict for `for_player_id`.
    Other players' hands are hidden (empty list) but hand_count is preserved.
    """
    # Capture hand counts BEFORE hiding (public_view empties other hands)
    hand_counts = {p.id: len(p.hand) for p in state.players}
    view = state.public_view(for_player_id)

    return {
        "room_id": view.room_id,
        "phase": view.phase.value,
        "trump_mode": view.trump_mode.value if view.trump_mode else None,
        "trump_player_id": view.trump_player_id,
        "current_player_id": view.current_player_id,
        "round_number": view.round_number,
        "game_over": view.game_over,
        "winner": view.winner.value if view.winner else None,
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "team": p.team.value if p.team else None,
                "is_bot": p.is_bot,
                "connected": p.connected,
                "hand": [
                    {"suit": c.suit.value, "rank": c.rank.value}
                    for c in p.hand
                ],
                "hand_count": hand_counts.get(p.id, 0),
            }
            for p in view.players
        ],
        "current_trick": _serialise_trick(view.current_trick),
        "completed_tricks_count": len(view.completed_tricks),
        "scores": {
            team.value: {
                "total": ts.total,
                "round_scores": ts.round_scores,
            }
            for team, ts in view.scores.items()
        },
    }


def _serialise_trick(trick) -> dict | None:
    if trick is None:
        return None
    return {
        "entries": [
            {
                "player_id": e.player_id,
                "card": {"suit": e.card.suit.value, "rank": e.card.rank.value},
            }
            for e in trick.entries
        ],
        "lead_suit": trick.lead_suit.value if trick.lead_suit else None,
        "winner_id": trick.winner_id,
        "points": trick.points,
    }


# ---------------------------------------------------------------------------
# Inbound message parsing
# ---------------------------------------------------------------------------

def parse_inbound(data: dict) -> Optional[Any]:
    """
    Parse a raw dict from the WebSocket into a typed message model.
    Returns None if the event type is unrecognised.
    """
    event_type = data.get("type")
    try:
        if event_type == Event.JOIN_ROOM:
            return JoinRoomMessage(**data)
        if event_type == Event.LEAVE_ROOM:
            return LeaveRoomMessage(**data)
        if event_type == Event.START_GAME:
            return StartGameMessage(**data)
        if event_type == Event.CHOOSE_TRUMP:
            return ChooseTrumpMessage(**data)
        if event_type == Event.PLAY_CARD:
            return PlayCardMessage(**data)
        if event_type == Event.LIST_ROOMS:
            return ListRoomsMessage(**data)
    except Exception:
        return None
    return None
