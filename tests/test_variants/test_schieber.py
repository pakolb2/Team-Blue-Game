"""
tests/test_variants/test_schieber.py
-------------------------------------
Tests for Phase 3: BaseVariant interface + Schieber implementation.

Run with:  pytest tests/test_variants/test_schieber.py -v
"""

import pytest
from server.shared.types import (
    Card, Player, Trick, TrickEntry, GameState,
    Suit, Rank, TrumpMode, GamePhase, TeamId, TeamScore,
)
from server.shared.constants import (
    TRUMP_CARD_POINTS, BASE_CARD_POINTS, LAST_TRICK_BONUS,
    MATCH_BONUS, WINNING_SCORE, TOTAL_ROUND_POINTS,
)
from server.game.variants.schieber import Schieber


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(
    trump_mode: TrumpMode = TrumpMode.EICHEL,
    trick_entries: list[TrickEntry] | None = None,
    completed_tricks: list[Trick] | None = None,
    hands: dict[str, list[Card]] | None = None,
    scores: dict[TeamId, TeamScore] | None = None,
) -> GameState:
    """Build a minimal GameState for testing."""
    players = [
        Player(id="p1", name="Alice", team=TeamId.TEAM_A,
               hand=hands.get("p1", []) if hands else []),
        Player(id="p2", name="Bob",   team=TeamId.TEAM_B,
               hand=hands.get("p2", []) if hands else []),
        Player(id="p3", name="Carol", team=TeamId.TEAM_A,
               hand=hands.get("p3", []) if hands else []),
        Player(id="p4", name="Dave",  team=TeamId.TEAM_B,
               hand=hands.get("p4", []) if hands else []),
    ]

    lead_suit = trick_entries[0].card.suit if trick_entries else None
    trick = Trick(entries=trick_entries or [], lead_suit=lead_suit)

    return GameState(
        room_id="test_room",
        players=players,
        phase=GamePhase.PLAYING,
        trump_mode=trump_mode,
        current_trick=trick,
        completed_tricks=completed_tricks or [],
        scores=scores or {},
    )


def entry(player_id: str, suit: Suit, rank: Rank) -> TrickEntry:
    return TrickEntry(player_id=player_id, card=Card(suit=suit, rank=rank))


def card(suit: Suit, rank: Rank) -> Card:
    return Card(suit=suit, rank=rank)


def make_trick(
    entries: list[TrickEntry],
    winner_id: str | None = None,
    points: int = 0,
) -> Trick:
    lead_suit = entries[0].card.suit if entries else None
    return Trick(entries=entries, winner_id=winner_id, lead_suit=lead_suit, points=points)


# ---------------------------------------------------------------------------
# Card rank values — trump
# ---------------------------------------------------------------------------

class TestCardRankValueTrump:
    """Trump cards must rank above all non-trump cards, with Buur > Nell > rest."""

    def setup_method(self):
        self.v = Schieber()
        self.state = make_state(trump_mode=TrumpMode.EICHEL)  # Eichel is trump

    def test_buur_is_highest_trump(self):
        buur = card(Suit.EICHEL, Rank.JACK)
        nell = card(Suit.EICHEL, Rank.NINE)
        assert self.v.card_rank_value(buur, self.state) > self.v.card_rank_value(nell, self.state)

    def test_nell_is_second_highest_trump(self):
        nell = card(Suit.EICHEL, Rank.NINE)
        ace  = card(Suit.EICHEL, Rank.ACE)
        assert self.v.card_rank_value(nell, self.state) > self.v.card_rank_value(ace, self.state)

    def test_trump_beats_non_trump_ace(self):
        trump_six  = card(Suit.EICHEL, Rank.SIX)   # lowest trump
        normal_ace = card(Suit.ROSE,   Rank.ACE)    # highest non-trump
        assert self.v.card_rank_value(trump_six, self.state) > self.v.card_rank_value(normal_ace, self.state)

    def test_trump_rank_order_full(self):
        """Full trump rank: 6 < 7 < 8 < 10 < Q < K < A < Nell < Buur"""
        trump_ranks = [
            card(Suit.EICHEL, Rank.SIX),
            card(Suit.EICHEL, Rank.SEVEN),
            card(Suit.EICHEL, Rank.EIGHT),
            card(Suit.EICHEL, Rank.TEN),
            card(Suit.EICHEL, Rank.QUEEN),
            card(Suit.EICHEL, Rank.KING),
            card(Suit.EICHEL, Rank.ACE),
            card(Suit.EICHEL, Rank.NINE),   # Nell
            card(Suit.EICHEL, Rank.JACK),   # Buur
        ]
        values = [self.v.card_rank_value(c, self.state) for c in trump_ranks]
        assert values == sorted(values), "Trump rank order is wrong"

    def test_non_trump_jack_is_not_special(self):
        """Jack of a non-trump suit should NOT get the Buur bonus."""
        buur         = card(Suit.EICHEL, Rank.JACK)  # trump Jack
        non_trump_j  = card(Suit.ROSE,   Rank.JACK)  # normal Jack
        assert self.v.card_rank_value(buur, self.state) > self.v.card_rank_value(non_trump_j, self.state)

    def test_non_trump_nine_is_not_special(self):
        """Nine of a non-trump suit should NOT get the Nell bonus."""
        nell        = card(Suit.EICHEL, Rank.NINE)  # trump Nine
        non_trump_9 = card(Suit.ROSE,   Rank.NINE)  # normal Nine
        assert self.v.card_rank_value(nell, self.state) > self.v.card_rank_value(non_trump_9, self.state)


