"""
server/shared/types.py
----------------------
All Pydantic models used across the Jass codebase.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Suit(str, Enum):
    """The four suits of the Swiss Jass deck."""
    EICHEL  = "Eichel"
    SCHILTE = "Schilte"
    SCHELLE = "Schelle"
    ROSE    = "Rose"


class Rank(str, Enum):
    """Card ranks in the Jass deck (no 2-5)."""
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
    """The 6 ways trump can be chosen in Schieber."""
    EICHEL  = "Eichel"
    SCHILTE = "Schilte"
    SCHELLE = "Schelle"
    ROSE    = "Rose"
    OBENABE = "Obenabe"
    UNDEUFE = "Undeufe"


class GamePhase(str, Enum):
    """The lifecycle stages of a single game round."""
    WAITING      = "waiting"
    TRUMP_SELECT = "trump_select"
    PLAYING      = "playing"
    SCORING      = "scoring"
    FINISHED     = "finished"


class TeamId(str, Enum):
    """Team identifiers for team-based variants."""
    TEAM_A = "team_a"
    TEAM_B = "team_b"


class Card(BaseModel):
    """A single playing card."""
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

    seat_index is explicit lobby seating. Teams are still assigned by the
    engine from the final seat order for team-based variants, but seat_index
    lets the lobby show empty seats, add bots to a chosen seat, and move/swap
    players without relying on raw list position.
    """
    id: str
    name: str
    hand: list[Card] = Field(default_factory=list)
    is_bot: bool = False
    team: Optional[TeamId] = None
    connected: bool = True
    seat_index: Optional[int] = None


class TrickEntry(BaseModel):
    """One card played within a trick, tagged with who played it."""
    player_id: str
    card: Card


class Trick(BaseModel):
    """A single trick (one card from each player)."""
    entries: list[TrickEntry] = Field(default_factory=list)
    winner_id: Optional[str] = None
    lead_suit: Optional[Suit] = None
    points: int = 0

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
    """A lobby room. Holds players before and during a game."""
    id: str
    players: list[Player] = Field(default_factory=list)
    max_players: int = 4
    variant_name: Optional[str] = None
    is_active: bool = False

    @property
    def is_full(self) -> bool:
        return len(self.players) >= self.max_players

    @property
    def player_ids(self) -> list[str]:
        return [p.id for p in self.players]

    @property
    def occupied_seats(self) -> set[int]:
        return {
            p.seat_index
            for p in self.players
            if p.seat_index is not None
        }

    def player_at_seat(self, seat_index: int) -> Optional[Player]:
        return next((p for p in self.players if p.seat_index == seat_index), None)


class GameState(BaseModel):
    """The complete, authoritative snapshot of a game at any point in time."""
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
        return next((p for p in self.players if p.id == player_id), None)

    def get_player_team(self, player_id: str) -> Optional[TeamId]:
        player = self.get_player(player_id)
        return player.team if player else None

    def next_player_id(self, after_id: str) -> Optional[str]:
        ids = [p.id for p in self.players]
        if after_id not in ids:
            return None
        idx = ids.index(after_id)
        return ids[(idx + 1) % len(ids)]

    def public_view(self, for_player_id: str) -> "GameState":
        import copy
        state = copy.deepcopy(self)
        for player in state.players:
            if player.id != for_player_id:
                player.hand = []
        return state


class Variant(BaseModel):
    """Lightweight descriptor for a game variant."""
    name: str
    display_name: str
    description: str = ""
