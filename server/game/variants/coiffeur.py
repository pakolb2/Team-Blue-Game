from server.game.variants.base import BaseVariant
from server.shared.types import Card, GameState


class Coiffeur(BaseVariant):
    """Coiffeur variant — each player must play each game type once."""

    def get_legal_moves(self, state: GameState, player_id: str) -> list[Card]:
        raise NotImplementedError

    def score_trick(self, trick, state: GameState) -> int:
        raise NotImplementedError

    def score_game(self, state: GameState) -> dict:
        raise NotImplementedError

    def is_game_over(self, state: GameState) -> bool:
        raise NotImplementedError