# ---------------------------------------------------------------------------
# Card rank values — Obenabe and Undeufe
# ---------------------------------------------------------------------------

class TestCardRankValueNoTrump:
    def setup_method(self):
        self.v = Schieber()

    def test_obenabe_ace_is_highest(self):
        state = make_state(trump_mode=TrumpMode.OBENABE)
        ace = card(Suit.ROSE, Rank.ACE)
        king = card(Suit.ROSE, Rank.KING)
        assert self.v.card_rank_value(ace, state) > self.v.card_rank_value(king, state)

    def test_obenabe_six_is_lowest(self):
        state = make_state(trump_mode=TrumpMode.OBENABE)
        six   = card(Suit.ROSE, Rank.SIX)
        seven = card(Suit.ROSE, Rank.SEVEN)
        assert self.v.card_rank_value(six, state) < self.v.card_rank_value(seven, state)

    def test_undeufe_six_is_highest(self):
        state = make_state(trump_mode=TrumpMode.UNDEUFE)
        six = card(Suit.ROSE, Rank.SIX)
        ace = card(Suit.ROSE, Rank.ACE)
        assert self.v.card_rank_value(six, state) > self.v.card_rank_value(ace, state)

    def test_undeufe_ace_is_lowest(self):
        state = make_state(trump_mode=TrumpMode.UNDEUFE)
        ace  = card(Suit.ROSE, Rank.ACE)
        king = card(Suit.ROSE, Rank.KING)
        assert self.v.card_rank_value(ace, state) < self.v.card_rank_value(king, state)

    def test_undeufe_full_rank_order(self):
        """Undeufe: 6 > 7 > 8 > 9 > 10 > J > Q > K > A (reversed)"""
        state = make_state(trump_mode=TrumpMode.UNDEUFE)
        ranks_low_to_high = [
            Rank.ACE, Rank.KING, Rank.QUEEN, Rank.JACK,
            Rank.TEN, Rank.NINE, Rank.EIGHT, Rank.SEVEN, Rank.SIX,
        ]
        cards = [card(Suit.ROSE, r) for r in ranks_low_to_high]
        values = [self.v.card_rank_value(c, state) for c in cards]
        assert values == sorted(values)


# ---------------------------------------------------------------------------
# Trick winner
# ---------------------------------------------------------------------------

