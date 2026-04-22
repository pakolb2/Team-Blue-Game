from server.shared.types import Card
from server.shared.constants import SUITS, RANKS
import random


def build_deck() -> list[Card]:
    """Build a standard 36-card Swiss Jass deck."""
    return [Card(suit=s, rank=r) for s in SUITS for r in RANKS]


def shuffle(deck: list[Card]) -> list[Card]:
    random.shuffle(deck)
    return deck


def deal(deck: list[Card], num_players: int) -> list[list[Card]]:
    """Deal cards evenly to players."""
    hand_size = len(deck) // num_players
    return [deck[i * hand_size:(i + 1) * hand_size] for i in range(num_players)]
