"""
tests/test_rules.py
--------------------
Tests for Phase 4: server/game/rules.py

Run with:  pytest tests/test_rules.py -v
"""

import pytest

from server.shared.types import (
    Card, Player, Trick, TrickEntry, GameState, Room,
    Suit, Rank, TrumpMode, GamePhase, TeamId,
)
from server.game.variants.schieber import Schieber
from server.game.rules import (
    get_legal_moves, is_legal, validate_play,
    is_players_turn, next_trump_player,
    can_game_start, validate_game_start,
    assign_teams, get_team_players, get_partner_id,
    next_player_after_trick,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(pid: str, hand: list[Card] | None = None, connected: bool = True) -> Player:
    return Player(id=pid, name=pid.capitalize(), hand=hand or [], connected=connected)


def make_state(
    phase: GamePhase = GamePhase.PLAYING,
    current_player: str = "p1",
    trump_mode: TrumpMode = TrumpMode.EICHEL,
    trick_entries: list[TrickEntry] | None = None,
    hands: dict[str, list[Card]] | None = None,
) -> GameState:
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
        room_id="r1",
        players=players,
        phase=phase,
        trump_mode=trump_mode,
        current_trick=trick,
        current_player_id=current_player,
    )


def c(suit: Suit, rank: Rank) -> Card:
    return Card(suit=suit, rank=rank)


def entry(pid: str, suit: Suit, rank: Rank) -> TrickEntry:
    return TrickEntry(player_id=pid, card=c(suit, rank))


# ---------------------------------------------------------------------------
# get_legal_moves
# ---------------------------------------------------------------------------

class TestGetLegalMoves:
    def setup_method(self):
        self.v = Schieber()

    def test_returns_empty_wrong_phase(self):
        state = make_state(phase=GamePhase.WAITING,
                           hands={"p1": [c(Suit.ROSE, Rank.ACE)]})
        assert get_legal_moves(state, "p1", self.v) == []

    def test_returns_empty_wrong_turn(self):
        state = make_state(current_player="p2",
                           hands={"p1": [c(Suit.ROSE, Rank.ACE)]})
        assert get_legal_moves(state, "p1", self.v) == []

    def test_returns_empty_no_hand(self):
        state = make_state(current_player="p1", hands={"p1": []})
        assert get_legal_moves(state, "p1", self.v) == []

    def test_returns_empty_unknown_player(self):
        state = make_state()
        assert get_legal_moves(state, "nobody", self.v) == []

    def test_delegates_to_variant_on_lead(self):
        hand = [c(Suit.ROSE, Rank.ACE), c(Suit.EICHEL, Rank.TEN)]
        state = make_state(hands={"p1": hand})
        legal = get_legal_moves(state, "p1", self.v)
        assert set(legal) == set(hand)

    def test_delegates_follow_suit_rule(self):
        hand = [c(Suit.ROSE, Rank.ACE), c(Suit.SCHELLE, Rank.TEN)]
        trick = [entry("p2", Suit.ROSE, Rank.SIX)]
        state = make_state(hands={"p1": hand}, trick_entries=trick)
        legal = get_legal_moves(state, "p1", self.v)
        assert legal == [c(Suit.ROSE, Rank.ACE)]


# ---------------------------------------------------------------------------
# is_legal
# ---------------------------------------------------------------------------

class TestIsLegal:
    def setup_method(self):
        self.v = Schieber()

    def test_legal_card_returns_true(self):
        hand = [c(Suit.ROSE, Rank.ACE)]
        state = make_state(hands={"p1": hand})
        assert is_legal(state, "p1", c(Suit.ROSE, Rank.ACE), self.v)

    def test_illegal_card_returns_false(self):
        hand = [c(Suit.ROSE, Rank.ACE), c(Suit.SCHELLE, Rank.TEN)]
        trick = [entry("p2", Suit.ROSE, Rank.SIX)]
        state = make_state(hands={"p1": hand}, trick_entries=trick)
        # Must follow Rose — Schelle Ten is illegal
        assert not is_legal(state, "p1", c(Suit.SCHELLE, Rank.TEN), self.v)

    def test_card_not_in_hand_returns_false(self):
        hand = [c(Suit.ROSE, Rank.ACE)]
        state = make_state(hands={"p1": hand})
        assert not is_legal(state, "p1", c(Suit.EICHEL, Rank.KING), self.v)