class TestTrickWinner:
    def setup_method(self):
        self.v = Schieber()

    def test_highest_lead_suit_wins_no_trump_played(self):
        state = make_state(trump_mode=TrumpMode.EICHEL, trick_entries=[
            entry("p1", Suit.ROSE, Rank.KING),
            entry("p2", Suit.ROSE, Rank.ACE),
            entry("p3", Suit.ROSE, Rank.SIX),
            entry("p4", Suit.ROSE, Rank.QUEEN),
        ])
        assert self.v.trick_winner(state.current_trick, state) == "p2"

    def test_trump_beats_higher_lead_suit_card(self):
        state = make_state(trump_mode=TrumpMode.EICHEL, trick_entries=[
            entry("p1", Suit.ROSE,   Rank.ACE),    # lead suit ace
            entry("p2", Suit.EICHEL, Rank.SIX),    # lowest trump
            entry("p3", Suit.ROSE,   Rank.KING),
            entry("p4", Suit.ROSE,   Rank.QUEEN),
        ])
        assert self.v.trick_winner(state.current_trick, state) == "p2"

    def test_buur_beats_all_other_trump(self):
        state = make_state(trump_mode=TrumpMode.EICHEL, trick_entries=[
            entry("p1", Suit.EICHEL, Rank.ACE),    # trump ace
            entry("p2", Suit.EICHEL, Rank.NINE),   # Nell
            entry("p3", Suit.EICHEL, Rank.JACK),   # Buur
            entry("p4", Suit.EICHEL, Rank.KING),   # trump king
        ])
        assert self.v.trick_winner(state.current_trick, state) == "p3"

    def test_nell_beats_trump_ace(self):
        state = make_state(trump_mode=TrumpMode.EICHEL, trick_entries=[
            entry("p1", Suit.EICHEL, Rank.ACE),    # trump ace
            entry("p2", Suit.EICHEL, Rank.NINE),   # Nell
            entry("p3", Suit.EICHEL, Rank.KING),
            entry("p4", Suit.EICHEL, Rank.QUEEN),
        ])
        assert self.v.trick_winner(state.current_trick, state) == "p2"

    def test_first_card_wins_if_all_same_suit_no_trump(self):
        """If all cards are the same suit and no trump played, lead suit rules."""
        state = make_state(trump_mode=TrumpMode.EICHEL, trick_entries=[
            entry("p1", Suit.ROSE, Rank.ACE),
            entry("p2", Suit.ROSE, Rank.KING),
            entry("p3", Suit.ROSE, Rank.QUEEN),
            entry("p4", Suit.ROSE, Rank.JACK),
        ])
        assert self.v.trick_winner(state.current_trick, state) == "p1"

    def test_second_trump_beats_first_trump_if_higher(self):
        state = make_state(trump_mode=TrumpMode.ROSE, trick_entries=[
            entry("p1", Suit.EICHEL, Rank.ACE),
            entry("p2", Suit.ROSE,   Rank.SIX),    # first trump (low)
            entry("p3", Suit.ROSE,   Rank.ACE),    # higher trump
            entry("p4", Suit.EICHEL, Rank.KING),
        ])
        assert self.v.trick_winner(state.current_trick, state) == "p3"

    def test_off_suit_non_trump_cannot_win(self):
        """A card of a third suit (neither lead nor trump) can never win."""
        state = make_state(trump_mode=TrumpMode.EICHEL, trick_entries=[
            entry("p1", Suit.ROSE,    Rank.SIX),    # lead suit
            entry("p2", Suit.SCHELLE, Rank.ACE),    # off suit — cannot win
            entry("p3", Suit.ROSE,    Rank.SEVEN),
            entry("p4", Suit.ROSE,    Rank.EIGHT),
        ])
        # p1 has the highest rose (6 leads, 7 and 8 are higher... wait — 8 > 7 > 6)
        assert self.v.trick_winner(state.current_trick, state) == "p4"

    def test_obenabe_ace_wins_trick(self):
        state = make_state(trump_mode=TrumpMode.OBENABE, trick_entries=[
            entry("p1", Suit.ROSE, Rank.KING),
            entry("p2", Suit.ROSE, Rank.ACE),
            entry("p3", Suit.ROSE, Rank.SIX),
            entry("p4", Suit.ROSE, Rank.QUEEN),
        ])
        assert self.v.trick_winner(state.current_trick, state) == "p2"

    def test_undeufe_six_wins_trick(self):
        state = make_state(trump_mode=TrumpMode.UNDEUFE, trick_entries=[
            entry("p1", Suit.ROSE, Rank.ACE),
            entry("p2", Suit.ROSE, Rank.SIX),
            entry("p3", Suit.ROSE, Rank.KING),
            entry("p4", Suit.ROSE, Rank.QUEEN),
        ])
        assert self.v.trick_winner(state.current_trick, state) == "p2"


# ---------------------------------------------------------------------------
# Legal moves
# ---------------------------------------------------------------------------

