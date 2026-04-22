"""
server/rooms/room_manager.py
-----------------------------
Manages the full lifecycle of game rooms: creation, joining, leaving,
bot fill-in, and cleanup.

The RoomManager is a singleton held by the FastAPI app. It sits between
the WebSocket handlers (Phase 8) and the GameEngine (Phase 5):

  WebSocket event → RoomManager → GameEngine → updated GameState
                                              → broadcast to players

Responsibilities:
  - Create and delete rooms
  - Track which WebSocket connections belong to which player/room
  - Assign seats and teams
  - Fill empty seats with bots
  - Start engines when rooms are full
  - Route play_card / choose_trump actions to the right engine
  - Return per-player state views (hands hidden)

One GameEngine instance is created per room when the game starts
and lives until the room is deleted.

Public API:
    create_room(room_id, variant_name)         → Room
    join_room(room_id, player)                 → Room
    leave_room(room_id, player_id)             → Room
    get_room(room_id)                          → Room
    list_rooms()                               → list[Room]
    delete_room(room_id)                       → None
    fill_with_bots(room_id)                    → Room
    start_game(room_id)                        → GameState
    get_engine(room_id)                        → GameEngine | None
    choose_trump(room_id, player_id, mode)     → GameState
    play_card(room_id, player_id, card)        → GameState
    start_next_round(room_id)                  → GameState
"""

from __future__ import annotations

import uuid
from typing import Optional

from server.shared.types import (
    Card, Player, Room, GameState, TrumpMode,
)
from server.game.engine import GameEngine
from server.game.variants.base import BaseVariant
from server.game.variants.schieber import Schieber
from server.game.rules import can_game_start, validate_game_start
from server.bots.random_bot import RandomBot
from server.bots.rule_based_bot import RuleBasedBot
from server.bots.base import BaseBot
from server.shared.constants import MAX_PLAYERS


# ---------------------------------------------------------------------------
# Variant registry
# ---------------------------------------------------------------------------

VARIANT_REGISTRY: dict[str, BaseVariant] = {
    "schieber": Schieber(),
}


def get_variant(name: str) -> BaseVariant:
    """
    Look up a variant by name.
    Raises ValueError for unknown variant names.
    """
    variant = VARIANT_REGISTRY.get(name.lower())
    if variant is None:
        available = ", ".join(VARIANT_REGISTRY.keys())
        raise ValueError(
            f"Unknown variant '{name}'. Available: {available}."
        )
    return variant


# ---------------------------------------------------------------------------
# RoomManager
# ---------------------------------------------------------------------------

