"""
server/bots/base.py
--------------------
Abstract base class for all Jass bots.

Bots are treated as regular players by the engine — the engine never
checks whether a player is human or a bot. The only difference is that
instead of waiting for a WebSocket message, the room manager calls
bot.choose_card() and bot.choose_trump() to get the bot's action,
then feeds it directly into the engine.

Every bot must implement:
    choose_card(state, legal_moves)  → Card
    choose_trump(state)              → TrumpMode

Optional override:
    on_trick_complete(trick, state)  — called after each trick for bots
                                       that want to track game history
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from server.shared.types import Card, GameState, TrumpMode, Trick


class BaseBot(ABC):
    """
    Abstract bot interface.

    A bot knows its own player_id and receives the current GameState
    (with only its own hand visible — same view a human would get).
    """

    def __init__(self, player_id: str) -> None:
        """
        Args:
            player_id: Must match the Player.id this bot controls.
        """
        self.player_id = player_id

    # ------------------------------------------------------------------
    # Required
    # ------------------------------------------------------------------

    @abstractmethod
    def choose_card(self, state: GameState, legal_moves: list[Card]) -> Card:
        """
        Choose a card to play from `legal_moves`.

        Args:
            state:       Public game state (only this bot's hand is visible).
            legal_moves: Non-empty list of cards the bot may legally play.

        Returns:
            One card from `legal_moves`.

        Contract:
            - Must always return a card from `legal_moves`.
            - Must never return a card not in `legal_moves`.
            - Must not modify `state` or `legal_moves`.
        """

    @abstractmethod
    def choose_trump(self, state: GameState) -> TrumpMode:
        """
        Choose a trump mode at the start of a round.

        Args:
            state: Public game state in TRUMP_SELECT phase.
                   The bot's hand is visible (state.get_player(self.player_id).hand).

        Returns:
            One of the 6 TrumpMode values.
        """

    # ------------------------------------------------------------------
    # Optional hook
    # ------------------------------------------------------------------

    def on_trick_complete(self, trick: Trick, state: GameState) -> None:
        """
        Called after each trick is completed and scored.
        Override in subclasses that track game history (e.g. card counting).

        Default: no-op.
        """
