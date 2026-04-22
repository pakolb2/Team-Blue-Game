"""
tests/test_engine.py
---------------------
Tests for Phase 5: server/game/engine.py

Covers:
  - Construction & setup
  - start() — dealing and phase transition
  - choose_trump() — trump selection and validation
  - play_card() — single card, trick completion, round completion
  - Full game simulation — 36 cards played to completion
  - get_state_for() — hand hiding
  - start_next_round() — multi-round games
  - Error cases throughout

Run with:  pytest tests/test_engine.py -v
"""

import pytest
import random

from server.shared.types import (
    Card, Player, GamePhase, TeamId, TrumpMode, Suit, Rank, TeamScore,
)
from server.shared.constants import TRICKS_PER_ROUND, HAND_SIZE, WINNING_SCORE
from server.game.engine import GameEngine
from server.game.variants.schieber import Schieber


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_players(n: int = 4) -> list[Player]:
    return [Player(id=f"p{i}", name=f"Player{i}") for i in range(n)]


def make_engine(players: list[Player] | None = None) -> GameEngine:
    return GameEngine(players or make_players(), Schieber())


def started_engine() -> GameEngine:
    engine = make_engine()
    engine.start()
    return engine


def playing_engine(trump: TrumpMode = TrumpMode.EICHEL) -> GameEngine:
    engine = started_engine()
    trump_player = engine.state.trump_player_id
    engine.choose_trump(trump_player, trump)
    return engine


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_requires_four_players(self):
        with pytest.raises(ValueError, match="4 players"):
            GameEngine(make_players(3), Schieber())

    def test_teams_assigned_on_init(self):
        engine = make_engine()
        players = engine.state.players
        assert players[0].team == TeamId.TEAM_A
        assert players[1].team == TeamId.TEAM_B
        assert players[2].team == TeamId.TEAM_A
        assert players[3].team == TeamId.TEAM_B

    def test_initial_phase_is_waiting(self):
        assert make_engine().state.phase == GamePhase.WAITING

    def test_scores_initialised_for_both_teams(self):
        engine = make_engine()
        assert TeamId.TEAM_A in engine.state.scores
        assert TeamId.TEAM_B in engine.state.scores

    def test_for_room_sets_room_id(self):
        engine = GameEngine.for_room("room42", make_players(), Schieber())
        assert engine.state.room_id == "room42"


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------

class TestStart:
    def test_phase_becomes_trump_select(self):
        engine = make_engine()
        engine.start()
        assert engine.state.phase == GamePhase.TRUMP_SELECT

    def test_each_player_gets_9_cards(self):
        engine = started_engine()
        for player in engine.state.players:
            assert len(player.hand) == HAND_SIZE

    def test_all_36_cards_dealt(self):
        engine = started_engine()
        all_cards = [c for p in engine.state.players for c in p.hand]
        assert len(all_cards) == 36
        assert len(set(all_cards)) == 36  # no duplicates

    def test_trump_player_id_set(self):
        engine = started_engine()
        assert engine.state.trump_player_id is not None

    def test_current_player_is_trump_player(self):
        engine = started_engine()
        assert engine.state.current_player_id == engine.state.trump_player_id

    def test_current_trick_is_empty(self):
        engine = started_engine()
        assert not engine.state.current_trick.entries

    def test_completed_tricks_empty(self):
        engine = started_engine()
        assert engine.state.completed_tricks == []

    def test_cannot_start_twice(self):
        engine = started_engine()
        with pytest.raises(ValueError, match="phase"):
            engine.start()

    def test_round_0_trump_player_is_seat_0(self):
        engine = make_engine()
        engine.start()
        assert engine.state.trump_player_id == engine.state.players[0].id

    def test_different_deals_each_time(self):
        """Two starts should (almost certainly) produce different hands."""
        e1 = make_engine()
        e2 = make_engine()
        e1.start()
        e2.start()
        assert e1.state.players[0].hand != e2.state.players[0].hand


# ---------------------------------------------------------------------------
# choose_trump()
# ---------------------------------------------------------------------------

