"""
tests/test_websocket.py
------------------------
Integration tests for Phase 8: events.py, handlers.py, and main.py.

Uses FastAPI's TestClient with WebSocket support via httpx + anyio.
Tests exercise the full stack from WebSocket message → RoomManager →
GameEngine → serialised state response.

Run with:  pytest tests/test_websocket.py -v

Dependencies:
    pip install httpx pytest-anyio
"""

from __future__ import annotations

import json
import random
import pytest

from fastapi.testclient import TestClient

from server.main import app
from server.shared.events import Event
from server.shared.types import TrumpMode, Suit, Rank, GamePhase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client() -> TestClient:
    """Fresh TestClient with a clean app state for each test."""
    # Re-import to get a clean RoomManager per test
    from server import main as main_module
    from server.rooms.room_manager import RoomManager
    from server.sockets.handlers import ConnectionManager
    main_module.room_manager = RoomManager()
    main_module.connection_manager = ConnectionManager()
    return TestClient(app)


def ws_send(ws, msg: dict) -> None:
    ws.send_text(json.dumps(msg))


def ws_recv(ws) -> dict:
    return json.loads(ws.receive_text())


def ws_recv_until(ws, event_type: str, max_messages: int = 10) -> dict | None:
    """Receive messages until one of `event_type` is found."""
    for _ in range(max_messages):
        msg = ws_recv(ws)
        if msg.get("type") == event_type:
            return msg
    return None


# ---------------------------------------------------------------------------
# events.py — serialisation
# ---------------------------------------------------------------------------

class TestEventsSerialization:
    def test_error_msg_structure(self):
        from server.shared.events import error_msg
        msg = error_msg("Something went wrong", code="test_error")
        assert msg["type"] == Event.ERROR
        assert msg["message"] == "Something went wrong"
        assert msg["code"] == "test_error"

    def test_rooms_list_msg_structure(self):
        from server.shared.events import rooms_list_msg
        from server.shared.types import Room
        rooms = [Room(id="R1", variant_name="schieber")]
        msg = rooms_list_msg(rooms)
        assert msg["type"] == Event.ROOMS_LIST
        assert len(msg["rooms"]) == 1
        assert msg["rooms"][0]["id"] == "R1"

    def test_room_updated_msg_structure(self):
        from server.shared.events import room_updated_msg
        from server.shared.types import Room, Player
        room = Room(
            id="R1",
            players=[Player(id="p1", name="Alice")],
            variant_name="schieber",
        )
        msg = room_updated_msg(room)
        assert msg["type"] == Event.ROOM_UPDATED
        assert msg["room"]["id"] == "R1"
        assert len(msg["room"]["players"]) == 1

    def test_parse_inbound_join_room(self):
        from server.shared.events import parse_inbound, JoinRoomMessage
        data = {
            "type": Event.JOIN_ROOM,
            "room_id": "R1",
            "player_id": "p1",
            "player_name": "Alice",
        }
        msg = parse_inbound(data)
        assert isinstance(msg, JoinRoomMessage)
        assert msg.room_id == "R1"

    def test_parse_inbound_play_card(self):
        from server.shared.events import parse_inbound, PlayCardMessage
        data = {
            "type": Event.PLAY_CARD,
            "room_id": "R1",
            "player_id": "p1",
            "card_suit": "Rose",
            "card_rank": "A",
        }
        msg = parse_inbound(data)
        assert isinstance(msg, PlayCardMessage)

    def test_parse_inbound_unknown_returns_none(self):
        from server.shared.events import parse_inbound
        assert parse_inbound({"type": "kaboom"}) is None

    def test_state_serialisation_hides_other_hands(self):
        from server.shared.events import _serialise_state
        from server.shared.types import (
            GameState, Player, TeamId, GamePhase, Card, Suit, Rank
        )
        players = [
            Player(id="p1", team=TeamId.TEAM_A,
                   hand=[Card(suit=Suit.ROSE, rank=Rank.ACE)], name="P1"),
            Player(id="p2", team=TeamId.TEAM_B,
                   hand=[Card(suit=Suit.EICHEL, rank=Rank.JACK)], name="P2"),
            Player(id="p3", team=TeamId.TEAM_A, hand=[], name="P3"),
            Player(id="p4", team=TeamId.TEAM_B, hand=[], name="P4"),
        ]
        state = GameState(room_id="r", players=players, phase=GamePhase.PLAYING)
        serialised = _serialise_state(state, "p1")
        p1_data = next(p for p in serialised["players"] if p["id"] == "p1")
        p2_data = next(p for p in serialised["players"] if p["id"] == "p2")
        assert len(p1_data["hand"]) == 1         # p1 sees own hand
        assert len(p2_data["hand"]) == 0         # p2's hand hidden
        assert p2_data["hand_count"] == 1        # but count is visible