class TestLegalMoves:
    def setup_method(self):
        self.v = Schieber()

    def _state_with_hand(
        self,
        hand: list[Card],
        trick_entries: list[TrickEntry] | None = None,
        trump_mode: TrumpMode = TrumpMode.EICHEL,
    ) -> GameState:
        return make_state(
            trump_mode=trump_mode,
            trick_entries=trick_entries,
            hands={"p1": hand},
        )

    def test_lead_any_card(self):
        """When leading (empty trick), all cards are legal."""
        hand = [card(Suit.ROSE, Rank.ACE), card(Suit.SCHELLE, Rank.TEN)]
        state = self._state_with_hand(hand, trick_entries=None)
        legal = self.v.get_legal_moves(state, "p1")
        assert set(legal) == set(hand)

    def test_must_follow_lead_suit(self):
        hand = [
            card(Suit.ROSE,    Rank.ACE),
            card(Suit.ROSE,    Rank.KING),
            card(Suit.SCHELLE, Rank.TEN),
        ]
        trick = [entry("p2", Suit.ROSE, Rank.SIX)]
        state = self._state_with_hand(hand, trick_entries=trick)
        legal = self.v.get_legal_moves(state, "p1")
        assert set(legal) == {card(Suit.ROSE, Rank.ACE), card(Suit.ROSE, Rank.KING)}

    def test_can_play_any_card_if_no_lead_suit(self):
        hand = [
            card(Suit.EICHEL, Rank.ACE),
            card(Suit.SCHELLE, Rank.TEN),
        ]
        trick = [entry("p2", Suit.ROSE, Rank.SIX)]  # lead = Rose, hand has none
        state = self._state_with_hand(hand, trick_entries=trick)
        legal = self.v.get_legal_moves(state, "p1")
        assert set(legal) == set(hand)

    def test_buur_always_legal_on_non_trump_lead(self):
        """Even when following a non-trump lead suit, Buur may be played."""
        buur = card(Suit.EICHEL, Rank.JACK)  # Eichel is trump
        hand = [
            card(Suit.ROSE, Rank.ACE),   # follows lead
            card(Suit.ROSE, Rank.KING),  # follows lead
            buur,                         # Buur — always allowed
        ]
        trick = [entry("p2", Suit.ROSE, Rank.SIX)]  # Rose lead, Eichel is trump
        state = self._state_with_hand(hand, trick_entries=trick)
        legal = self.v.get_legal_moves(state, "p1")
        assert buur in legal
        assert card(Suit.ROSE, Rank.ACE) in legal
        assert card(Suit.ROSE, Rank.KING) in legal

    def test_buur_not_double_counted_when_following_trump_lead(self):
        """If lead suit IS trump, Buur is included normally (it's trump)."""
        buur = card(Suit.EICHEL, Rank.JACK)
        hand = [buur, card(Suit.EICHEL, Rank.ACE)]
        trick = [entry("p2", Suit.EICHEL, Rank.SIX)]  # trump lead
        state = self._state_with_hand(hand, trick_entries=trick)
        legal = self.v.get_legal_moves(state, "p1")
        assert legal.count(buur) == 1  # not duplicated

    def test_empty_hand_returns_empty(self):
        state = self._state_with_hand([], trick_entries=None)
        assert self.v.get_legal_moves(state, "p1") == []

    def test_unknown_player_returns_empty(self):
        state = make_state()
        assert self.v.get_legal_moves(state, "nonexistent") == []

    def test_obenabe_must_follow_suit_no_buur_exception(self):
        """In Obenabe there is no trump, so no Buur exception applies."""
        hand = [
            card(Suit.ROSE,    Rank.ACE),
            card(Suit.EICHEL,  Rank.JACK),  # would be Buur in suit trump — not here
        ]
        trick = [entry("p2", Suit.ROSE, Rank.SIX)]
        state = self._state_with_hand(hand, trick_entries=trick, trump_mode=TrumpMode.OBENABE)
        legal = self.v.get_legal_moves(state, "p1")
        # Must follow Rose — Eichel Jack is not a special card in Obenabe
        assert legal == [card(Suit.ROSE, Rank.ACE)]


# ---------------------------------------------------------------------------
# Trick scoring
# ---------------------------------------------------------------------------

