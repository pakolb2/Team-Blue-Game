"""
server/bots/rule_based_bot.py
------------------------------
A rule-based Jass bot that applies standard Jass heuristics to pick
a reasonable card each turn.

Strategy summary
----------------
Trump selection:
  1. Count trump cards and high-value cards in hand.
  2. Choose the suit with the most trump cards (ideally with Buur or Nell).
  3. Fall back to Obenabe if hand has several Aces; Undeufe if many low cards.

Card play — leading a trick:
  1. Lead with Buur or Nell if holding them (strong trump control).
  2. Lead the highest card of a suit where partner is likely to be strong.
  3. Lead a low card in a suit to probe the table.
  4. Avoid leading into a suit where opponents are known to be strong.

Card play — following:
  1. If partner is currently winning → play lowest legal card (don't waste points).
  2. If opponents are winning:
       a. Trump in if it wins the trick and you hold Buur/Nell.
       b. Play highest card of lead suit to try to win.
       c. If can't win, throw the lowest-value card (minimise gift to opponents).
  3. Never sacrifice Buur or Nell unless they will win.

This is intentionally a moderate-strength bot — good enough to give a
human a real game, not so good as to be frustrating for new players.
"""

from __future__ import annotations

from server.bots.base import BaseBot
from server.shared.types import (
    Card, GameState, TrumpMode, Trick, Suit, Rank, TeamId,
)
from server.shared.constants import (
    BASE_CARD_POINTS, TRUMP_CARD_POINTS, UNDEUFE_CARD_POINTS,
    TRUMP_MODE_TO_SUIT, NO_TRUMP_MODES, SUIT_TRUMP_MODES,
)


