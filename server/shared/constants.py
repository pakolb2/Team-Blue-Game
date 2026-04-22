"""
server/shared/constants.py
--------------------------
All fixed game constants for the Jass implementation.
Import from here everywhere — never hardcode magic numbers or strings.

Sections:
  - Deck composition
  - Card point values (base, trump, special)
  - Game rules
  - Team assignment
"""

from server.shared.types import Suit, Rank, TrumpMode

# ---------------------------------------------------------------------------
# Deck composition
# ---------------------------------------------------------------------------

# All 4 suits in the Swiss Jass deck
SUITS: list[Suit] = [Suit.EICHEL, Suit.SCHILTE, Suit.SCHELLE, Suit.ROSE]

# All 9 ranks (Swiss Jass uses 6–A, no 2–5)
RANKS: list[Rank] = [
    Rank.SIX,
    Rank.SEVEN,
    Rank.EIGHT,
    Rank.NINE,
    Rank.TEN,
    Rank.JACK,
    Rank.QUEEN,
    Rank.KING,
    Rank.ACE,
]

# Total cards in a Jass deck
DECK_SIZE: int = 36  # 9 ranks × 4 suits

# Cards per player in a 4-player game
HAND_SIZE: int = 9

# ---------------------------------------------------------------------------
# Card point values — normal (non-trump) cards
# ---------------------------------------------------------------------------
# In a normal suit (not trump), cards score these points.
# 6, 7, 8 are worth 0. Only 10, J, Q, K, A score.

BASE_CARD_POINTS: dict[Rank, int] = {
    Rank.SIX:   0,
    Rank.SEVEN: 0,
    Rank.EIGHT: 0,
    Rank.NINE:  0,
    Rank.TEN:   10,
    Rank.JACK:  2,
    Rank.QUEEN: 3,
    Rank.KING:  4,
    Rank.ACE:   11,
}

# ---------------------------------------------------------------------------
# Card point values — trump suit cards
# ---------------------------------------------------------------------------
# When a suit is trump, JACK (Buur) scores 20 and NINE (Nell) scores 14.
# All other trump cards keep their base point values.

TRUMP_CARD_POINTS: dict[Rank, int] = {
    Rank.SIX:   0,
    Rank.SEVEN: 0,
    Rank.EIGHT: 0,
    Rank.NINE:  14,  # Nell — second most valuable card in the game
    Rank.TEN:   10,
    Rank.JACK:  20,  # Buur — most valuable card in the game
    Rank.QUEEN: 3,
    Rank.KING:  4,
    Rank.ACE:   11,
}

# ---------------------------------------------------------------------------
# Card point values — Obenabe mode (no trump, Aces highest)
# ---------------------------------------------------------------------------
# Same as base points — normal card values apply, no special trump bonuses.

OBENABE_CARD_POINTS: dict[Rank, int] = BASE_CARD_POINTS.copy()

# ---------------------------------------------------------------------------
# Card point values — Undeufe mode (no trump, 6s highest)
# ---------------------------------------------------------------------------
# In Undeufe the 6 is the most powerful card and scores 11,
# the 8 scores 8, all others keep their normal values.

UNDEUFE_CARD_POINTS: dict[Rank, int] = {
    Rank.SIX:   11,  # Most powerful in Undeufe
    Rank.SEVEN: 0,
    Rank.EIGHT: 8,   # Special scoring in Undeufe
    Rank.NINE:  0,
    Rank.TEN:   10,
    Rank.JACK:  2,
    Rank.QUEEN: 3,
    Rank.KING:  4,
    Rank.ACE:   11,
}

# ---------------------------------------------------------------------------
# Card rank order — used to determine who wins a trick
# ---------------------------------------------------------------------------
# Higher index = beats lower index cards.
# These are the DEFAULT rank orders; trump cards use a different order (see below).

# Normal suit rank order (6 lowest → Ace highest)
NORMAL_RANK_ORDER: list[Rank] = [
    Rank.SIX,
    Rank.SEVEN,
    Rank.EIGHT,
    Rank.NINE,
    Rank.TEN,
    Rank.JACK,
    Rank.QUEEN,
    Rank.KING,
    Rank.ACE,
]

# Trump suit rank order — Buur (J) is highest, Nell (9) is second
TRUMP_RANK_ORDER: list[Rank] = [
    Rank.SIX,
    Rank.SEVEN,
    Rank.EIGHT,
    Rank.TEN,
    Rank.QUEEN,
    Rank.KING,
    Rank.ACE,
    Rank.NINE,   # Nell — 2nd highest trump
    Rank.JACK,   # Buur — highest trump
]

# Obenabe rank order (Ace highest, no special cards)
OBENABE_RANK_ORDER: list[Rank] = NORMAL_RANK_ORDER.copy()

# Undeufe rank order (6 highest, order reversed)
UNDEUFE_RANK_ORDER: list[Rank] = list(reversed(NORMAL_RANK_ORDER))

# ---------------------------------------------------------------------------
# Scoring totals — useful for validation
# ---------------------------------------------------------------------------

# Total points available per round from card values alone
# (Verified: sum of BASE_CARD_POINTS × 4 suits = 152)
TOTAL_CARD_POINTS: int = 152

# Bonus points for winning the last trick
LAST_TRICK_BONUS: int = 5

# Total points available in a full round (card points + last trick bonus)
TOTAL_ROUND_POINTS: int = TOTAL_CARD_POINTS + LAST_TRICK_BONUS  # 157

# Bonus for taking all 9 tricks ("Match")
MATCH_BONUS: int = 100

# ---------------------------------------------------------------------------
# Game rules
# ---------------------------------------------------------------------------

MAX_PLAYERS: int = 4
MIN_PLAYERS: int = 4      # Jass requires exactly 4 players
TRICKS_PER_ROUND: int = 9 # 36 cards ÷ 4 players = 9 tricks

# First team to reach this score wins (Schieber)
WINNING_SCORE: int = 1000

# ---------------------------------------------------------------------------
# Team assignment — seats 0 & 2 vs seats 1 & 3
# ---------------------------------------------------------------------------
# In a 4-player game, players are seated 0–3.
# Players in seats 0 and 2 form Team A; seats 1 and 3 form Team B.

TEAM_A_SEATS: list[int] = [0, 2]
TEAM_B_SEATS: list[int] = [1, 3]

# ---------------------------------------------------------------------------
# Trump modes that have a real trump suit (vs. Obenabe/Undeufe)
# ---------------------------------------------------------------------------

SUIT_TRUMP_MODES: list[TrumpMode] = [
    TrumpMode.EICHEL,
    TrumpMode.SCHILTE,
    TrumpMode.SCHELLE,
    TrumpMode.ROSE,
]

NO_TRUMP_MODES: list[TrumpMode] = [
    TrumpMode.OBENABE,
    TrumpMode.UNDEUFE,
]

# Map from TrumpMode to Suit (only valid for SUIT_TRUMP_MODES)
TRUMP_MODE_TO_SUIT: dict[TrumpMode, "Suit"] = {
    TrumpMode.EICHEL:  Suit.EICHEL,
    TrumpMode.SCHILTE: Suit.SCHILTE,
    TrumpMode.SCHELLE: Suit.SCHELLE,
    TrumpMode.ROSE:    Suit.ROSE,
}
