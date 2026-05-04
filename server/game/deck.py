"""
server/game/deck.py
-------------------
Deck building, shuffling, and dealing for the Swiss Jass deck.

The Jass deck has 36 cards: 4 suits × 9 ranks (6 through Ace).
There are no 2s, 3s, 4s, or 5s.

Public API:
    build_deck()              → list[Card]          — fresh ordered deck
    shuffle(deck)             → list[Card]          — shuffled copy
    deal(deck, num_players)   → list[list[Card]]    — hands for each player
    deal_to_players(players)  → list[Player]        — deals directly onto Player objects
"""

from __future__ import annotations

import random
from copy import deepcopy

from server.shared.types import Card, Player, Suit, Rank
from server.shared.constants import SUITS, RANKS, DECK_SIZE, HAND_SIZE, MAX_PLAYERS


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def build_deck() -> list[Card]:
    """
    Build a complete, ordered 36-card Swiss Jass deck.
    Order: all ranks of Eichel, then Schilte, then Schelle, then Rose.
    The order is deterministic so tests can rely on it before shuffling.
    
    assert:
        - The deck contains exactly DECK_SIZE cards.
        - Each card is unique (no duplicates).
        - All suits and ranks are represented correctly.

    return: 
        A list of Card objects representing the full deck.
    """
    deck = [Card(suit=suit, rank=rank) for suit in SUITS for rank in RANKS]
    assert len(deck) == DECK_SIZE, f"Expected {DECK_SIZE} cards, got {len(deck)}"
    return deck


def shuffle(deck: list[Card]) -> list[Card]:
    """
    Return a new shuffled copy of the deck.
    The original list is never mutated.

        Args:
            deck: A list of Card objects to shuffle.

    Returns:
        A new list of Card objects representing the shuffled deck.
    """
    shuffled = list(deck)   # shallow copy — Cards are frozen/immutable so this is safe
    random.shuffle(shuffled)
    return shuffled


def deal(deck: list[Card], num_players: int = MAX_PLAYERS) -> list[list[Card]]:
    """
    Split the deck into equal hands, one per player.
    Cards are dealt round-robin (as in real Jass), so hand[0] gets
    cards 0, num_players, 2*num_players, ... rather than a contiguous slice.

    Args:
        deck:        A 36-card deck (should be shuffled first).
        num_players: Number of hands to deal into. Must divide len(deck) evenly.

    Returns:
        A list of `num_players` hands, each a list[Card].

    Raises:
        ValueError: If the deck cannot be divided evenly.
    """
    if len(deck) % num_players != 0:
        raise ValueError(
            f"Cannot deal {len(deck)} cards evenly to {num_players} players."
        )

    hand_size = len(deck) // num_players
    # Round-robin deal: player i gets cards at indices i, i+num_players, i+2*num_players, ...
    hands: list[list[Card]] = [[] for _ in range(num_players)]
    for i, card in enumerate(deck):
        hands[i % num_players].append(card)

    assert all(len(h) == hand_size for h in hands), "Uneven deal detected"
    return hands


def deal_to_players(players: list[Player]) -> list[Player]:
    """
    Build a fresh deck, shuffle it, deal it, and assign hands to each Player.
    Returns new Player objects (originals are not mutated).

    Args:
        players: Exactly 4 Player objects in seat order.

    Returns:
        Updated Player objects with their hands set.

    Raises:
        ValueError: If the number of players is not exactly MAX_PLAYERS (4).
    """
    if len(players) != MAX_PLAYERS:
        raise ValueError(
            f"Jass requires exactly {MAX_PLAYERS} players, got {len(players)}."
        )

    deck = shuffle(build_deck())
    hands = deal(deck, num_players=len(players))

    updated: list[Player] = []
    for player, hand in zip(players, hands):
        # Pydantic model — create a copy with the new hand
        updated.append(player.model_copy(update={"hand": hand}))

    return updated


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def cards_remaining(players: list[Player]) -> int:
    """Return the total number of cards still held across all players."""
    return sum(len(p.hand) for p in players)


def remove_card(hand: list[Card], card: Card) -> list[Card]:
    """
    Return a new hand list with `card` removed.
    Raises ValueError if the card is not in the hand.
    """
    if card not in hand:
        raise ValueError(f"Card {card} not found in hand.")
    new_hand = list(hand)
    new_hand.remove(card)
    return new_hand