class RuleBasedBot(BaseBot):
    """Applies Jass heuristics to choose cards and trump."""

    # ------------------------------------------------------------------
    # Trump selection
    # ------------------------------------------------------------------

    def choose_trump(self, state: GameState) -> TrumpMode:
        """
        Choose trump based on hand strength.

        Scoring per TrumpMode candidate:
          +4  for holding Buur (Jack of that suit)
          +3  for holding Nell (Nine of that suit)
          +2  for each other trump card
          +1  for each Ace in hand (bonus for Obenabe)
          -1  for each Six in hand (penalty for not choosing Undeufe)

        Obenabe is scored by counting Aces (+2 each).
        Undeufe is scored by counting Sixes (+2 each).
        """
        player = state.get_player(self.player_id)
        if not player:
            return TrumpMode.OBENABE

        hand = player.hand
        best_mode = TrumpMode.OBENABE
        best_score = -999

        # Score each suit trump
        for mode in SUIT_TRUMP_MODES:
            trump_suit = TRUMP_MODE_TO_SUIT[mode]
            score = 0
            for card in hand:
                if card.suit == trump_suit:
                    if card.rank == Rank.JACK:
                        score += 4   # Buur
                    elif card.rank == Rank.NINE:
                        score += 3   # Nell
                    else:
                        score += 2   # other trump
            if score > best_score:
                best_score = score
                best_mode = mode

        # Score Obenabe — reward Aces
        obenabe_score = sum(2 for c in hand if c.rank == Rank.ACE)
        if obenabe_score > best_score:
            best_score = obenabe_score
            best_mode = TrumpMode.OBENABE

        # Score Undeufe — reward Sixes
        undeufe_score = sum(2 for c in hand if c.rank == Rank.SIX)
        if undeufe_score > best_score:
            best_mode = TrumpMode.UNDEUFE

        return best_mode

    # ------------------------------------------------------------------
    # Card play
    # ------------------------------------------------------------------

    def choose_card(self, state: GameState, legal_moves: list[Card]) -> Card:
        """
        Pick a card using layered heuristics.
        Falls back to the lowest-value legal card if no rule fires.
        """
        if len(legal_moves) == 1:
            return legal_moves[0]

        trick = state.current_trick
        trump_suit = self._trump_suit(state)

        # --- Leading the trick ---
        if not trick.entries:
            return self._lead(state, legal_moves, trump_suit)

        # --- Following ---
        return self._follow(state, legal_moves, trump_suit)

    # ------------------------------------------------------------------
    # Leading strategy
    # ------------------------------------------------------------------

    def _lead(
        self,
        state: GameState,
        legal_moves: list[Card],
        trump_suit: Suit | None,
    ) -> Card:
        """
        Heuristics for leading a new trick.

        Priority:
          1. Lead Buur — forces out opponents' trump
          2. Lead Nell — if Buur is already gone or you don't hold it
          3. Lead Ace of a non-trump suit — likely to win
          4. Lead highest non-trump card (aggressive)
          5. Fall back to lowest-value card
        """
        # 1. Lead Buur if holding it
        if trump_suit:
            buur = Card(suit=trump_suit, rank=Rank.JACK)
            if buur in legal_moves:
                return buur

            # 2. Lead Nell
            nell = Card(suit=trump_suit, rank=Rank.NINE)
            if nell in legal_moves:
                return nell

        # 3. Lead an Ace of a non-trump suit
        aces = [c for c in legal_moves if c.rank == Rank.ACE
                and c.suit != trump_suit]
        if aces:
            return aces[0]

        # 4. Lead highest non-trump card
        non_trump = [c for c in legal_moves if c.suit != trump_suit]
        if non_trump:
            return self._highest_value(non_trump, state)

        # 5. Fallback — lowest value
        return self._lowest_value(legal_moves, state)

    # ------------------------------------------------------------------
    # Following strategy
    # ------------------------------------------------------------------

    def _follow(
        self,
        state: GameState,
        legal_moves: list[Card],
        trump_suit: Suit | None,
    ) -> Card:
        """
        Heuristics for playing when the trick is already started.

        Determines:
          - Who is currently winning the trick (partner or opponent)?
          - Can we win the trick?
          - Should we try to win or discard cheaply?
        """
        trick = state.current_trick
        current_winner_id = self._current_winner(trick, state)
        partner_id = state.get_player(self.player_id)
        my_team = partner_id.team if partner_id else None

        # Is the current winner on my team?
        winner_team = state.get_player_team(current_winner_id) if current_winner_id else None
        partner_winning = (winner_team == my_team)

        # --- Partner is winning the trick ---
        if partner_winning:
            return self._discard_cheap(legal_moves, state, trump_suit)

        # --- Opponent is winning — try to win ---
        winning_cards = self._cards_that_win(legal_moves, trick, state, trump_suit)

        if winning_cards:
            # Win with the lowest-value winning card to preserve strong cards
            return self._lowest_value(winning_cards, state)

        # Can't win — discard cheapest card
        return self._discard_cheap(legal_moves, state, trump_suit)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _trump_suit(self, state: GameState) -> Suit | None:
        """Return the trump Suit, or None for Obenabe/Undeufe."""
        if state.trump_mode is None:
            return None
        if state.trump_mode in NO_TRUMP_MODES:
            return None
        return TRUMP_MODE_TO_SUIT.get(state.trump_mode)

    def _current_winner(self, trick: Trick, state: GameState) -> str | None:
        """Return the player_id currently winning the trick, or None if empty."""
        if not trick.entries:
            return None
        # Import here to avoid circular imports
        from server.game.variants.schieber import Schieber
        # We only use Schieber for trick resolution — in future phases
        # the engine's variant instance should be passed in, but for now
        # this is the only variant available.
        variant = Schieber()
        try:
            return variant.trick_winner(trick, state)
        except Exception:
            return trick.entries[0].player_id

    def _cards_that_win(
        self,
        legal_moves: list[Card],
        trick: Trick,
        state: GameState,
        trump_suit: Suit | None,
    ) -> list[Card]:
        """
        Return cards from legal_moves that would currently win the trick.
        A card wins if it beats the card currently winning the trick.
        """
        if not trick.entries:
            return legal_moves

        # Find the current best entry
        from server.game.variants.schieber import Schieber
        variant = Schieber()
        current_winner_id = self._current_winner(trick, state)
        if not current_winner_id:
            return legal_moves

        # Find the winning card's value
        winning_entry = next(
            (e for e in trick.entries if e.player_id == current_winner_id),
            trick.entries[0],
        )
        winning_card = winning_entry.card
        winning_value = variant.card_rank_value(winning_card, state)
        winning_is_trump = (trump_suit is not None and winning_card.suit == trump_suit)

        result = []
        for card in legal_moves:
            card_value = variant.card_rank_value(card, state)
            card_is_trump = (trump_suit is not None and card.suit == trump_suit)

            # Can beat if same suit as winner, or is trump when winner is not
            same_suit_as_winner = (card.suit == winning_card.suit)
            trumping_non_trump = (card_is_trump and not winning_is_trump)

            if (same_suit_as_winner or trumping_non_trump) and card_value > winning_value:
                result.append(card)

        return result

    def _discard_cheap(
        self,
        legal_moves: list[Card],
        state: GameState,
        trump_suit: Suit | None,
    ) -> Card:
        """
        Discard the lowest-value card.
        Prefers non-trump discards — never sacrifice Buur or Nell cheaply.
        """
        # Avoid discarding Buur or Nell
        safe = [
            c for c in legal_moves
            if not (trump_suit and c.suit == trump_suit
                    and c.rank in (Rank.JACK, Rank.NINE))
        ]
        candidates = safe if safe else legal_moves
        return self._lowest_value(candidates, state)

    def _card_point_value(self, card: Card, state: GameState) -> int:
        """Return the scoring point value of a card (not its rank strength)."""
        trump_suit = self._trump_suit(state)
        if state.trump_mode == TrumpMode.UNDEUFE:
            return UNDEUFE_CARD_POINTS[card.rank]
        if trump_suit and card.suit == trump_suit:
            return TRUMP_CARD_POINTS[card.rank]
        return BASE_CARD_POINTS[card.rank]

    def _lowest_value(self, cards: list[Card], state: GameState) -> Card:
        """Return the card with the lowest point value."""
        return min(cards, key=lambda c: self._card_point_value(c, state))

    def _highest_value(self, cards: list[Card], state: GameState) -> Card:
        """Return the card with the highest point value."""
        return max(cards, key=lambda c: self._card_point_value(c, state))
