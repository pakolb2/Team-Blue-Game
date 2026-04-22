"""
server/bots/random_bot.py
--------------------------
The simplest possible bot — plays a random legal card every turn
and picks a random trump mode.

Used for:
  - Filling empty seats so a human can play immediately
  - Integration testing (fast, deterministic with a seed)
  - Baseline to compare smarter bots against
"""

from __future__ import annotations

import random

from server.bots.base import BaseBot
from server.shared.types import Card, GameState, TrumpMode


class RandomBot(BaseBot):
    """Plays a uniformly random legal card. Picks trump randomly."""

    def choose_card(self, state: GameState, legal_moves: list[Card]) -> Card:
        return random.choice(legal_moves)

    def choose_trump(self, state: GameState) -> TrumpMode:
        return random.choice(list(TrumpMode))
