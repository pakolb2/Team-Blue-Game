from server.game.variants.base import BaseVariant
from server.shared.types import Card, GameState


class Schieber(BaseVariant):
    """Standard Schieber variant — most common form of Jass."""

    def get_legal_moves(self, state: GameState, player_id: str) -> list[Card]:
        raise NotImplementedError

    def score_trick(self, trick, state: GameState) -> int:
        raise NotImplementedError

    def score_game(self, state: GameState) -> dict:
        raise NotImplementedError

    def is_game_over(self, state: GameState) -> bool:
        raise NotImplementedError