# ---------------------------------------------------------------------------
# validate_play
# ---------------------------------------------------------------------------

class TestValidatePlay:
    def setup_method(self):
        self.v = Schieber()

    def test_valid_play_raises_nothing(self):
        hand = [c(Suit.ROSE, Rank.ACE)]
        state = make_state(hands={"p1": hand})
        validate_play(state, "p1", c(Suit.ROSE, Rank.ACE), self.v)  # no error

    def test_raises_wrong_phase(self):
        state = make_state(phase=GamePhase.TRUMP_SELECT,
                           hands={"p1": [c(Suit.ROSE, Rank.ACE)]})
        with pytest.raises(ValueError, match="phase"):
            validate_play(state, "p1", c(Suit.ROSE, Rank.ACE), self.v)

    def test_raises_not_players_turn(self):
        state = make_state(current_player="p2",
                           hands={"p1": [c(Suit.ROSE, Rank.ACE)]})
        with pytest.raises(ValueError, match="turn"):
            validate_play(state, "p1", c(Suit.ROSE, Rank.ACE), self.v)

    def test_raises_player_not_found(self):
        # Unknown player passes the turn check only if set as current player
        state = make_state(current_player="ghost")
        with pytest.raises(ValueError, match="not found"):
            validate_play(state, "ghost", c(Suit.ROSE, Rank.ACE), self.v)

    def test_raises_card_not_in_hand(self):
        hand = [c(Suit.ROSE, Rank.ACE)]
        state = make_state(hands={"p1": hand})
        with pytest.raises(ValueError, match="not in"):
            validate_play(state, "p1", c(Suit.EICHEL, Rank.KING), self.v)

    def test_raises_illegal_card(self):
        hand = [c(Suit.ROSE, Rank.ACE), c(Suit.SCHELLE, Rank.TEN)]
        trick = [entry("p2", Suit.ROSE, Rank.SIX)]
        state = make_state(hands={"p1": hand}, trick_entries=trick)
        with pytest.raises(ValueError, match="not a legal play"):
            validate_play(state, "p1", c(Suit.SCHELLE, Rank.TEN), self.v)

    def test_error_message_includes_legal_moves(self):
        hand = [c(Suit.ROSE, Rank.ACE), c(Suit.SCHELLE, Rank.TEN)]
        trick = [entry("p2", Suit.ROSE, Rank.SIX)]
        state = make_state(hands={"p1": hand}, trick_entries=trick)
        with pytest.raises(ValueError, match="Legal moves"):
            validate_play(state, "p1", c(Suit.SCHELLE, Rank.TEN), self.v)


# ---------------------------------------------------------------------------
# Turn helpers
# ---------------------------------------------------------------------------

class TestTurnHelpers:
    def test_is_players_turn_correct(self):
        state = make_state(current_player="p1")
        assert is_players_turn(state, "p1")

    def test_is_players_turn_wrong(self):
        state = make_state(current_player="p2")
        assert not is_players_turn(state, "p1")

    def test_next_player_after_trick_returns_winner(self):
        state = make_state()
        assert next_player_after_trick(state, "p3") == "p3"

    def test_next_trump_player_round_0(self):
        state = make_state()
        # round_number defaults to 0 — seat 0 = p1
        assert next_trump_player(state) == "p1"

    def test_next_trump_player_round_1(self):
        state = make_state()
        state = state.model_copy(update={"round_number": 1})
        assert next_trump_player(state) == "p2"

    def test_next_trump_player_wraps(self):
        state = make_state()
        state = state.model_copy(update={"round_number": 4})
        assert next_trump_player(state) == "p1"   # 4 % 4 = 0

    def test_next_trump_player_empty_room(self):
        state = GameState(room_id="r", players=[], phase=GamePhase.WAITING)
        assert next_trump_player(state) is None


