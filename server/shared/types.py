"""
server/shared/types.py
----------------------
All Pydantic models used across the Jass codebase.
These are the single source of truth for every data structure —
server game logic, WebSocket messages, and bot interfaces all import from here.

Model hierarchy:
  Card
  Player       (holds list[Card] as hand)
  Trick        (holds list[TrickEntry] — card + who played it)
  Room         (holds list[Player])
  GameState    (holds Room, list[Trick], current Trick, scores, ...)
  Variant      (lightweight name holder — logic lives in variant classes)
  GamePhase    (enum for the stages a game moves through)
  TrumpMode    (enum for the 6 possible trump selections in Schieber)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Suit(str, Enum):
    """The four suits of the Swiss Jass deck."""
    EICHEL  = "Eichel"   # Acorns
    SCHILTE = "Schilte"  # Shields
    SCHELLE = "Schelle"  # Bells
    ROSE    = "Rose"     # Roses


class Rank(str, Enum):
    """Card ranks in the Jass deck (no 2–5)."""
    SIX   = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE  = "9"
    TEN   = "10"
    JACK  = "J"
    QUEEN = "Q"
    KING  = "K"
    ACE   = "A"


class TrumpMode(str, Enum):
    """
    The 6 ways trump can be chosen in Schieber.
    OBENABE and UNEUFE are special modes with no trump suit —
    all suits rank by face value (high-to-low or low-to-high).
    """
    EICHEL  = "Eichel"
    SCHILTE = "Schilte"
    SCHELLE = "Schelle"
    ROSE    = "Rose"
    OBENABE = "Obenabe"   # No trump — Aces are highest
    UNDEUFE = "Undeufe"   # No trump — 6s are highest


class GamePhase(str, Enum):
    """
    The lifecycle stages of a single game round.

      WAITING      — room exists, not enough players yet
      TRUMP_SELECT — cards dealt, the designated player must choose trump
      PLAYING      — trump chosen, tricks being played
      SCORING      — all 9 tricks done, scores being tallied
      FINISHED     — game over, winner determined
    """
    WAITING      = "waiting"
    TRUMP_SELECT = "trump_select"
    PLAYING      = "playing"
    SCORING      = "scoring"
    FINISHED     = "finished"


class TeamId(str, Enum):
    """Two teams in a 4-player game. Players 0 & 2 are TEAM_A, players 1 & 3 are TEAM_B."""
    TEAM_A = "team_a"
    TEAM_B = "team_b"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class Card(BaseModel):
    """
    A single playing card.
    Immutable by convention — never mutate a card, replace it.
    """
    suit: Suit
    rank: Rank

    def __str__(self) -> str:
        return f"{self.rank.value} of {self.suit.value}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return False
        return self.suit == other.suit and self.rank == other.rank

    def __hash__(self) -> int:
        return hash((self.suit, self.rank))

    model_config = {"frozen": True}


class Player(BaseModel):
    """
    A participant in the game — human or bot.
    `hand` is the cards currently held; it shrinks as cards are played.
    `team` is assigned by the room manager based on seat order.
    """
    id: str
    name: str
    hand: list[Card] = Field(default_factory=list)
    is_bot: bool = False
    team: Optional[TeamId] = None
    connected: bool = True   # False if the WebSocket has dropped


class TrickEntry(BaseModel):
    """One card played within a trick, tagged with who played it."""
    player_id: str
    card: Card


class Trick(BaseModel):
    """
    A single trick (one card from each player).
    `entries` is ordered by play sequence.
    `winner_id` is None until the trick is complete and evaluated.
    `lead_suit` is the suit of the first card played — used for follow-suit rules.
    """
    entries: list[TrickEntry] = Field(default_factory=list)
    winner_id: Optional[str] = None
    lead_suit: Optional[Suit] = None
    points: int = 0   # Populated after trick is scored

    @property
    def is_complete(self) -> bool:
        return len(self.entries) == 4

    @property
    def cards(self) -> list[Card]:
        return [e.card for e in self.entries]

    @property
    def player_ids(self) -> list[str]:
        return [e.player_id for e in self.entries]


class TeamScore(BaseModel):
    """Running score for one team across rounds."""
    team: TeamId
    total: int = 0
    round_scores: list[int] = Field(default_factory=list)

    def add_round(self, points: int) -> None:
        self.round_scores.append(points)
        self.total += points


class Room(BaseModel):
    """
    A lobby room. Holds players before and during a game.
    `variant_name` is set when the game starts.
    """
    id: str
    players: list[Player] = Field(default_factory=list)
    max_players: int = 4
    variant_name: Optional[str] = None
    is_active: bool = False   # True once the game has started

    @property
    def is_full(self) -> bool:
        return len(self.players) >= self.max_players

    @property
    def player_ids(self) -> list[str]:
        return [p.id for p in self.players]


class GameState(BaseModel):
    """
    The complete, authoritative snapshot of a game at any point in time.
    The engine mutates this object; clients receive read-only copies.

    Fields:
      room_id         — which room this game belongs to
      players         — ordered list of players (seat 0 leads first)
      phase           — current lifecycle stage (see GamePhase)
      trump_mode      — chosen trump/mode (None during TRUMP_SELECT phase)
      trump_player_id — who gets to choose trump this round
      current_trick   — the trick currently being played
      completed_tricks — all finished tricks this round
      current_player_id — whose turn it is to act
      scores          — team scores
      round_number    — increments each time a full set of 9 tricks is played
      game_over       — True when a team has reached the winning score
      winner          — set when game_over is True
    """
    room_id: str
    players: list[Player]
    phase: GamePhase = GamePhase.WAITING
    trump_mode: Optional[TrumpMode] = None
    trump_player_id: Optional[str] = None
    current_trick: Trick = Field(default_factory=Trick)
    completed_tricks: list[Trick] = Field(default_factory=list)
    current_player_id: Optional[str] = None
    scores: dict[TeamId, TeamScore] = Field(default_factory=dict)
    round_number: int = 0
    game_over: bool = False
    winner: Optional[TeamId] = None

    def get_player(self, player_id: str) -> Optional[Player]:
        """Look up a player by id."""
        return next((p for p in self.players if p.id == player_id), None)

    def get_player_team(self, player_id: str) -> Optional[TeamId]:
        """Return the team of a player."""
        player = self.get_player(player_id)
        return player.team if player else None

    def next_player_id(self, after_id: str) -> Optional[str]:
        """Return the player_id of the next seat after `after_id` (wraps around)."""
        ids = [p.id for p in self.players]
        if after_id not in ids:
            return None
        idx = ids.index(after_id)
        return ids[(idx + 1) % len(ids)]

    def public_view(self, for_player_id: str) -> "GameState":
        """
        Return a copy of this state safe to send to `for_player_id`.
        Other players' hands are hidden (replaced with empty lists).
        """
        import copy
        state = copy.deepcopy(self)
        for player in state.players:
            if player.id != for_player_id:
                player.hand = []
        return state


class Variant(BaseModel):
    """
    Lightweight descriptor for a game variant.
    The actual rule logic lives in server/game/variants/*.py classes.
    This model is used in GameState and API responses to identify the variant by name.
    """
    name: str
    display_name: str
    description: str = ""
