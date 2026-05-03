"""
Tests for explicit lobby seats, targeted bots, and swap requests.
Place this as: tests/test_room_manager_seating.py
"""

import pytest

from server.shared.types import Player, GamePhase
from server.rooms.room_manager import RoomManager
from server.bots.random_bot import RandomBot
from server.bots.rule_based_bot import RuleBasedBot


def make_player(pid: str) -> Player:
    return Player(id=pid, name=pid.capitalize())


def make_manager() -> RoomManager:
    return RoomManager()


class TestExplicitSeats:
    def test_join_assigns_first_free_seat(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")

        room = mgr.join_room("R1", make_player("p1"))
        assert room.players[0].seat_index == 0

        room = mgr.join_room("R1", make_player("p2"))
        seats = {p.id: p.seat_index for p in room.players}
        assert seats == {"p1": 0, "p2": 1}

    def test_join_can_target_specific_empty_seat(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")

        room = mgr.join_room("R1", make_player("p1"), seat_index=2)
        assert room.players[0].seat_index == 2

    def test_join_rejects_occupied_seat(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"), seat_index=1)

        with pytest.raises(ValueError, match="occupied"):
            mgr.join_room("R1", make_player("p2"), seat_index=1)


class TestTargetedBots:
    def test_add_random_bot_to_specific_seat(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")

        room = mgr.add_bot("R1", "random", seat_index=3)
        bot_player = room.players[0]

        assert bot_player.is_bot
        assert bot_player.seat_index == 3
        assert isinstance(mgr.get_bot("R1", bot_player.id), RandomBot)

    def test_add_rule_bot_to_specific_seat(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")

        room = mgr.add_bot("R1", "rule_based", seat_index=2)
        bot_player = room.players[0]

        assert bot_player.is_bot
        assert bot_player.seat_index == 2
        assert isinstance(mgr.get_bot("R1", bot_player.id), RuleBasedBot)

    def test_fill_with_bots_fills_missing_seats(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"), seat_index=2)

        room = mgr.fill_with_bots("R1")
        assert len(room.players) == 4
        assert {p.seat_index for p in room.players} == {0, 1, 2, 3}
        assert sum(1 for p in room.players if p.is_bot) == 3


class TestSeatMovementAndSwaps:
    def test_move_to_empty_seat_is_instant(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"), seat_index=0)

        room = mgr.move_player_to_seat("R1", "p1", 2)
        assert next(p for p in room.players if p.id == "p1").seat_index == 2

    def test_move_to_bot_seat_swaps_instantly(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"), seat_index=0)
        room = mgr.add_bot("R1", "random", seat_index=1)
        bot_id = next(p.id for p in room.players if p.is_bot)

        room = mgr.move_player_to_seat("R1", "p1", 1)
        seats = {p.id: p.seat_index for p in room.players}

        assert seats["p1"] == 1
        assert seats[bot_id] == 0

    def test_move_to_human_seat_requires_request(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"), seat_index=0)
        mgr.join_room("R1", make_player("p2"), seat_index=1)

        with pytest.raises(ValueError, match="Request a swap"):
            mgr.move_player_to_seat("R1", "p1", 1)

    def test_human_swap_request_and_acceptance(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"), seat_index=0)
        mgr.join_room("R1", make_player("p2"), seat_index=1)

        mgr.request_swap("R1", requester_id="p1", target_player_id="p2")
        assert mgr.get_swap_requests("R1") == [
            {"target_player_id": "p2", "requester_player_id": "p1"}
        ]

        room = mgr.accept_swap("R1", accepter_id="p2", requester_id="p1")
        seats = {p.id: p.seat_index for p in room.players}

        assert seats == {"p1": 1, "p2": 0}
        assert mgr.get_swap_requests("R1") == []


class TestStartGameWithSeats:
    def test_start_game_uses_sorted_seat_order(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p2"), seat_index=2)
        mgr.join_room("R1", make_player("p0"), seat_index=0)
        mgr.join_room("R1", make_player("p3"), seat_index=3)
        mgr.join_room("R1", make_player("p1"), seat_index=1)

        state = mgr.start_game("R1")
        assert [p.id for p in state.players] == ["p0", "p1", "p2", "p3"]
        assert state.phase in (GamePhase.TRUMP_SELECT, GamePhase.PLAYING)

    def test_start_game_auto_fills_missing_seats_with_bots(self):
        mgr = make_manager()
        mgr.create_room("schieber", room_id="R1")
        mgr.join_room("R1", make_player("p1"), seat_index=2)

        state = mgr.start_game("R1")
        room = mgr.get_room("R1")

        assert len(room.players) == 4
        assert {p.seat_index for p in room.players} == {0, 1, 2, 3}
        assert sum(1 for p in room.players if p.is_bot) == 3
        assert state.phase in (GamePhase.TRUMP_SELECT, GamePhase.PLAYING)