class TestChooseTrump:
    def test_phase_becomes_playing(self):
        engine = started_engine()
        tp = engine.state.trump_player_id
        engine.choose_trump(tp, TrumpMode.EICHEL)
        assert engine.state.phase == GamePhase.PLAYING

    def test_trump_mode_stored(self):
        engine = started_engine()
        tp = engine.state.trump_player_id
        engine.choose_trump(tp, TrumpMode.ROSE)
        assert engine.state.trump_mode == TrumpMode.ROSE

    def test_all_trump_modes_accepted(self):
        for mode in TrumpMode:
            engine = started_engine()
            tp = engine.state.trump_player_id
            engine.choose_trump(tp, mode)
            assert engine.state.trump_mode == mode

    def test_wrong_player_raises(self):
        engine = started_engine()
        tp = engine.state.trump_player_id
        other = next(p.id for p in engine.state.players if p.id != tp)
        with pytest.raises(ValueError, match="may choose trump"):
            engine.choose_trump(other, TrumpMode.EICHEL)

    def test_wrong_phase_raises(self):
        engine = make_engine()   # WAITING phase
        with pytest.raises(ValueError, match="TRUMP_SELECT"):
            engine.choose_trump("p0", TrumpMode.EICHEL)

    def test_current_player_set_after_trump(self):
        engine = started_engine()
        tp = engine.state.trump_player_id
        engine.choose_trump(tp, TrumpMode.EICHEL)
        # Trump chooser leads the first trick
        assert engine.state.current_player_id == tp


# ---------------------------------------------------------------------------
# play_card() — single plays
# ---------------------------------------------------------------------------

class TestPlayCard:
    def test_card_removed_from_hand(self):
        engine = playing_engine()
        current_pid = engine.state.current_player_id
        player = engine.state.get_player(current_pid)
        card_to_play = engine.variant.get_legal_moves(engine.state, current_pid)[0]
        initial_count = len(player.hand)
        engine.play_card(current_pid, card_to_play)
        new_player = engine.state.get_player(current_pid)
        assert len(new_player.hand) == initial_count - 1
        assert card_to_play not in new_player.hand

    def test_card_added_to_trick(self):
        engine = playing_engine()
        pid = engine.state.current_player_id
        card = engine.variant.get_legal_moves(engine.state, pid)[0]
        engine.play_card(pid, card)
        assert card in engine.state.current_trick.cards

    def test_turn_advances_after_play(self):
        engine = playing_engine()
        pid = engine.state.current_player_id
        next_pid = engine.state.next_player_id(pid)
        card = engine.variant.get_legal_moves(engine.state, pid)[0]
        engine.play_card(pid, card)
        assert engine.state.current_player_id == next_pid

    def test_wrong_turn_raises(self):
        engine = playing_engine()
        current = engine.state.current_player_id
        other = engine.state.next_player_id(current)
        card = engine.state.get_player(other).hand[0]
        with pytest.raises(ValueError, match="turn"):
            engine.play_card(other, card)

    def test_wrong_phase_raises(self):
        engine = started_engine()  # TRUMP_SELECT phase
        with pytest.raises(ValueError, match="phase"):
            engine.play_card("p0", Card(suit=Suit.ROSE, rank=Rank.ACE))

    def test_card_not_in_hand_raises(self):
        engine = playing_engine()
        pid = engine.state.current_player_id
        # Find a card not in their hand
        hand = engine.state.get_player(pid).hand
        all_cards = [Card(suit=s, rank=r) for s in Suit for r in Rank]
        foreign = next(c for c in all_cards if c not in hand)
        with pytest.raises(ValueError, match="not in"):
            engine.play_card(pid, foreign)

    def test_lead_suit_set_on_first_card(self):
        engine = playing_engine()
        pid = engine.state.current_player_id
        card = engine.variant.get_legal_moves(engine.state, pid)[0]
        engine.play_card(pid, card)
        assert engine.state.current_trick.lead_suit == card.suit


# ---------------------------------------------------------------------------
# Trick completion
# ---------------------------------------------------------------------------

