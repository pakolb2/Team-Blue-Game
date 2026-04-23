"""
tests/test_variants/test_phase10.py
-------------------------------------
Tests for Phase 10: Differenzler and Coiffeur variants.

Covers:
  - Differenzler: prediction storage, penalty calculation, scoring,
    game-over condition, full simulation
  - Coiffeur: mode tracking, doubling, available modes,
    game-over condition, full simulation
  - Both variants registered in the room manager registry
  - Full bot games with each variant

Run with:  pytest tests/test_variants/test_phase10.py -v
"""

import random
import pytest

from server.shared.types import (
    Card, Player, Trick, TrickEntry, GameState,
    Suit, Rank, TrumpMode, GamePhase, TeamId, TeamScore,
)
from server.shared.constants import LAST_TRICK_BONUS, MATCH_BONUS

# Differenzler imports
from server.game.variants.differenzler import (
    Differenzler, set_prediction, get_prediction,
    clear_predictions, DIFFERENZLER_ROUNDS,
)

# Coiffeur imports
from server.game.variants.coiffeur import (
    Coiffeur, record_mode_played, is_mode_played,
    get_available_modes, clear_tracker, COIFFEUR_MODES,
    COIFFEUR_TOTAL_ROUNDS,
)

# Room manager registry
from server.rooms.room_manager import get_variant, VARIANT_REGISTRY

# Engine + bots for simulation
from server.game.engine import GameEngine
from server.bots.random_bot import RandomBot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def c(suit: Suit, rank: Rank) -> Card:
    return Card(suit=suit, rank=rank)


def make_trick(entries: list[TrickEntry], winner_id: str | None = None,
               points: int = 0) -> Trick:
    lead = entries[0].card.suit if entries else None
    return Trick(entries=entries, winner_id=winner_id, lead_suit=lead, points=points)


def entry(pid: str, suit: Suit, rank: Rank) -> TrickEntry:
    return TrickEntry(player_id=pid, card=c(suit, rank))


def make_state(
    trump_mode: TrumpMode = TrumpMode.EICHEL,
    completed_tricks: list[Trick] | None = None,
    trump_player_id: str = "p1",
    round_number: int = 0,
    scores: dict | None = None,
    room_id: str = "test_room",
) -> GameState:
    players = [
        Player(id="p1", name="Alice", team=TeamId.TEAM_A),
        Player(id="p2", name="Bob",   team=TeamId.TEAM_B),
        Player(id="p3", name="Carol", team=TeamId.TEAM_A),
        Player(id="p4", name="Dave",  team=TeamId.TEAM_B),
    ]
    return GameState(
        room_id=room_id,
        players=players,
        phase=GamePhase.SCORING,
        trump_mode=trump_mode,
        trump_player_id=trump_player_id,
        completed_tricks=completed_tricks or [],
        round_number=round_number,
        scores=scores or {},
    )


def make_9_tricks(winner_id: str = "p1", pts_each: int = 10) -> list[Trick]:
    tricks = []
    for _ in range(9):
        t = make_trick(
            [entry("p1", Suit.ROSE, Rank.ACE),
             entry("p2", Suit.ROSE, Rank.SIX),
             entry("p3", Suit.ROSE, Rank.SEVEN),
             entry("p4", Suit.ROSE, Rank.EIGHT)],
            winner_id=winner_id,
            points=pts_each,
        )
        tricks.append(t)
    return tricks


def make_players() -> list[Player]:
    return [Player(id=f"p{i}", name=f"P{i}") for i in range(4)]


