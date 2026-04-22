"""
tests/test_scoring.py
----------------------
Tests for Phase 4: server/game/scoring.py

Run with:  pytest tests/test_scoring.py -v
"""

import pytest

from server.shared.types import (
    Card, Player, Trick, TrickEntry, GameState,
    Suit, Rank, TrumpMode, GamePhase, TeamId, TeamScore,
)
from server.shared.constants import LAST_TRICK_BONUS, MATCH_BONUS, WINNING_SCORE
from server.game.variants.schieber import Schieber
from server.game.scoring import (
    score_completed_trick,
    apply_round_scores,
    get_round_winner,
    get_game_winner,
    round_score_summary,
    tricks_per_team,
    points_per_team,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def c(suit: Suit, rank: Rank) -> Card:
    return Card(suit=suit, rank=rank)


def entry(pid: str, suit: Suit, rank: Rank) -> TrickEntry:
    return TrickEntry(player_id=pid, card=c(suit, rank))


def make_trick(entries: list[TrickEntry], winner_id: str | None = None, points: int = 0) -> Trick:
    lead_suit = entries[0].card.suit if entries else None
    return Trick(entries=entries, winner_id=winner_id, lead_suit=lead_suit, points=points)


def make_state(
    completed_tricks: list[Trick] | None = None,
    trump_mode: TrumpMode = TrumpMode.EICHEL,
    scores: dict[TeamId, TeamScore] | None = None,
    phase: GamePhase = GamePhase.SCORING,
) -> GameState:
    players = [
        Player(id="p1", name="Alice", team=TeamId.TEAM_A),
        Player(id="p2", name="Bob",   team=TeamId.TEAM_B),
        Player(id="p3", name="Carol", team=TeamId.TEAM_A),
        Player(id="p4", name="Dave",  team=TeamId.TEAM_B),
    ]
    return GameState(
        room_id="r1",
        players=players,
        phase=phase,
        trump_mode=trump_mode,
        completed_tricks=completed_tricks or [],
        scores=scores or {},
    )


def make_9_tricks(team_a_wins: int = 5) -> list[Trick]:
    """Build 9 completed tricks: team_a_wins for TEAM_A, rest for TEAM_B."""
    assert 0 <= team_a_wins <= 9
    tricks = []
    for i in range(9):
        winner = "p1" if i < team_a_wins else "p2"
        t = make_trick(
            entries=[
                entry("p1", Suit.ROSE, Rank.ACE),
                entry("p2", Suit.ROSE, Rank.SIX),
                entry("p3", Suit.ROSE, Rank.SEVEN),
                entry("p4", Suit.ROSE, Rank.EIGHT),
            ],
            winner_id=winner,
            points=10,
        )
        tricks.append(t)
    return tricks


# ---------------------------------------------------------------------------
# score_completed_trick
# ---------------------------------------------------------------------------

class TestScoreCompletedTrick:
    def setup_method(self):
        self.v = Schieber()

    def test_scores_trick_with_buur(self):
        state = make_state()
        trick = make_trick([
            entry("p1", Suit.EICHEL, Rank.JACK),   # Buur = 20
            entry("p2", Suit.EICHEL, Rank.NINE),   # Nell = 14
            entry("p3", Suit.ROSE,   Rank.ACE),    # 11
            entry("p4", Suit.ROSE,   Rank.TEN),    # 10
        ])
        scored = score_completed_trick(trick, state, self.v)
        assert scored.points == 55

    def test_returns_new_trick_object(self):
        state = make_state()
        trick = make_trick([entry("p1", Suit.ROSE, Rank.ACE)] * 4)
        scored = score_completed_trick(trick, state, self.v)
        assert scored is not trick

    def test_does_not_mutate_original_trick(self):
        state = make_state()
        trick = make_trick([entry("p1", Suit.ROSE, Rank.ACE)] * 4)
        original_points = trick.points
        score_completed_trick(trick, state, self.v)
        assert trick.points == original_points

    def test_raises_on_incomplete_trick(self):
        state = make_state()
        trick = make_trick([entry("p1", Suit.ROSE, Rank.ACE)])  # only 1 card
        with pytest.raises(ValueError, match="incomplete"):
            score_completed_trick(trick, state, self.v)

    def test_all_zero_cards_scores_zero(self):
        state = make_state()
        trick = make_trick([
            entry("p1", Suit.ROSE,    Rank.SIX),
            entry("p2", Suit.SCHILTE, Rank.SEVEN),
            entry("p3", Suit.SCHELLE, Rank.EIGHT),
            entry("p4", Suit.ROSE,    Rank.NINE),
        ])
        scored = score_completed_trick(trick, state, self.v)
        assert scored.points == 0


# ---------------------------------------------------------------------------
# apply_round_scores
# ---------------------------------------------------------------------------

class TestApplyRoundScores:
    def setup_method(self):
        self.v = Schieber()

    def test_initialises_scores_on_first_round(self):
        tricks = make_9_tricks(team_a_wins=5)
        state = make_state(completed_tricks=tricks)
        new_state = apply_round_scores(state, self.v)
        assert TeamId.TEAM_A in new_state.scores
        assert TeamId.TEAM_B in new_state.scores

    def test_scores_accumulate_across_rounds(self):
        tricks = make_9_tricks(team_a_wins=9)  # team A wins all
        state = make_state(completed_tricks=tricks)

        # First round
        state = apply_round_scores(state, self.v)
        round1_a = state.scores[TeamId.TEAM_A].total

        # Reset tricks, second round — team B wins all
        tricks2 = make_9_tricks(team_a_wins=0)
        state = state.model_copy(update={
            "completed_tricks": tricks2,
            "game_over": False,
            "winner": None,
            "phase": GamePhase.SCORING,
        })
        state = apply_round_scores(state, self.v)

        # TEAM_A total should be at least round1_a (may have won more)
        assert state.scores[TeamId.TEAM_A].total >= round1_a
        assert len(state.scores[TeamId.TEAM_A].round_scores) == 2

    def test_does_not_mutate_original_state(self):
        tricks = make_9_tricks()
        state = make_state(completed_tricks=tricks)
        apply_round_scores(state, self.v)
        assert not state.scores  # original unchanged

    def test_sets_game_over_when_team_reaches_1000(self):
        tricks = make_9_tricks(team_a_wins=9)
        existing = {
            TeamId.TEAM_A: TeamScore(team=TeamId.TEAM_A, total=900),
            TeamId.TEAM_B: TeamScore(team=TeamId.TEAM_B, total=800),
        }
        state = make_state(completed_tricks=tricks, scores=existing)
        new_state = apply_round_scores(state, self.v)
        # TEAM_A gets 9×10 + 5 bonus + 100 match = 215 pts this round → total ≥ 1000
        assert new_state.game_over
        assert new_state.winner == TeamId.TEAM_A
        assert new_state.phase == GamePhase.FINISHED

    def test_no_game_over_below_winning_score(self):
        tricks = make_9_tricks(team_a_wins=5)
        state = make_state(completed_tricks=tricks)
        new_state = apply_round_scores(state, self.v)
        assert not new_state.game_over
        assert new_state.winner is None


# ---------------------------------------------------------------------------
# get_round_winner
# ---------------------------------------------------------------------------

class TestGetRoundWinner:
    def test_higher_score_wins(self):
        scores = {TeamId.TEAM_A: 90, TeamId.TEAM_B: 67}
        assert get_round_winner(scores) == TeamId.TEAM_A

    def test_team_b_wins(self):
        scores = {TeamId.TEAM_A: 50, TeamId.TEAM_B: 107}
        assert get_round_winner(scores) == TeamId.TEAM_B

    def test_tie_returns_none(self):
        scores = {TeamId.TEAM_A: 78, TeamId.TEAM_B: 78}
        assert get_round_winner(scores) is None

    def test_empty_returns_none(self):
        assert get_round_winner({}) is None


# ---------------------------------------------------------------------------
# get_game_winner
# ---------------------------------------------------------------------------

class TestGetGameWinner:
    def test_no_scores_returns_none(self):
        state = make_state()
        assert get_game_winner(state) is None

    def test_below_winning_score_returns_none(self):
        state = make_state(scores={
            TeamId.TEAM_A: TeamScore(team=TeamId.TEAM_A, total=999),
            TeamId.TEAM_B: TeamScore(team=TeamId.TEAM_B, total=800),
        })
        assert get_game_winner(state) is None

    def test_returns_winner_at_1000(self):
        state = make_state(scores={
            TeamId.TEAM_A: TeamScore(team=TeamId.TEAM_A, total=1000),
            TeamId.TEAM_B: TeamScore(team=TeamId.TEAM_B, total=850),
        })
        assert get_game_winner(state) == TeamId.TEAM_A

    def test_both_over_1000_higher_wins(self):
        state = make_state(scores={
            TeamId.TEAM_A: TeamScore(team=TeamId.TEAM_A, total=1050),
            TeamId.TEAM_B: TeamScore(team=TeamId.TEAM_B, total=1010),
        })
        assert get_game_winner(state) == TeamId.TEAM_A

    def test_team_b_over_1000(self):
        state = make_state(scores={
            TeamId.TEAM_A: TeamScore(team=TeamId.TEAM_A, total=900),
            TeamId.TEAM_B: TeamScore(team=TeamId.TEAM_B, total=1157),
        })
        assert get_game_winner(state) == TeamId.TEAM_B


# ---------------------------------------------------------------------------
# round_score_summary
# ---------------------------------------------------------------------------

class TestRoundScoreSummary:
    def test_returns_all_keys(self):
        tricks = make_9_tricks(team_a_wins=5)
        state = make_state(completed_tricks=tricks)
        v = Schieber()
        state = apply_round_scores(state, v)
        summary = round_score_summary(state)
        assert "team_a" in summary
        assert "team_b" in summary
        assert "round_winner" in summary
        assert "game_winner" in summary

    def test_round_and_total_present(self):
        tricks = make_9_tricks(team_a_wins=5)
        state = make_state(completed_tricks=tricks)
        state = apply_round_scores(state, Schieber())
        summary = round_score_summary(state)
        assert "round" in summary["team_a"]
        assert "total" in summary["team_a"]

    def test_no_scores_returns_zeros(self):
        state = make_state()
        summary = round_score_summary(state)
        assert summary["team_a"]["total"] == 0
        assert summary["team_b"]["total"] == 0


# ---------------------------------------------------------------------------
# tricks_per_team / points_per_team
# ---------------------------------------------------------------------------

class TestMidRoundHelpers:
    def test_tricks_per_team(self):
        tricks = [
            make_trick([entry("p1", Suit.ROSE, Rank.ACE)] * 4, winner_id="p1", points=11),
            make_trick([entry("p2", Suit.ROSE, Rank.ACE)] * 4, winner_id="p2", points=11),
            make_trick([entry("p1", Suit.ROSE, Rank.ACE)] * 4, winner_id="p1", points=11),
        ]
        state = make_state(completed_tricks=tricks)
        counts = tricks_per_team(state)
        assert counts[TeamId.TEAM_A] == 2
        assert counts[TeamId.TEAM_B] == 1

    def test_points_per_team(self):
        tricks = [
            make_trick([entry("p1", Suit.ROSE, Rank.ACE)] * 4, winner_id="p1", points=20),
            make_trick([entry("p2", Suit.ROSE, Rank.ACE)] * 4, winner_id="p2", points=10),
        ]
        state = make_state(completed_tricks=tricks)
        pts = points_per_team(state)
        assert pts[TeamId.TEAM_A] == 20
        assert pts[TeamId.TEAM_B] == 10

    def test_empty_tricks(self):
        state = make_state(completed_tricks=[])
        assert tricks_per_team(state) == {TeamId.TEAM_A: 0, TeamId.TEAM_B: 0}
        assert points_per_team(state) == {TeamId.TEAM_A: 0, TeamId.TEAM_B: 0}