class TestTrickCompletion:
    def _play_full_trick(self, engine: GameEngine) -> GameEngine:
        """Play one complete trick with legal moves."""
        for _ in range(4):
            pid = engine.state.current_player_id
            legal = engine.variant.get_legal_moves(engine.state, pid)
            engine.play_card(pid, legal[0])
        return engine

    def test_trick_moved_to_completed(self):
        engine = playing_engine()
        self._play_full_trick(engine)
        assert len(engine.state.completed_tricks) == 1
        assert not engine.state.current_trick.entries

    def test_completed_trick_has_winner(self):
        engine = playing_engine()
        self._play_full_trick(engine)
        trick = engine.state.completed_tricks[0]
        assert trick.winner_id is not None
        assert trick.winner_id in [p.id for p in engine.state.players]

    def test_completed_trick_has_points(self):
        engine = playing_engine()
        self._play_full_trick(engine)
        trick = engine.state.completed_tricks[0]
        assert trick.points >= 0  # Could be 0 if all zero-value cards

    def test_trick_winner_leads_next(self):
        engine = playing_engine()
        self._play_full_trick(engine)
        winner_id = engine.state.completed_tricks[0].winner_id
        assert engine.state.current_player_id == winner_id

    def test_nine_tricks_advances_to_scoring(self):
        engine = playing_engine()
        for _ in range(TRICKS_PER_ROUND):
            self._play_full_trick(engine)
        assert engine.state.phase in (GamePhase.SCORING, GamePhase.FINISHED)

    def test_nine_tricks_scores_set(self):
        engine = playing_engine()
        for _ in range(TRICKS_PER_ROUND):
            self._play_full_trick(engine)
        for team in TeamId:
            assert team in engine.state.scores
            assert len(engine.state.scores[team].round_scores) == 1

    def test_nine_tricks_hands_empty(self):
        engine = playing_engine()
        for _ in range(TRICKS_PER_ROUND):
            self._play_full_trick(engine)
        for player in engine.state.players:
            assert player.hand == []


# ---------------------------------------------------------------------------
# Full game simulation
# ---------------------------------------------------------------------------

class TestFullGameSimulation:
    def _play_game(
        self,
        trump: TrumpMode = TrumpMode.EICHEL,
        seed: int = 42,
    ) -> GameEngine:
        """Simulate a full game (multiple rounds) until game_over."""
        random.seed(seed)
        engine = GameEngine.for_room("sim_room", make_players(), Schieber())
        engine.start()  # first round

        max_rounds = 20   # safety cap
        for _ in range(max_rounds):
            tp = engine.state.trump_player_id
            engine.choose_trump(tp, trump)

            while engine.state.phase == GamePhase.PLAYING:
                pid = engine.state.current_player_id
                legal = engine.variant.get_legal_moves(engine.state, pid)
                engine.play_card(pid, legal[0])

            if engine.state.game_over:
                break

            # SCORING phase — start the next round (which calls start() internally)
            engine.start_next_round()

        return engine

    def test_game_ends_with_winner(self):
        engine = self._play_game()
        assert engine.state.game_over
        assert engine.state.winner in TeamId

    def test_game_phase_is_finished(self):
        engine = self._play_game()
        assert engine.state.phase == GamePhase.FINISHED

    def test_winner_has_1000_or_more(self):
        engine = self._play_game()
        winner = engine.state.winner
        assert engine.state.scores[winner].total >= WINNING_SCORE

    def test_all_hands_empty_at_end(self):
        engine = self._play_game()
        for player in engine.state.players:
            assert player.hand == []

    def test_scores_are_positive(self):
        engine = self._play_game()
        for ts in engine.state.scores.values():
            assert ts.total >= 0

    def test_full_game_different_trump_modes(self):
        """Game should complete for every trump mode."""
        for mode in TrumpMode:
            engine = self._play_game(trump=mode)
            assert engine.state.game_over, f"Game did not finish with trump={mode}"

    def test_all_36_cards_played_each_round(self):
        """After each round of 9 tricks, all 36 cards should have been played."""
        random.seed(0)
        engine = GameEngine.for_room("r", make_players(), Schieber())
        engine.start()
        tp = engine.state.trump_player_id
        engine.choose_trump(tp, TrumpMode.EICHEL)

        while engine.state.phase == GamePhase.PLAYING:
            pid = engine.state.current_player_id
            legal = engine.variant.get_legal_moves(engine.state, pid)
            engine.play_card(pid, legal[0])

        assert len(engine.state.completed_tricks) == 9
        all_played = [
            entry.card
            for t in engine.state.completed_tricks
            for entry in t.entries
        ]
        assert len(all_played) == 36
        assert len(set(all_played)) == 36  # every card played exactly once

    def test_round_scores_sum_correctly(self):
        """After a round, team scores should sum to TOTAL_ROUND_POINTS (157)."""
        from server.shared.constants import TOTAL_ROUND_POINTS, MATCH_BONUS
        random.seed(7)
        engine = GameEngine.for_room("r", make_players(), Schieber())
        engine.start()
        tp = engine.state.trump_player_id
        engine.choose_trump(tp, TrumpMode.EICHEL)

        while engine.state.phase == GamePhase.PLAYING:
            pid = engine.state.current_player_id
            legal = engine.variant.get_legal_moves(engine.state, pid)
            engine.play_card(pid, legal[0])

        # Sum of both teams' round scores
        total = sum(
            ts.round_scores[-1]
            for ts in engine.state.scores.values()
        )
        # Either 157 (normal) or 157 + 100 match bonus (one team won all)
        assert total in (TOTAL_ROUND_POINTS, TOTAL_ROUND_POINTS + MATCH_BONUS)


