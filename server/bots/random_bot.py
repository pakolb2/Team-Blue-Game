import random
from server.bots.base import BaseBot
from server.shared.types import Card, GameState


class RandomBot(BaseBot):
    """Plays a random legal card every turn."""

    def choose_card(self, state: GameState, legal_moves: list[Card]) -> Card:
        return random.choice(legal_moves)
