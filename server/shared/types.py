from pydantic import BaseModel
from typing import Optional


class Card(BaseModel):
    suit: str
    rank: str


class Player(BaseModel):
    id: str
    name: str
    hand: list[Card] = []
    is_bot: bool = False


class Trick(BaseModel):
    cards: list[Card] = []
    winner_id: Optional[str] = None


class Room(BaseModel):
    id: str
    players: list[Player] = []
    max_players: int = 4


class GameState(BaseModel):
    room_id: str
    players: list[Player]
    current_trick: Trick = Trick()
    tricks: list[Trick] = []
    trump_suit: Optional[str] = None
    current_player_id: Optional[str] = None
    variant: Optional[str] = None
    scores: dict = {}
    game_over: bool = False


class Variant(BaseModel):
    name: str