def run_full_game(variant, seed: int = 0, max_rounds: int = 30) -> GameEngine:
    """Run a complete game with bots using the given variant."""
    random.seed(seed)
    engine = GameEngine.for_room("sim", make_players(), variant)
    engine.start()

    for _ in range(max_rounds):
        if engine.state.phase == GamePhase.TRUMP_SELECT:
            tp = engine.state.trump_player_id
            # For Coiffeur, pick an available mode
            if isinstance(variant, Coiffeur):
                team = engine.state.get_player_team(tp)
                available = get_available_modes("sim", team) if team else []
                mode = available[0] if available else list(TrumpMode)[0]
            else:
                mode = random.choice(list(TrumpMode))
            engine.choose_trump(tp, mode)
            if isinstance(variant, Coiffeur):
                variant.on_round_start(engine.state)

        while engine.state.phase == GamePhase.PLAYING:
            pid = engine.state.current_player_id
            view = engine.get_state_for(pid)
            legal = variant.get_legal_moves(view, pid)
            engine.play_card(pid, legal[0])

        if engine.state.game_over:
            break
        if engine.state.phase == GamePhase.SCORING:
            engine.start_next_round()

    return engine


# ===========================================================================
# Differenzler tests
# ===========================================================================

class TestDifferenzlerPredictions:
    def setup_method(self):
        clear_predictions("test_room")

    def test_set_and_get_prediction(self):
        set_prediction("test_room", "p1", 80)
        assert get_prediction("test_room", "p1") == 80

    def test_default_prediction_is_zero(self):
        assert get_prediction("test_room", "p_unknown") == 0

    def test_prediction_clamped_to_valid_range(self):
        set_prediction("test_room", "p1", 200)
        assert get_prediction("test_room", "p1") == 157  # max

        set_prediction("test_room", "p1", -10)
        assert get_prediction("test_room", "p1") == 0    # min

    def test_clear_predictions(self):
        set_prediction("test_room", "p1", 80)
        clear_predictions("test_room")
        assert get_prediction("test_room", "p1") == 0

    def test_multiple_players(self):
        set_prediction("test_room", "p1", 80)
        set_prediction("test_room", "p2", 50)
        assert get_prediction("test_room", "p1") == 80
        assert get_prediction("test_room", "p2") == 50


class TestDifferenzlerScoring:
    def setup_method(self):
        self.v = Differenzler()
        clear_predictions("test_room")

    def test_zero_penalty_when_prediction_matches(self):
        """Player predicts exactly their trick points → penalty = 0."""
        # p1 wins all 9 tricks of 10pts + 5 last trick bonus = 95pts
        tricks = make_9_tricks(winner_id="p1", pts_each=10)
        state = make_state(completed_tricks=tricks)

        # p1 predicted 95 (9×10 + 5 last trick bonus)
        set_prediction("test_room", "p1", 95)

        penalties = self.v.get_player_penalties(state)
        assert penalties["p1"] == 0

    def test_penalty_is_absolute_difference(self):
        """Penalty = |prediction - actual|."""
        tricks = make_9_tricks(winner_id="p1", pts_each=10)
        state = make_state(completed_tricks=tricks)

        set_prediction("test_room", "p1", 50)  # actual = 95, diff = 45
        penalties = self.v.get_player_penalties(state)
        assert penalties["p1"] == 45

    def test_penalty_same_above_and_below(self):
        """Missing by +30 and -30 both give penalty 30."""
        tricks = make_9_tricks(winner_id="p1", pts_each=10)
        state = make_state(completed_tricks=tricks)

        # Actual for p1 = 95 (9*10 + 5 bonus)
        set_prediction("test_room", "p1", 65)   # under by 30
        assert self.v.get_player_penalties(state)["p1"] == 30

        set_prediction("test_room", "p1", 125)  # over by 30
        assert self.v.get_player_penalties(state)["p1"] == 30

    def test_score_game_returns_team_totals(self):
        """score_game() sums per-player penalties by team."""
        tricks = make_9_tricks(winner_id="p1", pts_each=10)
        state = make_state(completed_tricks=tricks)
        set_prediction("test_room", "p1", 90)   # penalty = 5 (TEAM_A)
        set_prediction("test_room", "p3", 0)    # penalty = 0 (TEAM_A)
        set_prediction("test_room", "p2", 0)    # penalty = 0 (TEAM_B)
        set_prediction("test_room", "p4", 0)    # penalty = 0 (TEAM_B)

        scores = self.v.score_game(state)
        assert scores[TeamId.TEAM_A] == 5   # p1 missed by 5
        assert scores[TeamId.TEAM_B] == 0

    def test_last_trick_bonus_included_in_actual(self):
        """The last-trick bonus (+5) must be included in actual score."""
        tricks = make_9_tricks(winner_id="p1", pts_each=10)
        state = make_state(completed_tricks=tricks)

        # p1 wins all tricks: 9*10 = 90 card pts + 5 bonus = 95 actual
        set_prediction("test_room", "p1", 90)   # predicts without bonus
        penalties = self.v.get_player_penalties(state)
        assert penalties["p1"] == 5  # missed by 5 (bonus not counted)

    def test_no_tricks_zero_actual(self):
        """Player who wins no tricks has actual = 0."""
        tricks = make_9_tricks(winner_id="p1", pts_each=10)
        state = make_state(completed_tricks=tricks)
        set_prediction("test_room", "p2", 30)

        penalties = self.v.get_player_penalties(state)
        assert penalties["p2"] == 30   # predicted 30, got 0