# ---------------------------------------------------------------------------
# HTTP API routes
# ---------------------------------------------------------------------------

class TestHTTPRoutes:
    def test_create_room(self):
        client = make_client()
        resp = client.post("/api/rooms")
        assert resp.status_code == 200
        data = resp.json()
        assert "room_id" in data
        assert data["variant"] == "schieber"

    def test_list_rooms_empty(self):
        client = make_client()
        resp = client.get("/api/rooms")
        assert resp.status_code == 200
        assert resp.json()["rooms"] == []

    def test_list_rooms_after_create(self):
        client = make_client()
        client.post("/api/rooms")
        resp = client.get("/api/rooms")
        assert len(resp.json()["rooms"]) == 1

    def test_get_room(self):
        client = make_client()
        room_id = client.post("/api/rooms").json()["room_id"]
        resp = client.get(f"/api/rooms/{room_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == room_id

    def test_get_missing_room_404(self):
        client = make_client()
        resp = client.get("/api/rooms/NOPE")
        assert resp.status_code == 404

    def test_home_page_loads(self):
        client = make_client()
        resp = client.get("/")
        assert resp.status_code == 200

    def test_tutorial_page_loads(self):
        client = make_client()
        resp = client.get("/tutorial")
        assert resp.status_code == 200

    def test_game_page_missing_room_404(self):
        client = make_client()
        resp = client.get("/game/NOPE")
        assert resp.status_code == 404

    def test_game_page_existing_room(self):
        client = make_client()
        room_id = client.post("/api/rooms").json()["room_id"]
        resp = client.get(f"/game/{room_id}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# WebSocket — connection and basic routing
# ---------------------------------------------------------------------------

class TestWebSocketConnection:
    def test_unknown_event_returns_error(self):
        client = make_client()
        with client.websocket_connect("/ws/player1") as ws:
            ws_send(ws, {"type": "totally_unknown"})
            msg = ws_recv(ws)
            assert msg["type"] == Event.ERROR
            assert msg["code"] == "unknown_event"

    def test_invalid_json_returns_error(self):
        client = make_client()
        with client.websocket_connect("/ws/player1") as ws:
            ws.send_text("not json at all {{{")
            msg = ws_recv(ws)
            assert msg["type"] == "error"

    def test_list_rooms_returns_rooms_list(self):
        client = make_client()
        with client.websocket_connect("/ws/player1") as ws:
            ws_send(ws, {"type": Event.LIST_ROOMS})
            msg = ws_recv(ws)
            assert msg["type"] == Event.ROOMS_LIST
            assert "rooms" in msg

    def test_join_missing_room_returns_error(self):
        client = make_client()
        with client.websocket_connect("/ws/player1") as ws:
            ws_send(ws, {
                "type": Event.JOIN_ROOM,
                "room_id": "MISSING",
                "player_id": "player1",
                "player_name": "Alice",
            })
            msg = ws_recv(ws)
            assert msg["type"] == Event.ERROR


# ---------------------------------------------------------------------------
# WebSocket — room lifecycle
# ---------------------------------------------------------------------------

class TestWebSocketRoomLifecycle:
    def test_join_room_broadcasts_room_updated(self):
        client = make_client()
        # Create room via HTTP
        room_id = client.post("/api/rooms").json()["room_id"]

        with client.websocket_connect("/ws/player1") as ws:
            ws_send(ws, {
                "type": Event.JOIN_ROOM,
                "room_id": room_id,
                "player_id": "player1",
                "player_name": "Alice",
            })
            msg = ws_recv(ws)
            assert msg["type"] == Event.ROOM_UPDATED
            assert any(p["id"] == "player1" for p in msg["room"]["players"])

    def test_two_players_join_room(self):
        client = make_client()
        room_id = client.post("/api/rooms").json()["room_id"]

        with client.websocket_connect("/ws/p1") as ws1, \
             client.websocket_connect("/ws/p2") as ws2:

            ws_send(ws1, {
                "type": Event.JOIN_ROOM,
                "room_id": room_id,
                "player_id": "p1",
                "player_name": "Alice",
            })
            ws_recv(ws1)  # room_updated to p1

            ws_send(ws2, {
                "type": Event.JOIN_ROOM,
                "room_id": room_id,
                "player_id": "p2",
                "player_name": "Bob",
            })

            # Both players should receive room_updated
            msg_p1 = ws_recv(ws1)
            msg_p2 = ws_recv(ws2)

            assert msg_p1["type"] == Event.ROOM_UPDATED
            assert msg_p2["type"] == Event.ROOM_UPDATED
            assert len(msg_p2["room"]["players"]) == 2

    def test_leave_room_broadcasts_update(self):
        client = make_client()
        room_id = client.post("/api/rooms").json()["room_id"]

        with client.websocket_connect("/ws/p1") as ws1,              client.websocket_connect("/ws/p2") as ws2:

            # Both join
            ws_send(ws1, {"type": Event.JOIN_ROOM, "room_id": room_id,
                          "player_id": "p1", "player_name": "Alice"})
            ws_recv(ws1)  # room_updated to p1

            ws_send(ws2, {"type": Event.JOIN_ROOM, "room_id": room_id,
                          "player_id": "p2", "player_name": "Bob"})
            ws_recv(ws1)  # p1 notified p2 joined
            ws_recv(ws2)  # p2 notified of join

            # p1 leaves — p2 should be notified
            ws_send(ws1, {"type": Event.LEAVE_ROOM, "room_id": room_id,
                          "player_id": "p1"})
            msg = ws_recv(ws2)   # p2 receives the update
            assert msg["type"] == Event.ROOM_UPDATED


# ---------------------------------------------------------------------------
# WebSocket — game flow
# ---------------------------------------------------------------------------

class TestWebSocketGameFlow:
    def _setup_full_room(self, client: TestClient) -> tuple[str, str]:
        """Create a room, join one human, fill with bots. Returns (room_id, player_id)."""
        from server import main as main_module
        room = main_module.room_manager.create_room("schieber")
        room_id = room.id
        player_id = "human1"
        from server.shared.types import Player
        main_module.room_manager.join_room(room_id, Player(id=player_id, name="Alice"))
        main_module.room_manager.fill_with_bots(room_id)
        return room_id, player_id

    def test_start_game_sends_game_started(self):
        random.seed(0)
        client = make_client()
        room_id, player_id = self._setup_full_room(client)

        with client.websocket_connect(f"/ws/{player_id}") as ws:
            ws_send(ws, {
                "type": Event.START_GAME,
                "room_id": room_id,
                "player_id": player_id,
            })
            msg = ws_recv(ws)
            assert msg["type"] == Event.GAME_STARTED
            assert "state" in msg

    def test_game_started_has_hand(self):
        random.seed(1)
        client = make_client()
        room_id, player_id = self._setup_full_room(client)

        with client.websocket_connect(f"/ws/{player_id}") as ws:
            ws_send(ws, {
                "type": Event.START_GAME,
                "room_id": room_id,
                "player_id": player_id,
            })
            msg = ws_recv(ws)
            state = msg["state"]
            # Find our player's data
            my_player = next(
                p for p in state["players"] if p["id"] == player_id
            )
            assert my_player["hand_count"] == 9

    def test_choose_trump_advances_to_playing(self):
        random.seed(2)
        client = make_client()
        room_id, player_id = self._setup_full_room(client)

        with client.websocket_connect(f"/ws/{player_id}") as ws:
            ws_send(ws, {
                "type": Event.START_GAME,
                "room_id": room_id,
                "player_id": player_id,
            })
            msg = ws_recv(ws)
            state = msg["state"]

            # Only test this if human must pick trump
            if state["phase"] == GamePhase.TRUMP_SELECT.value and \
               state["trump_player_id"] == player_id:

                ws_send(ws, {
                    "type": Event.CHOOSE_TRUMP,
                    "room_id": room_id,
                    "player_id": player_id,
                    "trump_mode": TrumpMode.EICHEL.value,
                })
                msg = ws_recv(ws)
                assert msg["type"] == Event.STATE_UPDATED
                assert msg["state"]["phase"] == GamePhase.PLAYING.value

    def test_invalid_trump_mode_returns_error(self):
        random.seed(3)
        client = make_client()
        room_id, player_id = self._setup_full_room(client)

        with client.websocket_connect(f"/ws/{player_id}") as ws:
            ws_send(ws, {
                "type": Event.START_GAME,
                "room_id": room_id,
                "player_id": player_id,
            })
            ws_recv(ws)  # game_started

            ws_send(ws, {
                "type": Event.CHOOSE_TRUMP,
                "room_id": room_id,
                "player_id": player_id,
                "trump_mode": "InvalidMode",
            })
            msg = ws_recv(ws)
            assert msg["type"] == Event.ERROR

    def test_play_card_when_not_your_turn_returns_error(self):
        random.seed(4)
        client = make_client()
        room_id, player_id = self._setup_full_room(client)

        with client.websocket_connect(f"/ws/{player_id}") as ws:
            ws_send(ws, {
                "type": Event.START_GAME,
                "room_id": room_id,
                "player_id": player_id,
            })
            msg = ws_recv(ws)

            # Ensure we're in PLAYING phase (bots may have picked trump)
            state = msg["state"]
            if state["phase"] != GamePhase.PLAYING.value:
                return  # skip if game not fully started

            # Try to play when it's not our turn
            if state["current_player_id"] != player_id:
                ws_send(ws, {
                    "type": Event.PLAY_CARD,
                    "room_id": room_id,
                    "player_id": player_id,
                    "card_suit": "Rose",
                    "card_rank": "A",
                })
                msg = ws_recv(ws)
                assert msg["type"] == Event.ERROR

    def test_valid_card_play_returns_state_updated(self):
        random.seed(5)
        client = make_client()

        # All-bot room so we can control the game programmatically
        from server import main as main_module
        from server.bots.random_bot import RandomBot
        room = main_module.room_manager.create_room("schieber")
        rid = room.id
        from server.shared.types import Player
        main_module.room_manager.join_room(rid, Player(id="human1", name="Alice"))
        main_module.room_manager.fill_with_bots(rid, bot_class=RandomBot)

        with client.websocket_connect("/ws/human1") as ws:
            ws_send(ws, {
                "type": Event.START_GAME,
                "room_id": rid,
                "player_id": "human1",
            })
            msg = ws_recv(ws)
            state = msg["state"]

            # Get to PLAYING phase
            if state["phase"] == GamePhase.TRUMP_SELECT.value and \
               state["trump_player_id"] == "human1":
                ws_send(ws, {
                    "type": Event.CHOOSE_TRUMP,
                    "room_id": rid,
                    "player_id": "human1",
                    "trump_mode": TrumpMode.EICHEL.value,
                })
                msg = ws_recv(ws)
                state = msg["state"]

            if state["phase"] == GamePhase.PLAYING.value and \
               state["current_player_id"] == "human1":
                # Find a legal card from our hand
                my_player = next(
                    p for p in state["players"] if p["id"] == "human1"
                )
                if my_player["hand"]:
                    card = my_player["hand"][0]
                    ws_send(ws, {
                        "type": Event.PLAY_CARD,
                        "room_id": rid,
                        "player_id": "human1",
                        "card_suit": card["suit"],
                        "card_rank": card["rank"],
                    })
                    msg = ws_recv(ws)
                    assert msg["type"] in (
                        Event.STATE_UPDATED,
                        Event.TRICK_COMPLETE,
                        Event.ROUND_COMPLETE,
                        Event.GAME_OVER,
                    )

    def test_play_card_broadcasts_human_card_before_bot_cards(self, monkeypatch):
        """The first event after a human card must show only that human card."""
        random.seed(6)

        from server.sockets import handlers as handlers_module
        monkeypatch.setattr(handlers_module, "BOT_ACTION_DELAY_SECONDS", 0)
        monkeypatch.setattr(handlers_module, "TRICK_COMPLETE_PAUSE_SECONDS", 0)
        monkeypatch.setattr(handlers_module, "ROUND_START_PAUSE_SECONDS", 0)

        client = make_client()
        from server import main as main_module
        from server.bots.random_bot import RandomBot
        from server.shared.types import Player

        room = main_module.room_manager.create_room("schieber")
        rid = room.id
        main_module.room_manager.join_room(
            rid, Player(id="human1", name="Alice", seat_index=0), seat_index=0
        )
        main_module.room_manager.fill_with_bots(rid, bot_class=RandomBot)

        with client.websocket_connect("/ws/human1") as ws:
            ws_send(ws, {
                "type": Event.START_GAME,
                "room_id": rid,
                "player_id": "human1",
            })
            msg = ws_recv(ws)
            state = msg["state"]
            assert state["phase"] == GamePhase.TRUMP_SELECT.value
            assert state["trump_player_id"] == "human1"

            ws_send(ws, {
                "type": Event.CHOOSE_TRUMP,
                "room_id": rid,
                "player_id": "human1",
                "trump_mode": TrumpMode.EICHEL.value,
            })
            msg = ws_recv(ws)
            state = msg["state"]
            assert state["phase"] == GamePhase.PLAYING.value
            assert state["current_player_id"] == "human1"

            my_player = next(p for p in state["players"] if p["id"] == "human1")
            card = my_player["hand"][0]
            ws_send(ws, {
                "type": Event.PLAY_CARD,
                "room_id": rid,
                "player_id": "human1",
                "card_suit": card["suit"],
                "card_rank": card["rank"],
            })

            msg = ws_recv(ws)
            assert msg["type"] == Event.STATE_UPDATED
            trick_entries = msg["state"]["current_trick"]["entries"]
            assert len(trick_entries) == 1
            assert trick_entries[0]["player_id"] == "human1"

    def test_start_game_missing_room_returns_error(self):
        client = make_client()
        with client.websocket_connect("/ws/player1") as ws:
            ws_send(ws, {
                "type": Event.START_GAME,
                "room_id": "NOPE",
                "player_id": "player1",
            })
            msg = ws_recv(ws)
            assert msg["type"] == Event.ERROR
