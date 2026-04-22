from server.bots.base import BaseBot
from server.shared.types import Card, GameState


class RuleBasedBot(BaseBot):
    """Applies basic Jass heuristics to choose a card (e.g. play trump wisely, avoid gifting points)."""

    def choose_card(self, state: GameState, legal_moves: list[Card]) -> Card:
        raise NotImplementedError
