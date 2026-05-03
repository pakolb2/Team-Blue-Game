"""
server/rooms/room_manager.py  (Phase 10 update)
-------------------------------------------------
Adds Differenzler and Coiffeur to the variant registry, and hooks
Coiffeur's on_round_start() into start_game() / start_next_round().

All other logic is unchanged from Phase 7.
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
from server.game.variants.differenzler import Differenzler, clear_predictions
from server.game.variants.coiffeur import Coiffeur, clear_tracker
from server.game.rules import can_game_start, validate_game_start
from server.bots.random_bot import RandomBot
from server.bots.rule_based_bot import RuleBasedBot
from server.bots.base import BaseBot
from server.shared.constants import MAX_PLAYERS


# ---------------------------------------------------------------------------
# Variant registry  (Phase 10: Differenzler + Coiffeur added)
# ---------------------------------------------------------------------------

VARIANT_REGISTRY: dict[str, BaseVariant] = {
    "schieber":     Schieber(),
    "differenzler": Differenzler(),
    "coiffeur":     Coiffeur(),
}


def get_variant(name: str) -> BaseVariant:
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
    See Phase 7 for full documentation.
    """

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._engines: dict[str, GameEngine] = {}
        self._player_room: dict[str, str] = {}
        self._bots: dict[str, dict[str, BaseBot]] = {}

    # ------------------------------------------------------------------
    # Room lifecycle
    # ------------------------------------------------------------------

    def create_room(
        self,
        variant_name: str = "schieber",
        room_id: Optional[str] = None,
    ) -> Room:
        get_variant(variant_name)

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
        if room_id not in self._rooms:
            raise KeyError(f"Room '{room_id}' not found.")
        return self._rooms[room_id]

    def list_rooms(self) -> list[Room]:
        return list(self._rooms.values())

    def list_open_rooms(self) -> list[Room]:
        return [
            r for r in self._rooms.values()
            if not r.is_full and not r.is_active
        ]

    def delete_room(self, room_id: str) -> None:
        room = self._rooms.pop(room_id, None)
        self._engines.pop(room_id, None)
        self._bots.pop(room_id, None)
        # Clean up variant state
        clear_predictions(room_id)
        clear_tracker(room_id)
        if room:
            for player in room.players:
                self._player_room.pop(player.id, None)

    # ------------------------------------------------------------------
    # Player management
    # ------------------------------------------------------------------

    def join_room(self, room_id: str, player: Player) -> Room:
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
        room = self.get_room(room_id)

        if player_id not in room.player_ids:
            raise ValueError(
                f"Player '{player_id}' is not in room '{room_id}'."
            )

        if room.is_active:
            updated_players = [
                p.model_copy(update={"connected": False})
                if p.id == player_id else p
                for p in room.players
            ]
            updated_room = room.model_copy(update={"players": updated_players})
        else:
            updated_players = [p for p in room.players if p.id != player_id]
            updated_room = room.model_copy(update={"players": updated_players})
            self._player_room.pop(player_id, None)

        self._rooms[room_id] = updated_room
        return updated_room

    def reconnect_player(self, room_id: str, player_id: str) -> Room:
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
        return self._player_room.get(player_id)

    # ------------------------------------------------------------------
    # Bot management
    # ------------------------------------------------------------------

    def fill_with_bots(
        self,
        room_id: str,
        bot_class: type[BaseBot] = RuleBasedBot,
    ) -> Room:
        room = self.get_room(room_id)
        if room.is_active:
            raise ValueError(
                f"Cannot add bots to room '{room_id}': game already started."
            )

        empty_seats = MAX_PLAYERS - len(room.players)
        for i in range(empty_seats):
            bot_id = f"bot_{room_id}_{i}"
            bot = bot_class(bot_id)
            bot_player = Player(id=bot_id, name=f"Bot {i + 1}", is_bot=True)
            room = self.join_room(room_id, bot_player)
            self._bots[room_id][bot_id] = bot

        return room

    def get_bot(self, room_id: str, player_id: str) -> Optional[BaseBot]:
        return self._bots.get(room_id, {}).get(player_id)

    def is_bot(self, room_id: str, player_id: str) -> bool:
        return player_id in self._bots.get(room_id, {})

    def add_bot(
        self,
        room_id: str,
        bot_type: str = "rule_based",
    ) -> Room:
        room = self.get_room(room_id)

        if room.is_active:
            raise ValueError(f"Cannot add bot to room '{room_id}': game already started.")

        if room.is_full:
            raise ValueError(f"Cannot add bot to room '{room_id}': room is full.")

        if bot_type == "random":
            bot_class = RandomBot
            bot_name = "Random Bot"
        elif bot_type == "rule_based":
            bot_class = RuleBasedBot
            bot_name = "Rule Bot"
        else:
            raise ValueError(f"Unknown bot type: {bot_type}")

        bot_index = len(self._bots[room_id]) + 1
        bot_id = f"bot_{room_id}_{bot_index}"

        bot = bot_class(bot_id)
        bot_player = Player(
            id=bot_id,
            name=f"{bot_name} {bot_index}",
            is_bot=True,
        )

        room = self.join_room(room_id, bot_player)
        self._bots[room_id][bot_id] = bot
        return room

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------

    def start_game(self, room_id: str) -> GameState:
        room = self.get_room(room_id)

        # Only fill remaining seats, not override manual bots
        if len(room.players) < room.max_players:
            room = self.fill_with_bots(room_id)

        validate_game_start(room)

        variant = get_variant(room.variant_name or "schieber")

        # Clean up any leftover variant state from previous games
        clear_predictions(room_id)
        clear_tracker(room_id)

        engine = GameEngine.for_room(room_id, room.players, variant)
        self._engines[room_id] = engine

        self._rooms[room_id] = room.model_copy(update={"is_active": True})

        state = engine.start()
        state = self._auto_bot_trump(room_id, engine)

        # Hook: notify Coiffeur that a mode was chosen
        self._on_trump_chosen(room_id, engine)

        return state

    def choose_trump(
        self,
        room_id: str,
        player_id: str,
        mode: TrumpMode,
    ) -> GameState:
        engine = self._get_engine_or_raise(room_id)
        state = engine.choose_trump(player_id, mode)

        # Hook: record mode for Coiffeur
        self._on_trump_chosen(room_id, engine)

        return state

    def play_card(
        self,
        room_id: str,
        player_id: str,
        card: Card,
    ) -> GameState:
        engine = self._get_engine_or_raise(room_id)
        engine.play_card(player_id, card)
        self._advance_bots(room_id, engine)
        return engine.state

    def start_next_round(self, room_id: str) -> GameState:
        engine = self._get_engine_or_raise(room_id)
        engine.start_next_round()
        state = self._auto_bot_trump(room_id, engine)

        # Hook: record mode for Coiffeur (bot may have picked immediately)
        self._on_trump_chosen(room_id, engine)

        return state

    def get_engine(self, room_id: str) -> Optional[GameEngine]:
        return self._engines.get(room_id)

    def get_state_for(self, room_id: str, player_id: str) -> GameState:
        engine = self._get_engine_or_raise(room_id)
        return engine.get_state_for(player_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_engine_or_raise(self, room_id: str) -> GameEngine:
        self.get_room(room_id)
        engine = self._engines.get(room_id)
        if engine is None:
            raise KeyError(
                f"No active game in room '{room_id}'. Call start_game() first."
            )
        return engine

    def _auto_bot_trump(self, room_id: str, engine: GameEngine) -> GameState:
        from server.shared.types import GamePhase
        state = engine.state
        if state.phase != GamePhase.TRUMP_SELECT:
            return state

        trump_pid = state.trump_player_id
        bot = self.get_bot(room_id, trump_pid)
        if bot is None:
            return state

        # For Coiffeur: restrict bot to available modes
        variant = engine.variant
        if isinstance(variant, Coiffeur):
            trump_team = state.get_player_team(trump_pid)
            if trump_team:
                available = get_available_modes_for_coiffeur(room_id, trump_team)
                if available:
                    import random
                    mode = random.choice(available)
                else:
                    mode = bot.choose_trump(engine.get_state_for(trump_pid))
            else:
                mode = bot.choose_trump(engine.get_state_for(trump_pid))
        else:
            mode = bot.choose_trump(engine.get_state_for(trump_pid))

        return engine.choose_trump(trump_pid, mode)

    def _on_trump_chosen(self, room_id: str, engine: GameEngine) -> None:
        """Hook called after trump is chosen — notify Coiffeur variant."""
        from server.shared.types import GamePhase
        state = engine.state
        if state.phase == GamePhase.PLAYING:
            variant = engine.variant
            if isinstance(variant, Coiffeur):
                variant.on_round_start(state)

    def _advance_bots(self, room_id: str, engine: GameEngine) -> None:
        from server.shared.types import GamePhase
        max_iterations = 40
        for _ in range(max_iterations):
            state = engine.state
            if state.phase not in (GamePhase.PLAYING,):
                break
            current_pid = state.current_player_id
            bot = self.get_bot(room_id, current_pid)
            if bot is None:
                break
            player_view = engine.get_state_for(current_pid)
            legal = engine.variant.get_legal_moves(player_view, current_pid)
            if not legal:
                break
            card = bot.choose_card(player_view, legal)
            engine.play_card(current_pid, card)


def get_available_modes_for_coiffeur(room_id: str, team) -> list[TrumpMode]:
    """Helper to get available Coiffeur modes for a team."""
    from server.game.variants.coiffeur import get_available_modes
    return get_available_modes(room_id, team)