class RoomManager:
    """
    Central coordinator for all active rooms and their game engines.

    Thread-safety note: This implementation uses plain dicts — suitable
    for a single-process asyncio server (FastAPI + uvicorn). For
    multi-process deployments, replace with a Redis-backed store.
    """

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._engines: dict[str, GameEngine] = {}
        # player_id → room_id reverse index for fast lookup
        self._player_room: dict[str, str] = {}
        # room_id → {player_id: BaseBot} for bot players
        self._bots: dict[str, dict[str, BaseBot]] = {}

    # ------------------------------------------------------------------
    # Room lifecycle
    # ------------------------------------------------------------------

    def create_room(
        self,
        variant_name: str = "schieber",
        room_id: Optional[str] = None,
    ) -> Room:
        """
        Create a new empty room.

        Args:
            variant_name: Game variant to play (default: 'schieber').
            room_id:      Optional explicit ID. Auto-generated if None.

        Returns:
            The new Room object.

        Raises:
            ValueError: If a room with that ID already exists, or variant unknown.
        """
        get_variant(variant_name)   # validate early

        if room_id is None:
            room_id = str(uuid.uuid4())[:8].upper()

        if room_id in self._rooms:
            raise ValueError(f"Room '{room_id}' already exists.")

        room = Room(
            id=room_id,
            variant_name=variant_name,
            max_players=MAX_PLAYERS,
        )
        self._rooms[room_id] = room
        self._bots[room_id] = {}
        return room

    def get_room(self, room_id: str) -> Room:
        """
        Return the room with the given ID.

        Raises:
            KeyError: If the room does not exist.
        """
        if room_id not in self._rooms:
            raise KeyError(f"Room '{room_id}' not found.")
        return self._rooms[room_id]

    def list_rooms(self) -> list[Room]:
        """Return all rooms, sorted by creation order."""
        return list(self._rooms.values())

    def list_open_rooms(self) -> list[Room]:
        """Return rooms that are not full and not yet active (joinable)."""
        return [
            r for r in self._rooms.values()
            if not r.is_full and not r.is_active
        ]

    def delete_room(self, room_id: str) -> None:
        """
        Remove a room and its engine from memory.
        Silent no-op if the room does not exist.
        """
        room = self._rooms.pop(room_id, None)
        self._engines.pop(room_id, None)
        self._bots.pop(room_id, None)

        if room:
            for player in room.players:
                self._player_room.pop(player.id, None)

    # ------------------------------------------------------------------
    # Player management
    # ------------------------------------------------------------------

    def join_room(self, room_id: str, player: Player) -> Room:
        """
        Add a human player to a room.

        Args:
            room_id: Target room.
            player:  Player to add. player.id must be unique in the room.

        Returns:
            Updated Room.

        Raises:
            KeyError:   Room not found.
            ValueError: Room is full, game already started, or duplicate player ID.
        """
        room = self.get_room(room_id)

        if room.is_active:
            raise ValueError(
                f"Cannot join room '{room_id}': game already in progress."
            )
        if room.is_full:
            raise ValueError(
                f"Cannot join room '{room_id}': room is full "
                f"({room.max_players}/{room.max_players})."
            )
        if player.id in room.player_ids:
            raise ValueError(
                f"Player '{player.id}' is already in room '{room_id}'."
            )

        updated_room = room.model_copy(
            update={"players": room.players + [player]}
        )
        self._rooms[room_id] = updated_room
        self._player_room[player.id] = room_id
        return updated_room

    def leave_room(self, room_id: str, player_id: str) -> Room:
        """
        Remove a player from a room.

        If the game is in progress, the player is marked as disconnected
        rather than fully removed — their seat is held so reconnection works.
        If the game has not started, the player is removed entirely.

        Returns:
            Updated Room.

        Raises:
            KeyError:   Room not found.
            ValueError: Player not in room.
        """
        room = self.get_room(room_id)

        if player_id not in room.player_ids:
            raise ValueError(
                f"Player '{player_id}' is not in room '{room_id}'."
            )

        if room.is_active:
            # Game in progress — mark disconnected, keep seat
            updated_players = [
                p.model_copy(update={"connected": False})
                if p.id == player_id else p
                for p in room.players
            ]
            updated_room = room.model_copy(update={"players": updated_players})
        else:
            # Pre-game — remove entirely
            updated_players = [p for p in room.players if p.id != player_id]
            updated_room = room.model_copy(update={"players": updated_players})
            self._player_room.pop(player_id, None)

        self._rooms[room_id] = updated_room
        return updated_room

    def reconnect_player(self, room_id: str, player_id: str) -> Room:
        """
        Mark a previously disconnected player as connected again.

        Raises:
            KeyError:   Room not found.
            ValueError: Player not in room.
        """
        room = self.get_room(room_id)
        if player_id not in room.player_ids:
            raise ValueError(
                f"Player '{player_id}' is not in room '{room_id}'."
            )
        updated_players = [
            p.model_copy(update={"connected": True})
            if p.id == player_id else p
            for p in room.players
        ]
        updated_room = room.model_copy(update={"players": updated_players})
        self._rooms[room_id] = updated_room
        self._player_room[player_id] = room_id
        return updated_room

    def find_player_room(self, player_id: str) -> Optional[str]:
        """Return the room_id the player is in, or None."""
        return self._player_room.get(player_id)

    # ------------------------------------------------------------------
    # Bot management
    # ------------------------------------------------------------------

    def fill_with_bots(
        self,
        room_id: str,
        bot_class: type[BaseBot] = RuleBasedBot,
    ) -> Room:
        """
        Fill all empty seats in the room with bots.

        Args:
            room_id:   Target room.
            bot_class: Bot type to use (default: RuleBasedBot).

        Returns:
            Updated Room (now full).

        Raises:
            KeyError:   Room not found.
            ValueError: Game already started.
        """
        room = self.get_room(room_id)
        if room.is_active:
            raise ValueError(
                f"Cannot add bots to room '{room_id}': game already started."
            )

        empty_seats = MAX_PLAYERS - len(room.players)
        for i in range(empty_seats):
            bot_id = f"bot_{room_id}_{i}"
            bot = bot_class(bot_id)
            bot_player = Player(
                id=bot_id,
                name=f"Bot {i + 1}",
                is_bot=True,
            )
            room = self.join_room(room_id, bot_player)
            self._bots[room_id][bot_id] = bot

        return room

    def get_bot(self, room_id: str, player_id: str) -> Optional[BaseBot]:
        """Return the bot instance for a player, or None if human."""
        return self._bots.get(room_id, {}).get(player_id)

    def is_bot(self, room_id: str, player_id: str) -> bool:
        """Return True if the player in this room is a bot."""
        return player_id in self._bots.get(room_id, {})

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------

    def start_game(self, room_id: str) -> GameState:
        """
        Validate the room, create a GameEngine, and deal cards.

        Steps:
          1. Validate that the room is ready (4 connected players).
          2. Create a GameEngine with the room's variant.
          3. Call engine.start() to deal and enter TRUMP_SELECT.
          4. If the trump player is a bot, auto-resolve trump immediately.

        Returns:
            GameState after dealing (TRUMP_SELECT phase, or PLAYING if bot picked trump).

        Raises:
            KeyError:   Room not found.
            ValueError: Room not ready (see validate_game_start).
        """
        room = self.get_room(room_id)
        validate_game_start(room)

        variant = get_variant(room.variant_name or "schieber")
        engine = GameEngine.for_room(room_id, room.players, variant)
        self._engines[room_id] = engine

        # Mark room as active
        self._rooms[room_id] = room.model_copy(update={"is_active": True})

        # Deal cards
        state = engine.start()

        # If trump player is a bot, resolve trump immediately
        state = self._auto_bot_trump(room_id, engine)

        return state

    def choose_trump(
        self,
        room_id: str,
        player_id: str,
        mode: TrumpMode,
    ) -> GameState:
        """
        Record a human player's trump choice.

        Returns:
            Updated GameState (PLAYING phase).

        Raises:
            KeyError:   Room or engine not found.
            ValueError: Wrong player or wrong phase.
        """
        engine = self._get_engine_or_raise(room_id)
        return engine.choose_trump(player_id, mode)

    def play_card(
        self,
        room_id: str,
        player_id: str,
        card: Card,
    ) -> GameState:
        """
        Apply a card play, then advance any subsequent bot turns.

        After a human plays, bots in the same trick take their turns
        automatically so the human always gets back a state where it
        is their turn again (or the round/game is over).

        Returns:
            GameState after human + all bot plays in the current trick.

        Raises:
            KeyError:   Room or engine not found.
            ValueError: Illegal move (propagated from engine).
        """
        engine = self._get_engine_or_raise(room_id)
        engine.play_card(player_id, card)

        # Let bots take their turns
        self._advance_bots(room_id, engine)

        return engine.state

    def start_next_round(self, room_id: str) -> GameState:
        """
        Begin a new round after SCORING phase.

        Deals new cards, rotates trump player, resolves bot trump
        selection if needed.

        Returns:
            GameState after dealing (TRUMP_SELECT or PLAYING phase).

        Raises:
            KeyError:   Room or engine not found.
            ValueError: Wrong phase or game already over.
        """
        engine = self._get_engine_or_raise(room_id)
        engine.start_next_round()
        return self._auto_bot_trump(room_id, engine)

    def get_engine(self, room_id: str) -> Optional[GameEngine]:
        """Return the GameEngine for a room, or None if not started."""
        return self._engines.get(room_id)

    def get_state_for(self, room_id: str, player_id: str) -> GameState:
        """
        Return the public game state for a specific player (hands hidden).

        Raises:
            KeyError: Room or engine not found.
        """
        engine = self._get_engine_or_raise(room_id)
        return engine.get_state_for(player_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_engine_or_raise(self, room_id: str) -> GameEngine:
        """Return the engine or raise KeyError with a clear message."""
        self.get_room(room_id)   # raises KeyError if room missing
        engine = self._engines.get(room_id)
        if engine is None:
            raise KeyError(
                f"No active game in room '{room_id}'. Call start_game() first."
            )
        return engine

    def _auto_bot_trump(self, room_id: str, engine: GameEngine) -> GameState:
        """
        If the current trump player is a bot, have it pick trump now.
        Returns the (possibly advanced) GameState.
        """
        from server.shared.types import GamePhase
        state = engine.state
        if state.phase != GamePhase.TRUMP_SELECT:
            return state

        trump_pid = state.trump_player_id
        bot = self.get_bot(room_id, trump_pid)
        if bot is None:
            return state  # human must choose

        player_view = engine.get_state_for(trump_pid)
        mode = bot.choose_trump(player_view)
        return engine.choose_trump(trump_pid, mode)

    def _advance_bots(self, room_id: str, engine: GameEngine) -> None:
        """
        Keep playing bot turns until a human's turn is reached,
        the round ends, or the game is over.
        """
        from server.shared.types import GamePhase

        max_iterations = 40   # safety cap (4 players × 9 tricks + buffer)
        for _ in range(max_iterations):
            state = engine.state

            if state.phase not in (GamePhase.PLAYING,):
                break

            current_pid = state.current_player_id
            bot = self.get_bot(room_id, current_pid)
            if bot is None:
                break   # human's turn — stop

            # Bot takes its turn
            player_view = engine.get_state_for(current_pid)
            legal = engine.variant.get_legal_moves(player_view, current_pid)
            if not legal:
                break
            card = bot.choose_card(player_view, legal)
            engine.play_card(current_pid, card)