class TestDifferenzlerGameOver:
    def setup_method(self):
        self.v = Differenzler(rounds=4)

    def test_not_over_before_rounds(self):
        state = make_state(round_number=3)
        assert not self.v.is_game_over(state)

    def test_over_at_round_count(self):
        state = make_state(round_number=4)
        assert self.v.is_game_over(state)

    def test_over_after_round_count(self):
        state = make_state(round_number=10)
        assert self.v.is_game_over(state)

    def test_custom_round_count(self):
        v = Differenzler(rounds=8)
        assert not v.is_game_over(make_state(round_number=7))
        assert     v.is_game_over(make_state(round_number=8))


class TestDifferenzlerSimulation:
    def test_full_game_completes(self):
        v = Differenzler(rounds=4)
        engine = run_full_game(v, seed=1, max_rounds=20)
        assert engine.state.round_number >= 4

    def test_card_ranking_same_as_schieber(self):
        """Differenzler uses identical card ranking to Schieber."""
        from server.game.variants.schieber import Schieber
        d = Differenzler()
        s = Schieber()
        state = make_state()
        card = c(Suit.EICHEL, Rank.JACK)
        assert d.card_rank_value(card, state) == s.card_rank_value(card, state)

    def test_legal_moves_same_as_schieber(self):
        """Differenzler uses identical legal move rules to Schieber."""
        from server.game.variants.schieber import Schieber
        d = Differenzler()
        s = Schieber()
        hand = [c(Suit.ROSE, Rank.ACE), c(Suit.EICHEL, Rank.TEN)]
        players = [
            Player(id="p1", name="P1", team=TeamId.TEAM_A, hand=hand),
            Player(id="p2", name="P2", team=TeamId.TEAM_B),
            Player(id="p3", name="P3", team=TeamId.TEAM_A),
            Player(id="p4", name="P4", team=TeamId.TEAM_B),
        ]
        state = GameState(
            room_id="r", players=players, phase=GamePhase.PLAYING,
            trump_mode=TrumpMode.EICHEL, current_player_id="p1",
        )
        assert set(d.get_legal_moves(state, "p1")) == set(s.get_legal_moves(state, "p1"))


# ===========================================================================
# Coiffeur tests
# ===========================================================================

