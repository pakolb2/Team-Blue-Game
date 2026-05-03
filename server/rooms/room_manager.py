"""
server/rooms/room_manager.py
----------------------------
Room, seating, bot, and game lifecycle management.
"""

from __future__ import annotations

import uuid
from typing import Optional

from server.shared.types import Card, Player, Room, GameState, TrumpMode
from server.game.engine import GameEngine
from server.game.variants.base import BaseVariant
from server.game.variants.schieber import Schieber
from server.game.variants.differenzler import Differenzler, clear_predictions
from server.game.variants.coiffeur import Coiffeur, clear_tracker
from server.game.rules import validate_game_start
from server.bots.random_bot import RandomBot
from server.bots.rule_based_bot import RuleBasedBot
from server.bots.base import BaseBot
from server.shared.constants import MAX_PLAYERS


VARIANT_REGISTRY: dict[str, BaseVariant] = {
    "schieber": Schieber(),
    "differenzler": Differenzler(),
    "coiffeur": Coiffeur(),
}


def get_variant(name: str) -> BaseVariant:
    variant = VARIANT_REGISTRY.get(name.lower())
    if variant is None:
        available = ", ".join(VARIANT_REGISTRY.keys())
        raise ValueError(f"Unknown variant '{name}'. Available: {available}.")
    return variant