class TestScoreTrick:
    def setup_method(self):
        self.v = Schieber()

    def test_empty_trick_scores_zero(self):
        state = make_state(trump_mode=TrumpMode.EICHEL)
        trick = Trick()
        assert self.v.score_trick(trick, state) == 0

    def test_trump_jack_scores_20(self):
        state = make_state(trump_mode=TrumpMode.EICHEL)
        trick = make_trick([entry("p1", Suit.EICHEL, Rank.JACK)])
        assert self.v.score_trick(trick, state) == TRUMP_CARD_POINTS[Rank.JACK]  # 20

    def test_trump_nine_scores_14(self):
        state = make_state(trump_mode=TrumpMode.EICHEL)
        trick = make_trick([entry("p1", Suit.EICHEL, Rank.NINE)])
        assert self.v.score_trick(trick, state) == TRUMP_CARD_POINTS[Rank.NINE]  # 14

    def test_normal_ace_scores_11(self):
        state = make_state(trump_mode=TrumpMode.EICHEL)
        trick = make_trick([entry("p1", Suit.ROSE, Rank.ACE)])
        assert self.v.score_trick(trick, state) == BASE_CARD_POINTS[Rank.ACE]  # 11

    def test_normal_ten_scores_10(self):
        state = make_state(trump_mode=TrumpMode.EICHEL)
        trick = make_trick([entry("p1", Suit.ROSE, Rank.TEN)])
        assert self.v.score_trick(trick, state) == BASE_CARD_POINTS[Rank.TEN]  # 10

    def test_full_trick_score(self):
        """A trick with Buur(20) + Nell(14) + normal Ace(11) + normal Ten(10) = 55."""
        state = make_state(trump_mode=TrumpMode.EICHEL)
        trick = make_trick([
            entry("p1", Suit.EICHEL, Rank.JACK),   # Buur = 20
            entry("p2", Suit.EICHEL, Rank.NINE),   # Nell = 14
            entry("p3", Suit.ROSE,   Rank.ACE),    # normal Ace = 11
            entry("p4", Suit.ROSE,   Rank.TEN),    # normal Ten = 10
        ])
        assert self.v.score_trick(trick, state) == 55

    def test_all_zero_cards_trick(self):
        state = make_state(trump_mode=TrumpMode.EICHEL)
        trick = make_trick([
            entry("p1", Suit.ROSE,    Rank.SIX),
            entry("p2", Suit.ROSE,    Rank.SEVEN),
            entry("p3", Suit.SCHELLE, Rank.EIGHT),
            entry("p4", Suit.SCHILTE, Rank.SIX),
        ])
        assert self.v.score_trick(trick, state) == 0

    def test_undeufe_six_scores_11(self):
        state = make_state(trump_mode=TrumpMode.UNDEUFE)
        trick = make_trick([entry("p1", Suit.ROSE, Rank.SIX)])
        assert self.v.score_trick(trick, state) == 11

    def test_undeufe_eight_scores_8(self):
        state = make_state(trump_mode=TrumpMode.UNDEUFE)
        trick = make_trick([entry("p1", Suit.ROSE, Rank.EIGHT)])
        assert self.v.score_trick(trick, state) == 8


# ---------------------------------------------------------------------------
# Game scoring
# ---------------------------------------------------------------------------

class TestScoreGame:
    def setup_method(self):
        self.v = Schieber()

    def _make_scored_state(
        self,
        team_a_tricks: int = 5,
        team_b_tricks: int = 4,
        points_per_trick: int = 10,
        last_winner: str = "p1",  # p1 is team_a
    ) -> GameState:
        """Build a state where TEAM_A won `team_a_tricks` and TEAM_B won the rest."""
        tricks = []
        for i in range(team_a_tricks):
            t = make_trick(
                [entry("p1", Suit.ROSE, Rank.ACE),
                 entry("p2", Suit.ROSE, Rank.SIX),
                 entry("p3", Suit.ROSE, Rank.SEVEN),
                 entry("p4", Suit.ROSE, Rank.EIGHT)],
                winner_id="p1",
                points=points_per_trick,
            )
            tricks.append(t)
        for i in range(team_b_tricks):
            t = make_trick(
                [entry("p1", Suit.ROSE, Rank.SIX),
                 entry("p2", Suit.ROSE, Rank.ACE),
                 entry("p3", Suit.ROSE, Rank.SEVEN),
                 entry("p4", Suit.ROSE, Rank.EIGHT)],
                winner_id="p2",
                points=points_per_trick,
            )
            tricks.append(t)
        # Override last trick winner
        tricks[-1] = tricks[-1].model_copy(update={"winner_id": last_winner})

        return make_state(
            trump_mode=TrumpMode.EICHEL,
            completed_tricks=tricks,
        )

    def test_last_trick_bonus_awarded(self):
        # Helper makes 5 TEAM_A + 4 TEAM_B tricks, then overrides the last trick
        # (originally TEAM_B) to p1 (TEAM_A) → TEAM_A wins 6 tricks = 60 pts + 5 bonus
        state = self._make_scored_state(last_winner="p1")  # p1 = TEAM_A
        scores = self.v.score_game(state)
        assert scores[TeamId.TEAM_A] == 6 * 10 + LAST_TRICK_BONUS

    def test_last_trick_bonus_goes_to_correct_team(self):
        state = self._make_scored_state(last_winner="p2")  # p2 = TEAM_B
        scores = self.v.score_game(state)
        assert scores[TeamId.TEAM_B] == 4 * 10 + LAST_TRICK_BONUS

    def test_match_bonus_when_one_team_wins_all(self):
        """If TEAM_A wins all 9 tricks, they get +100 match bonus and TEAM_B gets 0."""
        tricks = []
        for i in range(9):
            t = make_trick(
                [entry("p1", Suit.ROSE, Rank.ACE),
                 entry("p2", Suit.ROSE, Rank.SIX),
                 entry("p3", Suit.ROSE, Rank.SEVEN),
                 entry("p4", Suit.ROSE, Rank.EIGHT)],
                winner_id="p1",
                points=10,
            )
            tricks.append(t)
        state = make_state(trump_mode=TrumpMode.EICHEL, completed_tricks=tricks)
        scores = self.v.score_game(state)
        assert scores[TeamId.TEAM_A] == 9 * 10 + LAST_TRICK_BONUS + MATCH_BONUS
        assert scores[TeamId.TEAM_B] == 0

    def test_no_tricks_no_scores(self):
        state = make_state(trump_mode=TrumpMode.EICHEL, completed_tricks=[])
        scores = self.v.score_game(state)
        assert scores[TeamId.TEAM_A] == 0
        assert scores[TeamId.TEAM_B] == 0