class TestCoiffeurModeTracking:
    def setup_method(self):
        clear_tracker("test_room")

    def test_initial_all_modes_available(self):
        modes = get_available_modes("test_room", TeamId.TEAM_A)
        assert set(modes) == set(COIFFEUR_MODES)

    def test_record_mode_removes_from_available(self):
        record_mode_played("test_room", TeamId.TEAM_A, TrumpMode.EICHEL)
        available = get_available_modes("test_room", TeamId.TEAM_A)
        assert TrumpMode.EICHEL not in available
        assert len(available) == 5

    def test_teams_tracked_independently(self):
        record_mode_played("test_room", TeamId.TEAM_A, TrumpMode.EICHEL)
        # TEAM_B should still have all modes
        assert TrumpMode.EICHEL in get_available_modes("test_room", TeamId.TEAM_B)

    def test_is_mode_played_true_after_record(self):
        record_mode_played("test_room", TeamId.TEAM_A, TrumpMode.ROSE)
        assert is_mode_played("test_room", TeamId.TEAM_A, TrumpMode.ROSE)

    def test_is_mode_played_false_before_record(self):
        assert not is_mode_played("test_room", TeamId.TEAM_A, TrumpMode.ROSE)

    def test_clear_tracker(self):
        record_mode_played("test_room", TeamId.TEAM_A, TrumpMode.EICHEL)
        clear_tracker("test_room")
        assert TrumpMode.EICHEL in get_available_modes("test_room", TeamId.TEAM_A)

    def test_all_modes_eventually_exhausted(self):
        for mode in COIFFEUR_MODES:
            record_mode_played("test_room", TeamId.TEAM_A, mode)
        assert get_available_modes("test_room", TeamId.TEAM_A) == []


class TestCoiffeurScoring:
    def setup_method(self):
        self.v = Coiffeur()
        clear_tracker("test_room")

    def test_normal_round_no_doubling(self):
        """First time a mode is played — no doubling."""
        tricks = make_9_tricks(winner_id="p1", pts_each=10)
        state = make_state(completed_tricks=tricks, trump_mode=TrumpMode.EICHEL)

        scores = self.v.score_game(state)
        # Schieber: p1 wins all → TEAM_A gets 9*10 + 5 bonus + 100 match = 195
        assert scores[TeamId.TEAM_A] == 195
        assert scores[TeamId.TEAM_B] == 0

    def test_coiffeur_round_doubles_trump_team_score(self):
        """Second time a mode is played by same team → doubled."""
        # Mark EICHEL as already played by TEAM_A
        record_mode_played("test_room", TeamId.TEAM_A, TrumpMode.EICHEL)

        tricks = make_9_tricks(winner_id="p1", pts_each=10)
        state = make_state(completed_tricks=tricks, trump_mode=TrumpMode.EICHEL)

        scores = self.v.score_game(state)
        # Base = 195 (match bonus), doubled = 390
        assert scores[TeamId.TEAM_A] == 390

    def test_coiffeur_does_not_double_opponent(self):
        """Doubling only applies to the trump-choosing team."""
        record_mode_played("test_room", TeamId.TEAM_A, TrumpMode.EICHEL)

        # Split tricks: p1 (TEAM_A) wins 5, p2 (TEAM_B) wins 4
        tricks = []
        for i in range(5):
            t = make_trick(
                [entry("p1",Suit.ROSE,Rank.ACE),
                 entry("p2",Suit.ROSE,Rank.SIX),
                 entry("p3",Suit.ROSE,Rank.SEVEN),
                 entry("p4",Suit.ROSE,Rank.EIGHT)],
                winner_id="p1", points=10,
            )
            tricks.append(t)
        for i in range(4):
            t = make_trick(
                [entry("p1",Suit.ROSE,Rank.SIX),
                 entry("p2",Suit.ROSE,Rank.ACE),
                 entry("p3",Suit.ROSE,Rank.SEVEN),
                 entry("p4",Suit.ROSE,Rank.EIGHT)],
                winner_id="p2", points=10,
            )
            tricks.append(t)

        state = make_state(completed_tricks=tricks, trump_mode=TrumpMode.EICHEL)
        base = Coiffeur.__new__(Coiffeur)
        base._schieber = __import__(
            'server.game.variants.schieber', fromlist=['Schieber']
        ).Schieber()
        from server.game.variants.schieber import Schieber
        base_scores = Schieber().score_game(state)

        self.v = Coiffeur()
        scores = self.v.score_game(state)

        # TEAM_A score doubled, TEAM_B score unchanged
        assert scores[TeamId.TEAM_A] == base_scores[TeamId.TEAM_A] * 2
        assert scores[TeamId.TEAM_B] == base_scores[TeamId.TEAM_B]

    def test_is_coiffeur_round_false_first_time(self):
        state = make_state(trump_mode=TrumpMode.EICHEL)
        assert not self.v.is_coiffeur_round(state)

    def test_is_coiffeur_round_true_second_time(self):
        record_mode_played("test_room", TeamId.TEAM_A, TrumpMode.EICHEL)
        state = make_state(trump_mode=TrumpMode.EICHEL)
        assert self.v.is_coiffeur_round(state)

    def test_is_coiffeur_false_different_team(self):
        """Only triggers for the team that already played the mode."""
        record_mode_played("test_room", TeamId.TEAM_B, TrumpMode.EICHEL)
        # TEAM_A (p1) chose trump — they haven't played EICHEL yet
        state = make_state(trump_mode=TrumpMode.EICHEL, trump_player_id="p1")
        assert not self.v.is_coiffeur_round(state)