class RoomManager:
    """Central coordinator for rooms, seats, bot instances, and game engines."""

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._engines: dict[str, GameEngine] = {}
        self._player_room: dict[str, str] = {}
        self._bots: dict[str, dict[str, BaseBot]] = {}
        # room_id -> target_player_id -> requester_player_id
        self._swap_requests: dict[str, dict[str, str]] = {}

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

        room = Room(id=room_id, variant_name=variant_name, max_players=MAX_PLAYERS)
        self._rooms[room_id] = room
        self._bots[room_id] = {}
        self._swap_requests[room_id] = {}
        return room

    def get_room(self, room_id: str) -> Room:
        if room_id not in self._rooms:
            raise KeyError(f"Room '{room_id}' not found.")
        return self._rooms[room_id]

    def list_rooms(self) -> list[Room]:
        return list(self._rooms.values())

    def list_open_rooms(self) -> list[Room]:
        return [r for r in self._rooms.values() if not r.is_full and not r.is_active]

    def delete_room(self, room_id: str) -> None:
        room = self._rooms.pop(room_id, None)
        self._engines.pop(room_id, None)
        self._bots.pop(room_id, None)
        self._swap_requests.pop(room_id, None)
        clear_predictions(room_id)
        clear_tracker(room_id)
        if room:
            for player in room.players:
                self._player_room.pop(player.id, None)

    # ------------------------------------------------------------------
    # Seat helpers
    # ------------------------------------------------------------------

    def _validate_seat(self, room: Room, seat_index: int) -> None:
        if seat_index < 0 or seat_index >= room.max_players:
            raise ValueError(
                f"Seat {seat_index} is outside the valid range 0-{room.max_players - 1}."
            )

    def _first_free_seat(self, room: Room) -> int:
        occupied = room.occupied_seats
        for seat in range(room.max_players):
            if seat not in occupied:
                return seat
        raise ValueError(f"Room '{room.id}' is full.")

    def _seat_players(self, players: list[Player]) -> list[Player]:
        return sorted(players, key=lambda p: p.seat_index if p.seat_index is not None else 999)

    def _player_at_seat(self, room: Room, seat_index: int) -> Optional[Player]:
        return room.player_at_seat(seat_index)

    def get_swap_requests(self, room_id: str) -> list[dict[str, str]]:
        requests = self._swap_requests.get(room_id, {})
        return [
            {"target_player_id": target, "requester_player_id": requester}
            for target, requester in requests.items()
        ]

    def _clear_swap_requests_for_players(self, room_id: str, *player_ids: str) -> None:
        requests = self._swap_requests.get(room_id, {})
        for target, requester in list(requests.items()):
            if target in player_ids or requester in player_ids:
                requests.pop(target, None)

    # ------------------------------------------------------------------
    # Player management
    # ------------------------------------------------------------------

    def join_room(
        self,
        room_id: str,
        player: Player,
        seat_index: Optional[int] = None,
    ) -> Room:
        room = self.get_room(room_id)

        if room.is_active:
            raise ValueError(f"Cannot join room '{room_id}': game already in progress.")
        if room.is_full:
            raise ValueError(
                f"Cannot join room '{room_id}': room is full ({room.max_players}/{room.max_players})."
            )
        if player.id in room.player_ids:
            raise ValueError(f"Player '{player.id}' is already in room '{room_id}'.")

        if seat_index is None:
            seat_index = self._first_free_seat(room)
        self._validate_seat(room, seat_index)
        if self._player_at_seat(room, seat_index) is not None:
            raise ValueError(f"Seat {seat_index} is already occupied.")

        seated_player = player.model_copy(update={"seat_index": seat_index})
        updated_room = room.model_copy(update={"players": self._seat_players(room.players + [seated_player])})
        self._rooms[room_id] = updated_room
        self._player_room[player.id] = room_id
        return updated_room

    def leave_room(self, room_id: str, player_id: str) -> Room:
        room = self.get_room(room_id)

        if player_id not in room.player_ids:
            raise ValueError(f"Player '{player_id}' is not in room '{room_id}'.")

        if room.is_active:
            updated_players = [
                p.model_copy(update={"connected": False}) if p.id == player_id else p
                for p in room.players
            ]
            updated_room = room.model_copy(update={"players": updated_players})
        else:
            updated_players = [p for p in room.players if p.id != player_id]
            updated_room = room.model_copy(update={"players": self._seat_players(updated_players)})
            self._player_room.pop(player_id, None)
            self._clear_swap_requests_for_players(room_id, player_id)

        self._rooms[room_id] = updated_room
        return updated_room

    def reconnect_player(self, room_id: str, player_id: str) -> Room:
        room = self.get_room(room_id)
        if player_id not in room.player_ids:
            raise ValueError(f"Player '{player_id}' is not in room '{room_id}'.")
        updated_players = [
            p.model_copy(update={"connected": True}) if p.id == player_id else p
            for p in room.players
        ]
        updated_room = room.model_copy(update={"players": updated_players})
        self._rooms[room_id] = updated_room
        self._player_room[player_id] = room_id
        return updated_room

    def find_player_room(self, player_id: str) -> Optional[str]:
        return self._player_room.get(player_id)

    # ------------------------------------------------------------------
    # Seat movement / swap requests
    # ------------------------------------------------------------------

    def move_player_to_seat(self, room_id: str, player_id: str, target_seat: int) -> Room:
        """
        Move player to an empty seat, or instantly swap with a bot.
        Human-occupied seats require a swap request instead.
        """
        room = self.get_room(room_id)
        if room.is_active:
            raise ValueError("Cannot change seats after game has started.")
        self._validate_seat(room, target_seat)

        mover = next((p for p in room.players if p.id == player_id), None)
        if mover is None:
            raise ValueError("Player not found.")

        occupant = self._player_at_seat(room, target_seat)
        if occupant and occupant.id == player_id:
            return room
        if occupant and not occupant.is_bot:
            raise ValueError("Seat is occupied by a human player. Request a swap instead.")

        updated_players: list[Player] = []
        original_seat = mover.seat_index
        for p in room.players:
            if p.id == player_id:
                updated_players.append(p.model_copy(update={"seat_index": target_seat}))
            elif occupant and p.id == occupant.id:
                updated_players.append(p.model_copy(update={"seat_index": original_seat}))
            else:
                updated_players.append(p)

        self._clear_swap_requests_for_players(room_id, player_id, occupant.id if occupant else "")
        updated_room = room.model_copy(update={"players": self._seat_players(updated_players)})
        self._rooms[room_id] = updated_room
        return updated_room

    def request_swap(self, room_id: str, requester_id: str, target_player_id: str) -> Room:
        room = self.get_room(room_id)
        if room.is_active:
            raise ValueError("Cannot request swaps after game has started.")
        if requester_id == target_player_id:
            raise ValueError("Cannot request a swap with yourself.")
        if requester_id not in room.player_ids or target_player_id not in room.player_ids:
            raise ValueError("Player not found.")
        target = next(p for p in room.players if p.id == target_player_id)
        if target.is_bot:
            raise ValueError("Bots do not need swap requests. Move directly instead.")
        self._swap_requests.setdefault(room_id, {})[target_player_id] = requester_id
        return room

    def accept_swap(self, room_id: str, accepter_id: str, requester_id: str) -> Room:
        room = self.get_room(room_id)
        if room.is_active:
            raise ValueError("Cannot accept swaps after game has started.")
        pending_requester = self._swap_requests.get(room_id, {}).get(accepter_id)
        if pending_requester != requester_id:
            raise ValueError("No matching swap request found.")

        players = list(room.players)
        requester = next((p for p in players if p.id == requester_id), None)
        accepter = next((p for p in players if p.id == accepter_id), None)
        if requester is None or accepter is None:
            raise ValueError("Player not found.")

        updated_players = []
        for p in players:
            if p.id == requester.id:
                updated_players.append(p.model_copy(update={"seat_index": accepter.seat_index}))
            elif p.id == accepter.id:
                updated_players.append(p.model_copy(update={"seat_index": requester.seat_index}))
            else:
                updated_players.append(p)

        self._clear_swap_requests_for_players(room_id, requester_id, accepter_id)
        updated_room = room.model_copy(update={"players": self._seat_players(updated_players)})
        self._rooms[room_id] = updated_room
        return updated_room

    def swap_players(self, room_id: str, player_a_id: str, player_b_id: str) -> Room:
        """Backward-compatible immediate swap by player id."""
        room = self.get_room(room_id)
        if room.is_active:
            raise ValueError("Cannot change teams after game has started.")
        a = next((p for p in room.players if p.id == player_a_id), None)
        b = next((p for p in room.players if p.id == player_b_id), None)
        if a is None or b is None:
            raise ValueError("Player not found.")
        updated_players = [
            p.model_copy(update={"seat_index": b.seat_index}) if p.id == a.id
            else p.model_copy(update={"seat_index": a.seat_index}) if p.id == b.id
            else p
            for p in room.players
        ]
        self._clear_swap_requests_for_players(room_id, player_a_id, player_b_id)
        updated_room = room.model_copy(update={"players": self._seat_players(updated_players)})
        self._rooms[room_id] = updated_room
        return updated_room

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
            raise ValueError(f"Cannot add bots to room '{room_id}': game already started.")

        while len(room.players) < room.max_players:
            room = self._add_bot_with_class(room_id, bot_class, "Bot")
        return room

    def _add_bot_with_class(
        self,
        room_id: str,
        bot_class: type[BaseBot],
        bot_name: str,
        seat_index: Optional[int] = None,
    ) -> Room:
        room = self.get_room(room_id)
        if room.is_full:
            raise ValueError(f"Cannot add bot to room '{room_id}': room is full.")
        if seat_index is None:
            seat_index = self._first_free_seat(room)
        self._validate_seat(room, seat_index)
        if self._player_at_seat(room, seat_index) is not None:
            raise ValueError(f"Seat {seat_index} is already occupied.")

        bot_index = len(self._bots[room_id]) + 1
        bot_id = f"bot_{room_id}_{bot_index}"
        bot = bot_class(bot_id)
        bot_player = Player(
            id=bot_id,
            name=f"{bot_name} {bot_index}",
            is_bot=True,
            seat_index=seat_index,
        )
        room = self.join_room(room_id, bot_player, seat_index=seat_index)
        self._bots[room_id][bot_id] = bot
        return room

    def add_bot(
        self,
        room_id: str,
        bot_type: str = "rule_based",
        seat_index: Optional[int] = None,
    ) -> Room:
        room = self.get_room(room_id)
        if room.is_active:
            raise ValueError(f"Cannot add bot to room '{room_id}': game already started.")
        if bot_type == "random":
            return self._add_bot_with_class(room_id, RandomBot, "Random Bot", seat_index)
        if bot_type == "rule_based":
            return self._add_bot_with_class(room_id, RuleBasedBot, "Rule Bot", seat_index)
        raise ValueError(f"Unknown bot type: {bot_type}")

    def get_bot(self, room_id: str, player_id: str) -> Optional[BaseBot]:
        return self._bots.get(room_id, {}).get(player_id)

    def is_bot(self, room_id: str, player_id: str) -> bool:
        return player_id in self._bots.get(room_id, {})

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------

    def start_game(self, room_id: str) -> GameState:
        room = self.get_room(room_id)

        if len(room.players) < room.max_players:
            room = self.fill_with_bots(room_id)

        seated_players = self._seat_players(room.players)
        room = room.model_copy(update={"players": seated_players})
        self._rooms[room_id] = room

        validate_game_start(room)
        variant = get_variant(room.variant_name or "schieber")

        clear_predictions(room_id)
        clear_tracker(room_id)

        engine = GameEngine.for_room(room_id, seated_players, variant)
        self._engines[room_id] = engine
        self._rooms[room_id] = room.model_copy(update={"is_active": True})
        self._swap_requests[room_id] = {}

        state = engine.start()
        state = self._auto_bot_trump(room_id, engine)
        self._on_trump_chosen(room_id, engine)
        return state

    def choose_trump(self, room_id: str, player_id: str, mode: TrumpMode) -> GameState:
        engine = self._get_engine_or_raise(room_id)
        state = engine.choose_trump(player_id, mode)
        self._on_trump_chosen(room_id, engine)
        return state

    def play_card(self, room_id: str, player_id: str, card: Card) -> GameState:
        engine = self._get_engine_or_raise(room_id)
        engine.play_card(player_id, card)
        self._advance_bots(room_id, engine)
        return engine.state

    def start_next_round(self, room_id: str) -> GameState:
        engine = self._get_engine_or_raise(room_id)
        engine.start_next_round()
        state = self._auto_bot_trump(room_id, engine)
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
            raise KeyError(f"No active game in room '{room_id}'. Call start_game() first.")
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
    from server.game.variants.coiffeur import get_available_modes
    return get_available_modes(room_id, team)
