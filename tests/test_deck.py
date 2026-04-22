from server.game.deck import build_deck, shuffle, deal


def test_deck_has_36_cards():
    assert len(build_deck()) == 36


def test_deal_four_players():
    deck = build_deck()
    hands = deal(deck, 4)
    assert len(hands) == 4
    assert all(len(h) == 9 for h in hands)
