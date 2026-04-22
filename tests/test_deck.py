"""
tests/test_deck.py
------------------
Tests for Phase 2: server/game/deck.py

Run with:  pytest tests/test_deck.py -v
"""

import pytest
from collections import Counter

from server.shared.types import Card, Player, Suit, Rank, TeamId
from server.shared.constants import DECK_SIZE, HAND_SIZE, MAX_PLAYERS, SUITS, RANKS
from server.game.deck import build_deck, shuffle, deal, deal_to_players, cards_remaining, remove_card


# ---------------------------------------------------------------------------
# build_deck
# ---------------------------------------------------------------------------

class TestBuildDeck:
    def test_deck_has_36_cards(self):
        assert len(build_deck()) == DECK_SIZE

    def test_deck_has_no_duplicates(self):
        deck = build_deck()
        assert len(set(deck)) == DECK_SIZE

    def test_deck_contains_all_suits(self):
        deck = build_deck()
        suits_in_deck = {card.suit for card in deck}
        assert suits_in_deck == set(SUITS)

    def test_deck_contains_all_ranks(self):
        deck = build_deck()
        ranks_in_deck = {card.rank for card in deck}
        assert ranks_in_deck == set(RANKS)

    def test_deck_has_9_cards_per_suit(self):
        deck = build_deck()
        suit_counts = Counter(card.suit for card in deck)
        for suit in SUITS:
            assert suit_counts[suit] == 9, f"Expected 9 cards for {suit}, got {suit_counts[suit]}"

    def test_deck_has_4_cards_per_rank(self):
        deck = build_deck()
        rank_counts = Counter(card.rank for card in deck)
        for rank in RANKS:
            assert rank_counts[rank] == 4, f"Expected 4 cards for {rank}, got {rank_counts[rank]}"

    def test_deck_is_deterministic(self):
        """build_deck() always returns cards in the same order."""
        assert build_deck() == build_deck()

    def test_deck_contains_specific_cards(self):
        deck = build_deck()
        assert Card(suit=Suit.EICHEL, rank=Rank.ACE) in deck
        assert Card(suit=Suit.ROSE, rank=Rank.SIX) in deck
        assert Card(suit=Suit.SCHELLE, rank=Rank.JACK) in deck


# ---------------------------------------------------------------------------
# shuffle
# ---------------------------------------------------------------------------

class TestShuffle:
    def test_shuffle_preserves_card_count(self):
        deck = build_deck()
        assert len(shuffle(deck)) == DECK_SIZE

    def test_shuffle_preserves_all_cards(self):
        deck = build_deck()
        shuffled = shuffle(deck)
        assert set(shuffled) == set(deck)

    def test_shuffle_does_not_mutate_original(self):
        deck = build_deck()
        original_order = list(deck)
        shuffle(deck)
        assert deck == original_order

    def test_shuffle_changes_order(self):
        """Statistically very unlikely to shuffle into the same order."""
        deck = build_deck()
        results = [shuffle(deck) for _ in range(5)]
        # At least one shuffle should differ from the original
        assert any(r != deck for r in results)

    def test_shuffle_returns_new_list(self):
        deck = build_deck()
        shuffled = shuffle(deck)
        assert shuffled is not deck

    def test_double_shuffle_still_has_36_cards(self):
        deck = build_deck()
        assert len(shuffle(shuffle(deck))) == DECK_SIZE


# ---------------------------------------------------------------------------
# deal
# ---------------------------------------------------------------------------

class TestDeal:
    def test_deal_produces_correct_number_of_hands(self):
        deck = shuffle(build_deck())
        hands = deal(deck, 4)
        assert len(hands) == 4

    def test_deal_gives_9_cards_per_player(self):
        deck = shuffle(build_deck())
        hands = deal(deck, 4)
        for hand in hands:
            assert len(hand) == HAND_SIZE

    def test_deal_covers_all_cards(self):
        """Every card in the deck should appear exactly once across all hands."""
        deck = shuffle(build_deck())
        hands = deal(deck, 4)
        all_dealt = [card for hand in hands for card in hand]
        assert len(all_dealt) == DECK_SIZE
        assert set(all_dealt) == set(deck)

    def test_deal_no_card_appears_twice(self):
        deck = shuffle(build_deck())
        hands = deal(deck, 4)
        all_dealt = [card for hand in hands for card in hand]
        assert len(all_dealt) == len(set(all_dealt))

    def test_deal_is_round_robin(self):
        """Player 0 should get cards 0, 4, 8, ... from the deck."""
        deck = build_deck()  # unshuffled so order is known
        hands = deal(deck, 4)
        expected_p0 = [deck[i] for i in range(0, DECK_SIZE, 4)]
        assert hands[0] == expected_p0

    def test_deal_raises_on_uneven_split(self):
        deck = build_deck()
        with pytest.raises(ValueError):
            deal(deck, 5)   # 36 / 5 is not a whole number

    def test_deal_two_players(self):
        """Should work for 2 players (18 cards each) — useful for testing."""
        deck = build_deck()
        hands = deal(deck, 2)
        assert len(hands) == 2
        assert all(len(h) == 18 for h in hands)


