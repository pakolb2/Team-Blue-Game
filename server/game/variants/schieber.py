"""
server/game/variants/schieber.py
---------------------------------
Full implementation of the Schieber variant — the standard form of Jass.

Rules implemented:
  Trump selection
  ---------------
  - The player who is dealt the cards first may choose trump or "push" (schieben)
    to their partner, who must then choose.
  - Six trump modes: Eichel, Schilte, Schelle, Rose, Obenabe, Undeufe.

  Card ranking
  ------------
  - In a trump suit:   Buur (J) > Nell (9) > A > K > Q > 10 > 8 > 7 > 6
  - In a normal suit:  A > K > Q > J > 10 > 9 > 8 > 7 > 6
  - Obenabe (no trump): A > K > Q > J > 10 > 9 > 8 > 7 > 6  (all suits equal)
  - Undeufe (no trump): 6 > 7 > 8 > 9 > 10 > J > Q > K > A  (all suits reversed)

  Legal moves
  -----------
  - Must follow the lead suit if possible.
  - Exception: the Buur (Jack of trump) is ALWAYS allowed, even if you have
    other trump cards but cannot follow suit.
  - If you cannot follow suit, you may play any card (including trump).
  - If the lead suit IS trump, you must play trump if you have it —
    but you are never forced to play the Buur or Nell if the only
    card winning is a higher trump you don't want to sacrifice.
    (Simplified rule: must follow trump suit, Buur is always free.)

  Scoring
  -------
  - Trump suit: Buur=20, Nell=14, A=11, K=4, Q=3, 10=10, 8/7/6=0
  - Normal suit: A=11, K=4, Q=3, J=2, 10=10, 9/8/7/6=0
  - Obenabe/Undeufe: same as normal suit scoring
  - Last trick bonus: +5 to the winning team
  - Match bonus: +100 if one team wins ALL 9 tricks

  Winning condition
  -----------------
  - First team to reach 1000 points wins.
"""

from __future__ import annotations

from server.game.variants.base import BaseVariant
from server.shared.types import Card, GameState, Trick, TeamId, Suit, Rank, TrumpMode
from server.shared.constants import (
    BASE_CARD_POINTS,
    TRUMP_CARD_POINTS,
    UNDEUFE_CARD_POINTS,
    NORMAL_RANK_ORDER,
    TRUMP_RANK_ORDER,
    UNDEUFE_RANK_ORDER,
    LAST_TRICK_BONUS,
    MATCH_BONUS,
    WINNING_SCORE,
    NO_TRUMP_MODES,
    TRUMP_MODE_TO_SUIT,
    TOTAL_ROUND_POINTS,
)