class TestCoiffeurGameOver:
    def setup_method(self):
        self.v = Coiffeur()
        clear_tracker("test_room")

    def test_not_over_at_start(self):
        state = make_state(round_number=0)
        assert not self.v.is_game_over(state)

    def test_over_at_total_rounds_cap(self):
        state = make_state(round_number=COIFFEUR_TOTAL_ROUNDS)
        assert self.v.is_game_over(state)

    def test_over_when_all_modes_played(self):
        """Game ends early if both teams exhaust all modes."""
        for mode in COIFFEUR_MODES:
            record_mode_played("test_room", TeamId.TEAM_A, mode)
            record_mode_played("test_room", TeamId.TEAM_B, mode)
        state = make_state(round_number=5)   # before cap
        assert self.v.is_game_over(state)

    def test_not_over_only_one_team_exhausted(self):
        """Both teams must exhaust modes for early termination."""
        for mode in COIFFEUR_MODES:
            record_mode_played("test_room", TeamId.TEAM_A, mode)
        state = make_state(round_number=5)
        # TEAM_B still has modes left
        assert not self.v.is_game_over(state)

    def test_available_modes_shrinks_each_round(self):
        record_mode_played("test_room", TeamId.TEAM_A, TrumpMode.EICHEL)
        record_mode_played("test_room", TeamId.TEAM_A, TrumpMode.ROSE)
        avail = self.v.get_available_modes_for_team("test_room", TeamId.TEAM_A)
        assert len(avail) == 4
        assert TrumpMode.EICHEL not in avail
        assert TrumpMode.ROSE not in avail


class TestCoiffeurSimulation:
    def test_full_game_completes(self):
        clear_tracker("sim")
        v = Coiffeur()
        engine = run_full_game(v, seed=2, max_rounds=30)
        # Should reach game-over or max rounds
        assert engine.state.round_number > 0

    def test_card_ranking_same_as_schieber(self):
        from server.game.variants.schieber import Schieber
        co = Coiffeur()
        s = Schieber()
        state = make_state()
        for suit in Suit:
            for rank in Rank:
                card = c(suit, rank)
                assert co.card_rank_value(card, state) == s.card_rank_value(card, state)


# ===========================================================================
# Variant registry
# ===========================================================================

class TestVariantRegistry:
    def test_schieber_registered(self):
        v = get_variant("schieber")
        assert v.name == "schieber"

    def test_differenzler_registered(self):
        v = get_variant("differenzler")
        assert v.name == "differenzler"

    def test_coiffeur_registered(self):
        v = get_variant("coiffeur")
        assert v.name == "coiffeur"

    def test_all_three_in_registry(self):
        assert len(VARIANT_REGISTRY) >= 3

    def test_case_insensitive(self):
        assert get_variant("DIFFERENZLER").name == "differenzler"
        assert get_variant("Coiffeur").name == "coiffeur"

    def test_unknown_raises(self):
        from server.rooms.room_manager import get_variant as gv
        with pytest.raises(ValueError, match="Unknown variant"):
            gv("nonexistent")