# ---------------------------------------------------------------------------
# deal_to_players
# ---------------------------------------------------------------------------

class TestDealToPlayers:
    def _make_players(self) -> list[Player]:
        return [
            Player(id=f"p{i}", name=f"Player {i}", team=TeamId.TEAM_A if i % 2 == 0 else TeamId.TEAM_B)
            for i in range(4)
        ]

    def test_deal_to_players_gives_each_player_9_cards(self):
        players = self._make_players()
        updated = deal_to_players(players)
        for p in updated:
            assert len(p.hand) == HAND_SIZE

    def test_deal_to_players_does_not_mutate_originals(self):
        players = self._make_players()
        deal_to_players(players)
        for p in players:
            assert p.hand == []

    def test_deal_to_players_returns_new_player_objects(self):
        players = self._make_players()
        updated = deal_to_players(players)
        for orig, upd in zip(players, updated):
            assert orig is not upd

    def test_deal_to_players_preserves_player_metadata(self):
        players = self._make_players()
        updated = deal_to_players(players)
        for orig, upd in zip(players, updated):
            assert upd.id == orig.id
            assert upd.name == orig.name
            assert upd.team == orig.team
            assert upd.is_bot == orig.is_bot

    def test_deal_to_players_all_cards_distributed(self):
        players = self._make_players()
        updated = deal_to_players(players)
        all_cards = [card for p in updated for card in p.hand]
        assert len(all_cards) == DECK_SIZE
        assert len(set(all_cards)) == DECK_SIZE  # no duplicates

    def test_deal_to_players_raises_wrong_count(self):
        players = self._make_players()[:3]  # only 3 players
        with pytest.raises(ValueError, match="4 players"):
            deal_to_players(players)

    def test_deal_to_players_randomness(self):
        """Two deals should (very likely) produce different hands."""
        players = self._make_players()
        deal1 = deal_to_players(players)
        deal2 = deal_to_players(players)
        # Compare first player's hand — astronomically unlikely to match
        assert deal1[0].hand != deal2[0].hand


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def _make_players_with_cards(self) -> list[Player]:
        players = [Player(id=f"p{i}", name=f"P{i}") for i in range(4)]
        return deal_to_players(players)

    def test_cards_remaining_full_hands(self):
        players = self._make_players_with_cards()
        assert cards_remaining(players) == DECK_SIZE

    def test_cards_remaining_after_playing(self):
        players = self._make_players_with_cards()
        # Simulate p0 playing their first card
        updated_hand = players[0].hand[1:]
        players[0] = players[0].model_copy(update={"hand": updated_hand})
        assert cards_remaining(players) == DECK_SIZE - 1

    def test_cards_remaining_empty_hands(self):
        players = [Player(id=f"p{i}", name=f"P{i}") for i in range(4)]
        assert cards_remaining(players) == 0

    def test_remove_card_returns_new_list(self):
        hand = [Card(suit=Suit.EICHEL, rank=Rank.ACE), Card(suit=Suit.ROSE, rank=Rank.SIX)]
        card_to_remove = Card(suit=Suit.EICHEL, rank=Rank.ACE)
        new_hand = remove_card(hand, card_to_remove)
        assert card_to_remove not in new_hand
        assert len(new_hand) == 1

    def test_remove_card_does_not_mutate_original(self):
        hand = [Card(suit=Suit.EICHEL, rank=Rank.ACE), Card(suit=Suit.ROSE, rank=Rank.SIX)]
        original = list(hand)
        remove_card(hand, Card(suit=Suit.EICHEL, rank=Rank.ACE))
        assert hand == original

    def test_remove_card_raises_if_not_in_hand(self):
        hand = [Card(suit=Suit.EICHEL, rank=Rank.ACE)]
        with pytest.raises(ValueError):
            remove_card(hand, Card(suit=Suit.ROSE, rank=Rank.SIX))

    def test_remove_card_removes_only_one_instance(self):
        """If somehow a hand had duplicates, only one should be removed."""
        card = Card(suit=Suit.EICHEL, rank=Rank.ACE)
        hand = [card, card]
        new_hand = remove_card(hand, card)
        assert len(new_hand) == 1