# ---------------------------------------------------------------------------
# Game over
# ---------------------------------------------------------------------------

class TestIsGameOver:
    def setup_method(self):
        self.v = Schieber()

    def test_not_over_with_no_scores(self):
        state = make_state()
        assert not self.v.is_game_over(state)

    def test_not_over_below_winning_score(self):
        state = make_state(scores={
            TeamId.TEAM_A: TeamScore(team=TeamId.TEAM_A, total=999),
            TeamId.TEAM_B: TeamScore(team=TeamId.TEAM_B, total=500),
        })
        assert not self.v.is_game_over(state)

    def test_over_when_team_reaches_1000(self):
        state = make_state(scores={
            TeamId.TEAM_A: TeamScore(team=TeamId.TEAM_A, total=1000),
            TeamId.TEAM_B: TeamScore(team=TeamId.TEAM_B, total=800),
        })
        assert self.v.is_game_over(state)

    def test_over_when_team_exceeds_1000(self):
        state = make_state(scores={
            TeamId.TEAM_A: TeamScore(team=TeamId.TEAM_A, total=1157),
            TeamId.TEAM_B: TeamScore(team=TeamId.TEAM_B, total=600),
        })
        assert self.v.is_game_over(state)


# ---------------------------------------------------------------------------
# Buur / Nell helpers
# ---------------------------------------------------------------------------

class TestBuurNell:
    def setup_method(self):
        self.v = Schieber()
        self.state = make_state(trump_mode=TrumpMode.EICHEL)

    def test_is_buur_correct(self):
        assert self.v.is_buur(card(Suit.EICHEL, Rank.JACK), self.state)

    def test_is_buur_wrong_suit(self):
        assert not self.v.is_buur(card(Suit.ROSE, Rank.JACK), self.state)

    def test_is_buur_wrong_rank(self):
        assert not self.v.is_buur(card(Suit.EICHEL, Rank.ACE), self.state)

    def test_is_nell_correct(self):
        assert self.v.is_nell(card(Suit.EICHEL, Rank.NINE), self.state)

    def test_is_nell_wrong_suit(self):
        assert not self.v.is_nell(card(Suit.ROSE, Rank.NINE), self.state)

    def test_is_nell_wrong_rank(self):
        assert not self.v.is_nell(card(Suit.EICHEL, Rank.ACE), self.state)

    def test_no_buur_in_obenabe(self):
        state = make_state(trump_mode=TrumpMode.OBENABE)
        assert not self.v.is_buur(card(Suit.EICHEL, Rank.JACK), state)

    def test_no_nell_in_undeufe(self):
        state = make_state(trump_mode=TrumpMode.UNDEUFE)
        assert not self.v.is_nell(card(Suit.EICHEL, Rank.NINE), state)
