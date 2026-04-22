from abc import ABC, abstractmethod
from server.shared.types import Card, GameState


class BaseBot(ABC):
    """Abstract bot interface — bots are treated as players by the engine."""

    def __init__(self, player_id: str):
        self.player_id = player_id

    @abstractmethod
    def choose_card(self, state: GameState, legal_moves: list[Card]) -> Card:
        pass