# ---------------------------------------------------------------------------
# Room / game start
# ---------------------------------------------------------------------------

class TestCanGameStart:
    def _make_room(self, n: int = 4, connected: list[bool] | None = None) -> Room:
        if connected is None:
            connected = [True] * n
        players = [
            Player(id=f"p{i}", name=f"P{i}", connected=connected[i])
            for i in range(n)
        ]
        return Room(id="r", players=players)

    def test_four_connected_players_can_start(self):
        assert can_game_start(self._make_room(4))

    def test_three_players_cannot_start(self):
        assert not can_game_start(self._make_room(3))

    def test_disconnected_player_blocks_start(self):
        assert not can_game_start(self._make_room(4, [True, True, True, False]))

    def test_validate_game_start_ok(self):
        room = self._make_room(4)
        validate_game_start(room)  # no error

    def test_validate_game_start_too_few(self):
        room = self._make_room(3)
        with pytest.raises(ValueError, match="Need 4"):
            validate_game_start(room)

    def test_validate_game_start_disconnected(self):
        room = self._make_room(4, [True, False, True, True])
        with pytest.raises(ValueError, match="disconnected"):
            validate_game_start(room)

    def test_validate_game_start_already_active(self):
        room = self._make_room(4)
        room = room.model_copy(update={"is_active": True})
        with pytest.raises(ValueError, match="already in progress"):
            validate_game_start(room)


# ---------------------------------------------------------------------------
# Team assignment
# ---------------------------------------------------------------------------

class TestAssignTeams:
    def _four_players(self) -> list[Player]:
        return [Player(id=f"p{i}", name=f"P{i}") for i in range(4)]

    def test_seats_0_and_2_are_team_a(self):
        players = assign_teams(self._four_players())
        assert players[0].team == TeamId.TEAM_A
        assert players[2].team == TeamId.TEAM_A

    def test_seats_1_and_3_are_team_b(self):
        players = assign_teams(self._four_players())
        assert players[1].team == TeamId.TEAM_B
        assert players[3].team == TeamId.TEAM_B

    def test_does_not_mutate_originals(self):
        originals = self._four_players()
        assign_teams(originals)
        for p in originals:
            assert p.team is None

    def test_raises_wrong_count(self):
        with pytest.raises(ValueError, match="4 players"):
            assign_teams(self._four_players()[:3])

    def test_all_players_have_teams(self):
        players = assign_teams(self._four_players())
        assert all(p.team is not None for p in players)


# ---------------------------------------------------------------------------
# Team queries
# ---------------------------------------------------------------------------

class TestTeamQueries:
    def _state(self) -> GameState:
        return make_state()

    def test_get_team_players_team_a(self):
        state = self._state()
        team_a = get_team_players(state, TeamId.TEAM_A)
        assert {p.id for p in team_a} == {"p1", "p3"}

    def test_get_team_players_team_b(self):
        state = self._state()
        team_b = get_team_players(state, TeamId.TEAM_B)
        assert {p.id for p in team_b} == {"p2", "p4"}

    def test_get_partner_id_p1(self):
        state = self._state()
        assert get_partner_id(state, "p1") == "p3"

    def test_get_partner_id_p2(self):
        state = self._state()
        assert get_partner_id(state, "p2") == "p4"

    def test_get_partner_id_p3(self):
        state = self._state()
        assert get_partner_id(state, "p3") == "p1"

    def test_get_partner_id_unknown(self):
        state = self._state()
        assert get_partner_id(state, "nobody") is None
