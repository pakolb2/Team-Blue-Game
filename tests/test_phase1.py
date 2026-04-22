"""
tests/test_phase1.py
--------------------
Tests for Phase 1: types.py and constants.py

Run with:  pytest tests/test_phase1.py -v
"""

import pytest
from server.shared.types import (
    Card, Player, Trick, TrickEntry, Room, GameState,
    Suit, Rank, TrumpMode, GamePhase, TeamId, TeamScore, Variant
)
from server.shared.constants import (
    SUITS, RANKS, DECK_SIZE, HAND_SIZE,
    BASE_CARD_POINTS, TRUMP_CARD_POINTS, UNDEUFE_CARD_POINTS,
    NORMAL_RANK_ORDER, TRUMP_RANK_ORDER, UNDEUFE_RANK_ORDER,
    TOTAL_CARD_POINTS, TOTAL_ROUND_POINTS, LAST_TRICK_BONUS,
    MAX_PLAYERS, TRICKS_PER_ROUND, WINNING_SCORE,
    SUIT_TRUMP_MODES, NO_TRUMP_MODES, TRUMP_MODE_TO_SUIT,
    TEAM_A_SEATS, TEAM_B_SEATS,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_deck_size(self):
        assert len(SUITS) * len(RANKS) == DECK_SIZE == 36

    def test_hand_size(self):
        assert DECK_SIZE // MAX_PLAYERS == HAND_SIZE == 9

    def test_tricks_per_round(self):
        assert TRICKS_PER_ROUND == 9

    def test_base_card_points_total(self):
        """One full suit of base points should sum to 30 (10+2+3+4+11)."""
        assert sum(BASE_CARD_POINTS.values()) == 30

    def test_total_card_points(self):
        """4 suits × 30 base points = 120... wait, non-trump Jass uses 152.
        Let's verify the constant matches 4 × sum(BASE_CARD_POINTS)."""
        # Note: TOTAL_CARD_POINTS accounts for both normal and trump scoring.
        # In a standard round with one trump suit, 3 suits score base points
        # and 1 suit scores trump points.
        # The constant 152 = 3×30 + (0+0+0+14+10+20+3+4+11) = 90 + 62 = 152
        trump_suit_total = sum(TRUMP_CARD_POINTS.values())
        normal_suits_total = 3 * sum(BASE_CARD_POINTS.values())
        assert TOTAL_CARD_POINTS == normal_suits_total + trump_suit_total

    def test_total_round_points(self):
        assert TOTAL_ROUND_POINTS == TOTAL_CARD_POINTS + LAST_TRICK_BONUS

    def test_trump_card_points_buur(self):
        """Jack of trump (Buur) must be worth 20."""
        assert TRUMP_CARD_POINTS[Rank.JACK] == 20

    def test_trump_card_points_nell(self):
        """Nine of trump (Nell) must be worth 14."""
        assert TRUMP_CARD_POINTS[Rank.NINE] == 14

    def test_undeufe_six_is_highest_scorer(self):
        """In Undeufe, the 6 scores 11 points."""
        assert UNDEUFE_CARD_POINTS[Rank.SIX] == 11

    def test_trump_rank_order_buur_is_last(self):
        """Jack (Buur) must be highest trump — last in the rank order list."""
        assert TRUMP_RANK_ORDER[-1] == Rank.JACK

    def test_trump_rank_order_nell_is_second(self):
        """Nine (Nell) must be second highest trump."""
        assert TRUMP_RANK_ORDER[-2] == Rank.NINE

    def test_undeufe_rank_order_six_is_highest(self):
        """In Undeufe, 6 must be highest — last in rank order list."""
        assert UNDEUFE_RANK_ORDER[-1] == Rank.SIX

    def test_normal_rank_order_ace_is_highest(self):
        assert NORMAL_RANK_ORDER[-1] == Rank.ACE

    def test_suit_trump_modes_count(self):
        assert len(SUIT_TRUMP_MODES) == 4

    def test_no_trump_modes_count(self):
        assert len(NO_TRUMP_MODES) == 2

    def test_trump_mode_to_suit_mapping(self):
        assert TRUMP_MODE_TO_SUIT[TrumpMode.EICHEL] == Suit.EICHEL
        assert TRUMP_MODE_TO_SUIT[TrumpMode.ROSE] == Suit.ROSE

    def test_team_seats_cover_all_players(self):
        all_seats = sorted(TEAM_A_SEATS + TEAM_B_SEATS)
        assert all_seats == [0, 1, 2, 3]

    def test_team_seats_no_overlap(self):
        assert set(TEAM_A_SEATS).isdisjoint(set(TEAM_B_SEATS))


# ---------------------------------------------------------------------------
# Card model
# ---------------------------------------------------------------------------

class TestCard:
    def test_create_card(self):
        card = Card(suit=Suit.EICHEL, rank=Rank.ACE)
        assert card.suit == Suit.EICHEL
        assert card.rank == Rank.ACE

    def test_card_str(self):
        card = Card(suit=Suit.ROSE, rank=Rank.JACK)
        assert str(card) == "J of Rose"

    def test_card_equality(self):
        a = Card(suit=Suit.SCHELLE, rank=Rank.TEN)
        b = Card(suit=Suit.SCHELLE, rank=Rank.TEN)
        assert a == b

    def test_card_inequality_suit(self):
        a = Card(suit=Suit.EICHEL, rank=Rank.TEN)
        b = Card(suit=Suit.ROSE, rank=Rank.TEN)
        assert a != b

    def test_card_inequality_rank(self):
        a = Card(suit=Suit.EICHEL, rank=Rank.TEN)
        b = Card(suit=Suit.EICHEL, rank=Rank.ACE)
        assert a != b

    def test_card_hashable(self):
        """Cards must be hashable to be used in sets."""
        card = Card(suit=Suit.SCHILTE, rank=Rank.KING)
        s = {card}
        assert card in s

    def test_card_in_set(self):
        cards = {Card(suit=Suit.ROSE, rank=Rank.SIX), Card(suit=Suit.EICHEL, rank=Rank.ACE)}
        assert Card(suit=Suit.ROSE, rank=Rank.SIX) in cards

    def test_card_serialization(self):
        card = Card(suit=Suit.SCHELLE, rank=Rank.NINE)
        data = card.model_dump()
        assert data == {"suit": "Schelle", "rank": "9"}

    def test_card_immutable(self):
        """Frozen model — mutation must raise."""
        card = Card(suit=Suit.EICHEL, rank=Rank.ACE)
        with pytest.raises(Exception):
            card.suit = Suit.ROSE


# ---------------------------------------------------------------------------
# Player model
# ---------------------------------------------------------------------------

class TestPlayer:
    def test_create_player(self):
        p = Player(id="p1", name="Alice")
        assert p.id == "p1"
        assert p.name == "Alice"
        assert p.hand == []
        assert p.is_bot is False
        assert p.connected is True

    def test_player_with_hand(self):
        cards = [Card(suit=Suit.EICHEL, rank=Rank.ACE), Card(suit=Suit.ROSE, rank=Rank.SIX)]
        p = Player(id="p2", name="Bob", hand=cards)
        assert len(p.hand) == 2

    def test_bot_player(self):
        bot = Player(id="bot1", name="Bot", is_bot=True)
        assert bot.is_bot is True

    def test_player_serialization(self):
        p = Player(id="p1", name="Alice", team=TeamId.TEAM_A)
        data = p.model_dump()
        assert data["id"] == "p1"
        assert data["team"] == "team_a"


# ---------------------------------------------------------------------------
# Trick model
# ---------------------------------------------------------------------------

class TestTrick:
    def _make_entry(self, player_id: str, suit: Suit, rank: Rank) -> TrickEntry:
        return TrickEntry(player_id=player_id, card=Card(suit=suit, rank=rank))

    def test_empty_trick_not_complete(self):
        trick = Trick()
        assert not trick.is_complete

    def test_trick_complete_at_four_entries(self):
        trick = Trick(entries=[
            self._make_entry("p1", Suit.EICHEL, Rank.ACE),
            self._make_entry("p2", Suit.EICHEL, Rank.KING),
            self._make_entry("p3", Suit.ROSE, Rank.SIX),
            self._make_entry("p4", Suit.SCHELLE, Rank.TEN),
        ])
        assert trick.is_complete

    def test_trick_cards_property(self):
        trick = Trick(entries=[
            self._make_entry("p1", Suit.ROSE, Rank.JACK),
        ])
        assert len(trick.cards) == 1
        assert trick.cards[0] == Card(suit=Suit.ROSE, rank=Rank.JACK)

    def test_trick_player_ids_property(self):
        trick = Trick(entries=[
            self._make_entry("p1", Suit.EICHEL, Rank.SIX),
            self._make_entry("p2", Suit.EICHEL, Rank.SEVEN),
        ])
        assert trick.player_ids == ["p1", "p2"]


# ---------------------------------------------------------------------------
# Room model
# ---------------------------------------------------------------------------

class TestRoom:
    def test_create_room(self):
        room = Room(id="room1")
        assert room.id == "room1"
        assert room.players == []
        assert not room.is_full
        assert not room.is_active

    def test_room_full(self):
        players = [Player(id=f"p{i}", name=f"Player {i}") for i in range(4)]
        room = Room(id="room1", players=players)
        assert room.is_full

    def test_room_player_ids(self):
        players = [Player(id="a", name="A"), Player(id="b", name="B")]
        room = Room(id="r", players=players)
        assert room.player_ids == ["a", "b"]


# ---------------------------------------------------------------------------
# GameState model
# ---------------------------------------------------------------------------

class TestGameState:
    def _make_state(self) -> GameState:
        players = [
            Player(id="p1", name="Alice", team=TeamId.TEAM_A),
            Player(id="p2", name="Bob",   team=TeamId.TEAM_B),
            Player(id="p3", name="Carol", team=TeamId.TEAM_A),
            Player(id="p4", name="Dave",  team=TeamId.TEAM_B),
        ]
        return GameState(room_id="room1", players=players)

    def test_create_game_state(self):
        state = self._make_state()
        assert state.room_id == "room1"
        assert state.phase == GamePhase.WAITING
        assert state.game_over is False
        assert len(state.players) == 4

    def test_get_player_found(self):
        state = self._make_state()
        p = state.get_player("p2")
        assert p is not None
        assert p.name == "Bob"

    def test_get_player_not_found(self):
        state = self._make_state()
        assert state.get_player("nonexistent") is None

    def test_get_player_team(self):
        state = self._make_state()
        assert state.get_player_team("p1") == TeamId.TEAM_A
        assert state.get_player_team("p2") == TeamId.TEAM_B

    def test_next_player_id(self):
        state = self._make_state()
        assert state.next_player_id("p1") == "p2"
        assert state.next_player_id("p2") == "p3"
        assert state.next_player_id("p4") == "p1"  # wraps around

    def test_next_player_id_invalid(self):
        state = self._make_state()
        assert state.next_player_id("nobody") is None

    def test_public_view_hides_other_hands(self):
        state = self._make_state()
        # Give p1 some cards
        state.players[0].hand = [Card(suit=Suit.EICHEL, rank=Rank.ACE)]
        state.players[1].hand = [Card(suit=Suit.ROSE, rank=Rank.SIX)]

        view = state.public_view("p1")
        # p1 keeps their hand
        assert len(view.players[0].hand) == 1
        # p2's hand is hidden
        assert view.players[1].hand == []

    def test_public_view_does_not_mutate_original(self):
        state = self._make_state()
        state.players[1].hand = [Card(suit=Suit.ROSE, rank=Rank.SIX)]
        _ = state.public_view("p1")
        # Original state must be unchanged
        assert len(state.players[1].hand) == 1

    def test_game_state_serializable(self):
        state = self._make_state()
        data = state.model_dump()
        assert data["room_id"] == "room1"
        assert data["phase"] == "waiting"


# ---------------------------------------------------------------------------
# TeamScore model
# ---------------------------------------------------------------------------

class TestTeamScore:
    def test_add_round(self):
        ts = TeamScore(team=TeamId.TEAM_A)
        ts.add_round(80)
        ts.add_round(77)
        assert ts.total == 157
        assert ts.round_scores == [80, 77]


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------

class TestEnums:
    def test_all_suits_present(self):
        suit_values = {s.value for s in Suit}
        assert suit_values == {"Eichel", "Schilte", "Schelle", "Rose"}

    def test_all_ranks_present(self):
        rank_values = {r.value for r in Rank}
        assert rank_values == {"6", "7", "8", "9", "10", "J", "Q", "K", "A"}

    def test_all_trump_modes_present(self):
        assert len(TrumpMode) == 6

    def test_all_game_phases_present(self):
        phases = {p.value for p in GamePhase}
        assert "waiting" in phases
        assert "playing" in phases
        assert "finished" in phases