class Schieber(BaseVariant):
    """Standard Schieber variant — the most common form of Swiss Jass."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "schieber"

    @property
    def display_name(self) -> str:
        return "Schieber"

    # ------------------------------------------------------------------
    # Card ranking
    # ------------------------------------------------------------------

    def card_rank_value(self, card: Card, state: GameState) -> int:
        """
        Return a numeric rank value for the card.
        Higher = stronger. Used by trick_winner() to resolve tricks.

        Trump cards get a large offset (+100) so they always beat non-trump.
        Within trump, the order is:  6(0) 7(1) 8(2) 10(3) Q(4) K(5) A(6) Nell(7) Buur(8)
        Within normal suits: 6(0) 7(1) 8(2) 9(3) 10(4) J(5) Q(6) K(7) A(8)
        """
        trump_suit = self._get_trump_suit(state)
        trump_mode = state.trump_mode

        # --- Obenabe: no trump, Aces highest ---
        if trump_mode == TrumpMode.OBENABE:
            return NORMAL_RANK_ORDER.index(card.rank)

        # --- Undeufe: no trump, 6s highest ---
        if trump_mode == TrumpMode.UNDEUFE:
            return UNDEUFE_RANK_ORDER.index(card.rank)

        # --- Suit trump modes ---
        if trump_suit and card.suit == trump_suit:
            # Trump card — offset by 100 so trump always beats non-trump
            return 100 + TRUMP_RANK_ORDER.index(card.rank)
        else:
            # Normal (non-trump) card
            return NORMAL_RANK_ORDER.index(card.rank)

    # ------------------------------------------------------------------
    # Legal moves
    # ------------------------------------------------------------------

    def get_legal_moves(self, state: GameState, player_id: str) -> list[Card]:
        """
        Return cards this player may legally play.

        Rules:
          1. If the trick is empty (player leads), any card is legal.
          2. Must follow lead suit if possible.
          3. Buur (Jack of trump) is always playable, even when following
             a non-trump lead suit — it is never forced out.
          4. If unable to follow lead suit, any card is legal.
          5. Undeufe/Obenabe (no trump): must follow suit, no special cards.
        """
        player = state.get_player(player_id)
        if not player or not player.hand:
            return []

        hand = player.hand
        trick = state.current_trick

        # Leading the trick — all cards are legal
        if not trick.entries:
            return list(hand)

        lead_suit = trick.lead_suit
        trump_suit = self._get_trump_suit(state)

        # Cards in hand that match the lead suit
        same_suit = [c for c in hand if c.suit == lead_suit]

        # If we can follow suit
        if same_suit:
            # Special rule: if lead suit is NOT trump, the Buur is always
            # allowed as an alternative (it's never forced out by a non-trump lead)
            if trump_suit and lead_suit != trump_suit:
                buur = Card(suit=trump_suit, rank=Rank.JACK)
                if buur in hand and buur not in same_suit:
                    return same_suit + [buur]
            return same_suit

        # Cannot follow suit — any card is legal
        return list(hand)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _card_points(self, card: Card, state: GameState) -> int:
        """Return the point value of a single card given the current trump mode."""
        trump_suit = self._get_trump_suit(state)
        trump_mode = state.trump_mode

        if trump_mode == TrumpMode.UNDEUFE:
            return UNDEUFE_CARD_POINTS[card.rank]

        # Obenabe or no trump mode set: use base points
        if trump_mode == TrumpMode.OBENABE or trump_suit is None:
            return BASE_CARD_POINTS[card.rank]

        # Suit trump
        if card.suit == trump_suit:
            return TRUMP_CARD_POINTS[card.rank]

        return BASE_CARD_POINTS[card.rank]

    def score_trick(self, trick: Trick, state: GameState) -> int:
        """Return the total point value of all cards in a completed trick."""
        return sum(self._card_points(entry.card, state) for entry in trick.entries)

    def score_game(self, state: GameState) -> dict[TeamId, int]:
        """
        Calculate round scores for both teams.

        Steps:
          1. Sum trick points per team (tricks already have winner_id set).
          2. Award last-trick bonus (+5) to the team that won the last trick.
          3. If one team won ALL tricks, award match bonus (+100) and give
             the opposing team 0 for this round.

        Returns:
            {TeamId.TEAM_A: points_a, TeamId.TEAM_B: points_b}
        """
        scores: dict[TeamId, int] = {TeamId.TEAM_A: 0, TeamId.TEAM_B: 0}

        for trick in state.completed_tricks:
            if trick.winner_id is None:
                continue
            team = state.get_player_team(trick.winner_id)
            if team:
                scores[team] += trick.points

        # Last trick bonus
        if state.completed_tricks:
            last_trick = state.completed_tricks[-1]
            if last_trick.winner_id:
                team = state.get_player_team(last_trick.winner_id)
                if team:
                    scores[team] += LAST_TRICK_BONUS

        # Match bonus — one team won all 9 tricks
        tricks_won = {TeamId.TEAM_A: 0, TeamId.TEAM_B: 0}
        for trick in state.completed_tricks:
            if trick.winner_id:
                team = state.get_player_team(trick.winner_id)
                if team:
                    tricks_won[team] += 1

        for team, won in tricks_won.items():
            if won == len(state.completed_tricks) and won > 0:
                scores[team] += MATCH_BONUS
                # Opposing team gets nothing
                other = TeamId.TEAM_B if team == TeamId.TEAM_A else TeamId.TEAM_A
                scores[other] = 0
                break

        return scores

    # ------------------------------------------------------------------
    # Game over
    # ------------------------------------------------------------------

    def is_game_over(self, state: GameState) -> bool:
        """
        The game ends when at least one team reaches WINNING_SCORE (1000).
        If both teams cross 1000 in the same round, the higher score wins.
        """
        if not state.scores:
            return False
        return any(ts.total >= WINNING_SCORE for ts in state.scores.values())

    # ------------------------------------------------------------------
    # Helper: is this card the Buur (Jack of trump)?
    # ------------------------------------------------------------------

    def is_buur(self, card: Card, state: GameState) -> bool:
        """Return True if this card is the Jack of the trump suit."""
        trump_suit = self._get_trump_suit(state)
        return trump_suit is not None and card.suit == trump_suit and card.rank == Rank.JACK

    def is_nell(self, card: Card, state: GameState) -> bool:
        """Return True if this card is the Nine of the trump suit."""
        trump_suit = self._get_trump_suit(state)
        return trump_suit is not None and card.suit == trump_suit and card.rank == Rank.NINE
