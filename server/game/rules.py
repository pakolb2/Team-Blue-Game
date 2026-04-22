"""
server/game/rules.py
---------------------
Shared rule-validation helpers used by the GameEngine and all variants.

These functions sit between the engine and the variant classes:
  - The engine calls `get_legal_moves()` and `is_legal()` here
  - These functions delegate to the active variant for the variant-specific logic
  - Common cross-variant checks (empty hand, player turn, game phase) live here

This separation means:
  - Variants stay focused on their own rules (no boilerplate)
  - The engine never calls variant methods directly
  - Adding a new variant requires zero changes here

Public API:
    get_legal_moves(state, player_id, variant)  → list[Card]
    is_legal(state, player_id, card, variant)   → bool
    validate_play(state, player_id, card, variant) → None  (raises on violation)
    is_players_turn(state, player_id)           → bool
    can_game_start(room)                        → bool
    assign_teams(players)                       → list[Player]
    next_trump_player(state)                    → str  (player_id)
"""

from __future__ import annotations

from server.shared.types import Card, GameState, GamePhase, Player, Room, TeamId
from server.game.variants.base import BaseVariant
from server.shared.constants import MAX_PLAYERS, TEAM_A_SEATS, TEAM_B_SEATS


# ---------------------------------------------------------------------------
# Legal move queries
# ---------------------------------------------------------------------------

def get_legal_moves(
    state: GameState,
    player_id: str,
    variant: BaseVariant,
) -> list[Card]:
    """
    Return the cards `player_id` may legally play right now.

    Checks (in order):
      1. Game must be in PLAYING phase
      2. Player must exist and it must be their turn
      3. Player must have cards in hand
      4. Delegates to variant.get_legal_moves() for rule-specific filtering

    Returns an empty list if any precondition fails, so callers never
    need to guard against None.
    """
    if state.phase != GamePhase.PLAYING:
        return []

    if not is_players_turn(state, player_id):
        return []

    player = state.get_player(player_id)
    if not player or not player.hand:
        return []

    return variant.get_legal_moves(state, player_id)


def is_legal(
    state: GameState,
    player_id: str,
    card: Card,
    variant: BaseVariant,
) -> bool:
    """
    Return True if playing `card` is a legal move for `player_id`.

    Shorthand for checking whether `card` appears in get_legal_moves().
    """
    return card in get_legal_moves(state, player_id, variant)


def validate_play(
    state: GameState,
    player_id: str,
    card: Card,
    variant: BaseVariant,
) -> None:
    """
    Raise a descriptive ValueError if the play is illegal.
    Returns None if the play is valid.

    Used by the engine before applying a move to game state.
    Provides clear error messages for the WebSocket error event.
    """
    if state.phase != GamePhase.PLAYING:
        raise ValueError(
            f"Cannot play a card in phase '{state.phase.value}'. "
            f"Game must be in '{GamePhase.PLAYING.value}' phase."
        )

    if not is_players_turn(state, player_id):
        raise ValueError(
            f"It is not {player_id}'s turn. "
            f"Current player: {state.current_player_id}."
        )

    player = state.get_player(player_id)
    if player is None:
        raise ValueError(f"Player '{player_id}' not found in this game.")

    if card not in player.hand:
        raise ValueError(
            f"Card {card} is not in {player_id}'s hand."
        )

    legal = variant.get_legal_moves(state, player_id)
    if card not in legal:
        raise ValueError(
            f"Card {card} is not a legal play for {player_id}. "
            f"Legal moves: {[str(c) for c in legal]}."
        )


# ---------------------------------------------------------------------------
# Turn helpers
# ---------------------------------------------------------------------------

def is_players_turn(state: GameState, player_id: str) -> bool:
    """Return True if it is currently `player_id`'s turn to act."""
    return state.current_player_id == player_id


def next_player_after_trick(state: GameState, trick_winner_id: str) -> str:
    """
    After a trick is completed, the winner leads the next trick.
    Returns the player_id of the trick winner (they go first next trick).
    """
    return trick_winner_id


def next_trump_player(state: GameState) -> str | None:
    """
    Return the player_id who should choose trump next round.
    Trump selection rotates clockwise each round.

    Round 0: player at seat 0
    Round 1: player at seat 1
    ...and so on, wrapping around.
    """
    if not state.players:
        return None
    seat = state.round_number % len(state.players)
    return state.players[seat].id


# ---------------------------------------------------------------------------
# Room / game start validation
# ---------------------------------------------------------------------------

def can_game_start(room: Room) -> bool:
    """
    Return True if the room has enough connected players to start a game.
    Jass requires exactly MAX_PLAYERS (4) players, all connected.
    """
    connected = [p for p in room.players if p.connected]
    return len(connected) == MAX_PLAYERS


def validate_game_start(room: Room) -> None:
    """
    Raise ValueError with a descriptive message if the game cannot start.
    Returns None if all conditions are met.
    """
    connected = [p for p in room.players if p.connected]

    if len(room.players) < MAX_PLAYERS:
        raise ValueError(
            f"Need {MAX_PLAYERS} players to start. "
            f"Currently {len(room.players)} in room."
        )

    if len(connected) < MAX_PLAYERS:
        disconnected = [p.name for p in room.players if not p.connected]
        raise ValueError(
            f"Cannot start: {', '.join(disconnected)} "
            f"{'is' if len(disconnected) == 1 else 'are'} disconnected."
        )

    if room.is_active:
        raise ValueError("A game is already in progress in this room.")


# ---------------------------------------------------------------------------
# Team assignment
# ---------------------------------------------------------------------------

def assign_teams(players: list[Player]) -> list[Player]:
    """
    Assign players to teams based on seat order.
    Seats 0 & 2 → TEAM_A, seats 1 & 3 → TEAM_B.

    This is the standard Jass seating arrangement where partners
    sit across from each other.

    Returns new Player objects (originals not mutated).

    Raises:
        ValueError: if not exactly MAX_PLAYERS players provided.
    """
    if len(players) != MAX_PLAYERS:
        raise ValueError(
            f"Team assignment requires exactly {MAX_PLAYERS} players, "
            f"got {len(players)}."
        )

    updated = []
    for seat, player in enumerate(players):
        team = TeamId.TEAM_A if seat in TEAM_A_SEATS else TeamId.TEAM_B
        updated.append(player.model_copy(update={"team": team}))

    return updated


def get_team_players(state: GameState, team: TeamId) -> list[Player]:
    """Return all players belonging to `team`."""
    return [p for p in state.players if p.team == team]


def get_partner_id(state: GameState, player_id: str) -> str | None:
    """
    Return the player_id of `player_id`'s partner (the other player on the same team).
    Returns None if the player is not found or has no partner.
    """
    player = state.get_player(player_id)
    if not player or player.team is None:
        return None

    teammates = get_team_players(state, player.team)
    partners = [p for p in teammates if p.id != player_id]
    return partners[0].id if partners else None