# ---------------------------------------------------------------------------
# get_state_for()
# ---------------------------------------------------------------------------

class TestGetStateFor:
    def test_own_hand_visible(self):
        engine = playing_engine()
        pid = engine.state.players[0].id
        view = engine.get_state_for(pid)
        assert len(view.players[0].hand) > 0

    def test_other_hands_hidden(self):
        engine = playing_engine()
        pid = engine.state.players[0].id
        view = engine.get_state_for(pid)
        for player in view.players[1:]:
            assert player.hand == []

    def test_does_not_mutate_engine_state(self):
        engine = playing_engine()
        pid = engine.state.players[0].id
        original_hand_size = len(engine.state.players[1].hand)
        engine.get_state_for(pid)
        assert len(engine.state.players[1].hand) == original_hand_size

    def test_public_info_unchanged(self):
        engine = playing_engine()
        pid = engine.state.players[0].id
        view = engine.get_state_for(pid)
        assert view.trump_mode == engine.state.trump_mode
        assert view.phase == engine.state.phase
        assert view.current_player_id == engine.state.current_player_id


# ---------------------------------------------------------------------------
# start_next_round()
# ---------------------------------------------------------------------------

class TestStartNextRound:
    def _finish_one_round(self) -> GameEngine:
        """Play a full round and return the engine in SCORING phase."""
        random.seed(99)
        engine = GameEngine.for_room("r", make_players(), Schieber())
        engine.start()
        tp = engine.state.trump_player_id
        engine.choose_trump(tp, TrumpMode.EICHEL)
        while engine.state.phase == GamePhase.PLAYING:
            pid = engine.state.current_player_id
            legal = engine.variant.get_legal_moves(engine.state, pid)
            engine.play_card(pid, legal[0])
        return engine

    def test_round_number_increments(self):
        engine = self._finish_one_round()
        if engine.state.phase == GamePhase.SCORING:
            engine.start_next_round()
            assert engine.state.round_number == 1

    def test_new_cards_dealt(self):
        engine = self._finish_one_round()
        if engine.state.phase == GamePhase.SCORING:
            engine.start_next_round()
            for p in engine.state.players:
                assert len(p.hand) == HAND_SIZE

    def test_trump_player_rotates(self):
        engine = self._finish_one_round()
        if engine.state.phase == GamePhase.SCORING:
            engine.start_next_round()
            # Round 1 → seat 1 picks trump
            assert engine.state.trump_player_id == engine.state.players[1].id

    def test_raises_when_game_over(self):
        engine = self._finish_one_round()
        # Force game over
        engine._state = engine._state.model_copy(update={
            "game_over": True,
            "phase": GamePhase.FINISHED,
        })
        with pytest.raises(ValueError, match="game is over"):
            engine.start_next_round()

    def test_raises_wrong_phase(self):
        engine = playing_engine()
        with pytest.raises(ValueError, match="SCORING"):
            engine.start_next_round()
