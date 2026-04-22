"""
server/game/variants/base.py
-----------------------------
Abstract base class that every Jass variant must implement.

All game variants (Schieber, Coiffeur, Differenzler, ...) share the same
interface. The GameEngine only talks to this interface — it never imports
a concrete variant directly. This means adding a new variant never touches
the engine or any other existing code.

Contract:
    get_legal_moves(state, player_id)  → list[Card]
    card_rank_value(card, state)       → int          (higher = beats lower)
    score_trick(trick, state)          → int
    score_game(state)                  → dict[TeamId, int]
    is_game_over(state)                → bool
    trick_winner(trick, state)         → str          (player_id)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from server.shared.types import Card, GameState, Trick, TeamId


class BaseVariant(ABC):
    """
    Abstract interface all Jass variants must implement.

    A variant encapsulates:
      - Which cards are legal to play in a given game state
      - How cards rank against each other (to determine trick winner)
      - How many points a completed trick is worth
      - How final game scores are calculated
      - When the game is over
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Short internal name, e.g. 'schieber'."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g. 'Schieber'."""

    # ------------------------------------------------------------------
    # Core game logic — must be implemented by every variant
    # ------------------------------------------------------------------

    @abstractmethod
    def get_legal_moves(self, state: GameState, player_id: str) -> list[Card]:
        """
        Return the list of cards the player is legally allowed to play.

        Rules vary by variant but generally:
          - Must follow the lead suit if possible
          - May play trump if unable to follow suit
          - Special rules apply for trump cards (Buur, Nell)

        Args:
            state:     Current game state (includes current trick, trump, hands)
            player_id: The player whose legal moves to compute

        Returns:
            A non-empty list of Card objects from the player's hand.
            If the hand is empty, returns [].
        """

    @abstractmethod
    def card_rank_value(self, card: Card, state: GameState) -> int:
        """
        Return an integer rank value for `card` in the current game state.
        Higher value = beats lower value cards of the same comparison group.

        Used by trick_winner() to determine who takes the trick.
        Trump cards must rank above all non-trump cards.

        Args:
            card:  The card to rank
            state: Current game state (needed to know what trump is)

        Returns:
            An integer. Scale doesn't matter — only relative ordering.
        """

    @abstractmethod
    def score_trick(self, trick: Trick, state: GameState) -> int:
        """
        Return the point value of a completed trick.

        Args:
            trick: A completed Trick (is_complete == True)
            state: Current game state (needed to know trump mode)

        Returns:
            Integer point value of the trick (0 or more).
        """

    @abstractmethod
    def score_game(self, state: GameState) -> dict[TeamId, int]:
        """
        Calculate and return final scores for all teams at end of a round.
        Includes last-trick bonus and match bonus where applicable.

        Args:
            state: Game state with all tricks completed

        Returns:
            Dict mapping TeamId → total points for this round.
        """

    @abstractmethod
    def is_game_over(self, state: GameState) -> bool:
        """
        Return True if the overall game (potentially multiple rounds) is finished.
        For Schieber this means a team has reached WINNING_SCORE (1000).
        """

    # ------------------------------------------------------------------
    # Derived logic — implemented here using the abstract methods above.
    # Variants can override these if they need different behaviour.
    # ------------------------------------------------------------------

    def trick_winner(self, trick: Trick, state: GameState) -> str:
        """
        Determine which player wins a completed trick.

        The winner is the player who played the highest-ranking card,
        considering only cards that can legally beat the lead card
        (i.e. cards of the lead suit or trump cards).

        Returns:
            player_id of the trick winner.
        """
        if not trick.entries:
            raise ValueError("Cannot determine winner of an empty trick.")

        lead_entry = trick.entries[0]
        lead_suit = lead_entry.card.suit

        # Determine the trump suit (None for Obenabe/Undeufe)
        trump_suit = self._get_trump_suit(state)

        best_entry = lead_entry
        best_value = self.card_rank_value(lead_entry.card, state)

        for entry in trick.entries[1:]:
            card = entry.card
            card_value = self.card_rank_value(card, state)

            # A card can only beat the current best if it is:
            #   (a) of the same suit as the current best card, OR
            #   (b) trump and the current best is not trump
            current_best_is_trump = (
                trump_suit is not None and best_entry.card.suit == trump_suit
            )
            card_is_trump = trump_suit is not None and card.suit == trump_suit
            card_matches_best_suit = card.suit == best_entry.card.suit

            can_beat = card_matches_best_suit or (card_is_trump and not current_best_is_trump)

            if can_beat and card_value > best_value:
                best_entry = entry
                best_value = card_value

        return best_entry.player_id

    def _get_trump_suit(self, state: GameState):
        """
        Return the trump Suit for the current state, or None for
        Obenabe/Undeufe (no-trump modes).
        """
        from server.shared.constants import TRUMP_MODE_TO_SUIT, NO_TRUMP_MODES
        if state.trump_mode is None:
            return None
        if state.trump_mode in NO_TRUMP_MODES:
            return None
        return TRUMP_MODE_TO_SUIT.get(state.trump_mode)
