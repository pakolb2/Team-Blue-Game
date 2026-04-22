from abc import ABC, abstractmethod
from server.shared.types import Card, GameState


class BaseVariant(ABC):
    """Abstract interface all Jass variants must implement."""

    @abstractmethod
    def get_legal_moves(self, state: GameState, player_id: str) -> list[Card]:
        pass

    @abstractmethod
    def score_trick(self, trick, state: GameState) -> int:
        pass

    @abstractmethod
    def score_game(self, state: GameState) -> dict:
        pass

    @abstractmethod
    def is_game_over(self, state: GameState) -> bool:
        pass
