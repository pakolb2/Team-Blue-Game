"""
tests/test_room_manager.py
---------------------------
Tests for Phase 7: server/rooms/room_manager.py

Covers:
  - Room creation, listing, deletion
  - Player join / leave / reconnect
  - Bot fill-in
  - Game start validation
  - Trump selection routing
  - Card play routing and explicit one-card bot advancement
  - Multi-round games through the room manager
  - Error cases throughout

Run with:  pytest tests/test_room_manager.py -v
"""

import random
import pytest

from server.shared.types import (
    Card, Player, GamePhase, TrumpMode, Suit, Rank, TeamId,
)
from server.shared.constants import WINNING_SCORE
from server.rooms.room_manager import RoomManager, get_variant
from server.game.variants.registry import clear_room_variant_state
from server.bots.random_bot import RandomBot
from server.bots.rule_based_bot import RuleBasedBot
from server.game.variants.schieber import Schieber
from server.game.variants.differenzler import Differenzler, set_prediction, get_prediction
from server.game.variants.coiffeur import (
    Coiffeur, clear_tracker, get_available_modes, record_mode_played,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(pid: str, name: str | None = None) -> Player:
    return Player(id=pid, name=name or pid.capitalize())


def make_manager() -> RoomManager:
    return RoomManager()


def filled_room_manager(bot_class=RandomBot) -> tuple[RoomManager, str]:
    """Return a manager with one full room ready to start."""
    mgr = make_manager()
    room = mgr.create_room("schieber", room_id="ROOM1")
    mgr.join_room("ROOM1", make_player("human1"))
    mgr.fill_with_bots("ROOM1", bot_class=bot_class)
    return mgr, "ROOM1"


def c(suit: Suit, rank: Rank) -> Card:
    return Card(suit=suit, rank=rank)


# ---------------------------------------------------------------------------
# Variant registry
# ---------------------------------------------------------------------------

class TestVariantRegistry:
    def test_schieber_registered(self):
        assert isinstance(get_variant("schieber"), Schieber)

    def test_differenzler_registered(self):
        assert isinstance(get_variant("differenzler"), Differenzler)

    def test_coiffeur_registered(self):
        assert isinstance(get_variant("coiffeur"), Coiffeur)

    def test_case_insensitive(self):
        assert get_variant("SCHIEBER") is not None
        assert get_variant("Coiffeur").name == "coiffeur"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown variant"):
            get_variant("unknown_game")

    def test_clear_room_variant_state_clears_registered_side_stores(self):
        set_prediction("R1", "p1", 80)
        clear_tracker("R1")
        record_mode_played("R1", TeamId.TEAM_A, TrumpMode.EICHEL)

        assert get_prediction("R1", "p1") == 80
        assert TrumpMode.EICHEL not in get_available_modes("R1", TeamId.TEAM_A)

        clear_room_variant_state("R1")

        assert get_prediction("R1", "p1") == 0
        assert TrumpMode.EICHEL in get_available_modes("R1", TeamId.TEAM_A)


# ---------------------------------------------------------------------------
# Room creation
# ---------------------------------------------------------------------------

class TestCreateRoom:
    def test_creates_room(self):
        mgr = make_manager()
        room = mgr.create_room("schieber", room_id="R1")
        assert room.id == "R1"

    def test_room_empty_on_creation(self):
        mgr = make_manager()
        room = mgr.create_room()
        assert room.players == []

    def test_auto_generated_id(self):
        mgr = make_manager()
        room = mgr.create_room()
        assert len(room.id) > 0

    def test_duplicate_room_id_raises(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        with pytest.raises(ValueError, match="already exists"):
            mgr.create_room("schieber", room_id="R1")

    def test_unknown_variant_raises(self):
        with pytest.raises(ValueError, match="Unknown variant"):
            make_manager().create_room("chess")

    def test_room_not_active_on_creation(self):
        mgr = make_manager()
        room = mgr.create_room()
        assert not room.is_active

    def test_variant_name_stored(self):
        mgr = make_manager()
        room = mgr.create_room("schieber", room_id="R1")
        assert room.variant_name == "schieber"


# ---------------------------------------------------------------------------
# get_room / list_rooms
# ---------------------------------------------------------------------------

class TestGetListRooms:
    def test_get_existing_room(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        assert mgr.get_room("R1").id == "R1"

    def test_get_missing_room_raises(self):
        with pytest.raises(KeyError):
            make_manager().get_room("NOPE")

    def test_list_rooms_empty(self):
        assert make_manager().list_rooms() == []

    def test_list_rooms_returns_all(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.create_room("schieber", room_id="R2")
        ids = {r.id for r in mgr.list_rooms()}
        assert ids == {"R1", "R2"}

    def test_list_open_rooms_excludes_full(self):
        mgr, rid = filled_room_manager()
        open_rooms = mgr.list_open_rooms()
        assert all(not r.is_full for r in open_rooms)

    def test_list_open_rooms_excludes_active(self):
        mgr, rid = filled_room_manager()
        mgr.start_game(rid)
        open_rooms = mgr.list_open_rooms()
        assert not any(r.id == rid for r in open_rooms)


# ---------------------------------------------------------------------------
# delete_room
# ---------------------------------------------------------------------------

class TestDeleteRoom:
    def test_delete_existing_room(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.delete_room("R1")
        with pytest.raises(KeyError):
            mgr.get_room("R1")

    def test_delete_missing_room_silent(self):
        make_manager().delete_room("NOPE")  # should not raise

    def test_delete_clears_player_index(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"))
        mgr.delete_room("R1")
        assert mgr.find_player_room("p1") is None


# ---------------------------------------------------------------------------
# join_room
# ---------------------------------------------------------------------------

class TestJoinRoom:
    def test_player_added(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        room = mgr.join_room("R1", make_player("p1"))
        assert "p1" in room.player_ids

    def test_player_index_updated(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"))
        assert mgr.find_player_room("p1") == "R1"

    def test_room_not_found_raises(self):
        with pytest.raises(KeyError):
            make_manager().join_room("NOPE", make_player("p1"))

    def test_full_room_raises(self):
        mgr, rid = filled_room_manager()
        with pytest.raises(ValueError, match="full"):
            mgr.join_room(rid, make_player("extra"))

    def test_duplicate_player_raises(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"))
        with pytest.raises(ValueError, match="already in room"):
            mgr.join_room("R1", make_player("p1"))

    def test_active_room_raises(self):
        mgr, rid = filled_room_manager()
        mgr.start_game(rid)
        with pytest.raises(ValueError, match="already in progress"):
            mgr.join_room(rid, make_player("late"))

    def test_four_players_fills_room(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        for i in range(4):
            mgr.join_room("R1", make_player(f"p{i}"))
        assert mgr.get_room("R1").is_full


# ---------------------------------------------------------------------------
# leave_room
# ---------------------------------------------------------------------------

class TestLeaveRoom:
    def test_player_removed_pre_game(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"))
        room = mgr.leave_room("R1", "p1")
        assert "p1" not in room.player_ids

    def test_player_marked_disconnected_in_game(self):
        mgr, rid = filled_room_manager()
        mgr.start_game(rid)
        room = mgr.leave_room(rid, "human1")
        p = next(p for p in room.players if p.id == "human1")
        assert not p.connected

    def test_leave_missing_player_raises(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        with pytest.raises(ValueError, match="not in room"):
            mgr.leave_room("R1", "ghost")

    def test_leave_missing_room_raises(self):
        with pytest.raises(KeyError):
            make_manager().leave_room("NOPE", "p1")


# ---------------------------------------------------------------------------
# reconnect_player
# ---------------------------------------------------------------------------

class TestReconnectPlayer:
    def test_reconnect_sets_connected_true(self):
        mgr, rid = filled_room_manager()
        mgr.start_game(rid)
        mgr.leave_room(rid, "human1")
        room = mgr.reconnect_player(rid, "human1")
        p = next(p for p in room.players if p.id == "human1")
        assert p.connected

    def test_reconnect_missing_player_raises(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        with pytest.raises(ValueError, match="not in room"):
            mgr.reconnect_player("R1", "ghost")


# ---------------------------------------------------------------------------
# fill_with_bots
# ---------------------------------------------------------------------------

class TestFillWithBots:
    def test_fills_empty_room(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        room = mgr.fill_with_bots("R1")
        assert room.is_full

    def test_fills_partial_room(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("human1"))
        room = mgr.fill_with_bots("R1")
        assert room.is_full
        assert len([p for p in room.players if p.is_bot]) == 3

    def test_bot_players_flagged(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.fill_with_bots("R1")
        room = mgr.get_room("R1")
        assert all(p.is_bot for p in room.players)

    def test_fill_active_room_raises(self):
        mgr, rid = filled_room_manager()
        mgr.start_game(rid)
        with pytest.raises(ValueError, match="already started"):
            mgr.fill_with_bots(rid)

    def test_fill_already_full_noop(self):
        mgr, rid = filled_room_manager()
        room = mgr.fill_with_bots(rid)  # already full
        assert len(room.players) == 4

    def test_is_bot_returns_true_for_bots(self):
        mgr, rid = filled_room_manager()
        room = mgr.get_room(rid)
        bot_ids = [p.id for p in room.players if p.is_bot]
        assert all(mgr.is_bot(rid, bid) for bid in bot_ids)

    def test_is_bot_returns_false_for_humans(self):
        mgr, rid = filled_room_manager()
        assert not mgr.is_bot(rid, "human1")

    def test_uses_specified_bot_class(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.fill_with_bots("R1", bot_class=RandomBot)
        bots = mgr._bots["R1"]
        assert all(isinstance(b, RandomBot) for b in bots.values())

class TestAddBot:
    def test_add_random_bot_adds_one_bot(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"))

        room = mgr.add_bot("R1", "random")

        assert len(room.players) == 2
        assert room.players[-1].is_bot
        assert isinstance(mgr.get_bot("R1", room.players[-1].id), RandomBot)

    def test_add_rule_based_bot_adds_one_bot(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")

        room = mgr.add_bot("R1", "rule_based")

        assert len(room.players) == 1
        assert room.players[0].is_bot
        assert isinstance(mgr.get_bot("R1", room.players[0].id), RuleBasedBot)

    def test_add_bot_full_room_raises(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        for i in range(4):
            mgr.join_room("R1", make_player(f"p{i}"))

        with pytest.raises(ValueError, match="full"):
            mgr.add_bot("R1", "random")

# ---------------------------------------------------------------------------
# start_game
# ---------------------------------------------------------------------------

class TestStartGame:
    def test_game_starts_successfully(self):
        mgr, rid = filled_room_manager()
        state = mgr.start_game(rid)
        assert state.phase in (GamePhase.TRUMP_SELECT, GamePhase.PLAYING)

    def test_room_marked_active(self):
        mgr, rid = filled_room_manager()
        mgr.start_game(rid)
        assert mgr.get_room(rid).is_active

    def test_engine_created(self):
        mgr, rid = filled_room_manager()
        mgr.start_game(rid)
        assert mgr.get_engine(rid) is not None

    def test_cards_dealt(self):
        mgr, rid = filled_room_manager()
        mgr.start_game(rid)
        engine = mgr.get_engine(rid)
        total = sum(len(p.hand) for p in engine.state.players)
        assert total == 36

    def test_start_game_auto_fills_missing_players_with_bots(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"))

        state = mgr.start_game("R1")

        room = mgr.get_room("R1")
        assert len(room.players) == 4
        assert sum(1 for p in room.players if p.is_bot) == 3
        assert state.phase in (GamePhase.TRUMP_SELECT, GamePhase.PLAYING)

    def test_bot_picks_trump_automatically(self):
        """If all players are bots, phase should advance past TRUMP_SELECT."""
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.fill_with_bots("R1", bot_class=RandomBot)
        state = mgr.start_game("R1")
        # Bot should have already chosen trump
        assert state.phase == GamePhase.PLAYING

    def test_human_trump_player_stays_in_trump_select(self):
        """If human must pick trump, phase stays at TRUMP_SELECT."""
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        # human is at seat 0 so they pick trump in round 0
        mgr.join_room("R1", make_player("human1"))
        mgr.fill_with_bots("R1", bot_class=RandomBot)
        # Make sure human1 is at seat 0
        room = mgr.get_room("R1")
        if room.players[0].id == "human1":
            state = mgr.start_game("R1")
            assert state.phase == GamePhase.TRUMP_SELECT
            assert state.trump_player_id == "human1"


# ---------------------------------------------------------------------------
# choose_trump
# ---------------------------------------------------------------------------

class TestChooseTrump:
    def test_human_can_choose_trump(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("human1"))
        mgr.fill_with_bots("R1", bot_class=RandomBot)
        state = mgr.start_game("R1")

        if state.phase == GamePhase.TRUMP_SELECT:
            tp = state.trump_player_id
            state = mgr.choose_trump("R1", tp, TrumpMode.ROSE)
            assert state.trump_mode == TrumpMode.ROSE
            assert state.phase == GamePhase.PLAYING

    def test_wrong_room_raises(self):
        with pytest.raises(KeyError):
            make_manager().choose_trump("NOPE", "p1", TrumpMode.EICHEL)


# ---------------------------------------------------------------------------
# play_card
# ---------------------------------------------------------------------------

class TestPlayCard:
    def test_human_play_card_accepted(self):
        """A human card play should be accepted and state advanced."""
        random.seed(42)
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("human1"))
        mgr.fill_with_bots("R1", bot_class=RandomBot)
        state = mgr.start_game("R1")

        if state.phase == GamePhase.TRUMP_SELECT:
            tp = state.trump_player_id
            if tp == "human1":
                state = mgr.choose_trump("R1", "human1", TrumpMode.EICHEL)

        if state.phase == GamePhase.PLAYING and state.current_player_id == "human1":
            engine = mgr.get_engine("R1")
            legal = engine.variant.get_legal_moves(
                engine.get_state_for("human1"), "human1"
            )
            if legal:
                new_state = mgr.play_card("R1", "human1", legal[0])
                assert new_state is not None

    def test_human_play_does_not_auto_advance_bots(self):
        """RoomManager.play_card should apply only the requested card."""
        random.seed(10)
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("human1"), seat_index=0)
        mgr.fill_with_bots("R1", bot_class=RandomBot)
        state = mgr.start_game("R1")
        if state.phase == GamePhase.TRUMP_SELECT:
            state = mgr.choose_trump("R1", "human1", TrumpMode.EICHEL)

        engine = mgr.get_engine("R1")
        legal = engine.variant.get_legal_moves(
            engine.get_state_for("human1"), "human1"
        )
        state = mgr.play_card("R1", "human1", legal[0])

        assert len(state.current_trick.entries) == 1
        assert state.current_trick.entries[0].player_id == "human1"
        assert mgr.is_bot("R1", state.current_player_id)

    def test_play_one_bot_card_advances_exactly_one_bot(self):
        random.seed(11)
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("human1"), seat_index=0)
        mgr.fill_with_bots("R1", bot_class=RandomBot)
        state = mgr.start_game("R1")
        if state.phase == GamePhase.TRUMP_SELECT:
            state = mgr.choose_trump("R1", "human1", TrumpMode.EICHEL)

        engine = mgr.get_engine("R1")
        legal = engine.variant.get_legal_moves(
            engine.get_state_for("human1"), "human1"
        )
        state = mgr.play_card("R1", "human1", legal[0])
        bot_player = state.current_player_id

        state = mgr.play_one_bot_card("R1")

        assert state is not None
        assert len(state.current_trick.entries) == 2
        assert state.current_trick.entries[1].player_id == bot_player

    def test_play_one_bot_card_returns_none_on_human_turn(self):
        random.seed(12)
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("human1"), seat_index=0)
        mgr.fill_with_bots("R1", bot_class=RandomBot)
        state = mgr.start_game("R1")
        if state.phase == GamePhase.TRUMP_SELECT:
            mgr.choose_trump("R1", "human1", TrumpMode.EICHEL)

        assert mgr.play_one_bot_card("R1") is None

    def test_wrong_room_raises(self):
        with pytest.raises(KeyError):
            make_manager().play_card(
                "NOPE", "p1", Card(suit=Suit.ROSE, rank=Rank.ACE)
            )

    def test_no_engine_raises(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        with pytest.raises(KeyError, match="No active game"):
            mgr.play_card("R1", "p1", Card(suit=Suit.ROSE, rank=Rank.ACE))


# ---------------------------------------------------------------------------
# Full game through room manager
# ---------------------------------------------------------------------------

class TestFullGameThroughManager:
    def _run_all_bot_game(self, seed: int = 0) -> RoomManager:
        """Run a complete game with 4 RandomBots through the RoomManager."""
        random.seed(seed)
        mgr = make_manager()
        mgr.create_room("schieber", room_id="GAME")
        mgr.fill_with_bots("GAME", bot_class=RandomBot)
        state = mgr.start_game("GAME")

        engine = mgr.get_engine("GAME")
        max_rounds = 25
        for _ in range(max_rounds):
            # Trump (if needed — bots auto-pick, but just in case)
            if engine.state.phase == GamePhase.TRUMP_SELECT:
                tp = engine.state.trump_player_id
                bot = mgr.get_bot("GAME", tp)
                if bot:
                    view = engine.get_state_for(tp)
                    engine.choose_trump(tp, bot.choose_trump(view))

            # Play all cards
            while engine.state.phase == GamePhase.PLAYING:
                pid = engine.state.current_player_id
                view = engine.get_state_for(pid)
                legal = engine.variant.get_legal_moves(view, pid)
                engine.play_card(pid, legal[0])

            if engine.state.game_over:
                break

            if engine.state.phase == GamePhase.SCORING:
                engine.start_next_round()
                if engine.state.phase == GamePhase.TRUMP_SELECT:
                    tp = engine.state.trump_player_id
                    bot = mgr.get_bot("GAME", tp)
                    if bot:
                        view = engine.get_state_for(tp)
                        engine.choose_trump(tp, bot.choose_trump(view))

        return mgr

    def test_full_game_completes(self):
        mgr = self._run_all_bot_game()
        engine = mgr.get_engine("GAME")
        assert engine.state.game_over

    def test_full_game_has_winner(self):
        mgr = self._run_all_bot_game()
        engine = mgr.get_engine("GAME")
        assert engine.state.winner in TeamId

    def test_winner_has_1000(self):
        mgr = self._run_all_bot_game()
        engine = mgr.get_engine("GAME")
        winner = engine.state.winner
        assert engine.state.scores[winner].total >= WINNING_SCORE

    def test_multiple_seeds_complete(self):
        for seed in range(3):
            mgr = self._run_all_bot_game(seed=seed)
            engine = mgr.get_engine("GAME")
            assert engine.state.game_over, f"Game did not finish with seed={seed}"

    def test_start_next_round_through_manager(self):
        """start_next_round via manager should redeal and continue."""
        random.seed(5)
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.fill_with_bots("R1", bot_class=RandomBot)
        mgr.start_game("R1")
        engine = mgr.get_engine("R1")

        # Play one full round
        if engine.state.phase == GamePhase.TRUMP_SELECT:
            tp = engine.state.trump_player_id
            bot = mgr.get_bot("R1", tp)
            engine.choose_trump(tp, bot.choose_trump(engine.get_state_for(tp)))

        while engine.state.phase == GamePhase.PLAYING:
            pid = engine.state.current_player_id
            view = engine.get_state_for(pid)
            legal = engine.variant.get_legal_moves(view, pid)
            engine.play_card(pid, legal[0])

        if engine.state.phase == GamePhase.SCORING:
            state = mgr.start_next_round("R1")
            assert state.phase in (GamePhase.TRUMP_SELECT, GamePhase.PLAYING)
            assert engine.state.round_number == 1
