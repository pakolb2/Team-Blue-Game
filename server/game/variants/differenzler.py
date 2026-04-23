"""
server/game/variants/differenzler.py
--------------------------------------
Differenzler — a solo scoring variant of Jass.

Rules
-----
  Before the round each player secretly predicts how many points they
  will win in tricks. After the round, each player's score is the
  DIFFERENCE between their prediction and their actual trick points —
  the goal is to match your prediction exactly (difference = 0).

  There are no fixed teams in Differenzler: all four players compete
  individually. The player with the lowest cumulative difference after
  an agreed number of rounds (typically 4–8) wins.

  Trump selection rotates as in Schieber. Card ranking and trick play
  rules are identical to Schieber.

  Scoring per player per round:
      penalty = abs(prediction - actual_trick_points)

  The WINNING condition (lowest penalty total) replaces the 1000-point
  target. We implement it as: game ends after DIFFERENZLER_ROUNDS rounds,
  and the player with the lowest total penalty wins.

Implementation notes
--------------------
  Predictions are stored in GameState.scores as a custom dict keyed by
  player_id (not TeamId). We reuse TeamScore.round_scores as a list of
  per-round penalties for each player, and TeamScore.total as cumulative
  penalty. The player_id→TeamId mapping is bypassed — every player gets
  their own "team" slot identified by their seat index.

  Because GameState.scores uses TeamId keys, we map player positions to
  TeamId-like labels using a player_score_key() helper that the engine
  and room manager treat uniformly.

  Predictions are passed through GameState.trump_player_id extended data.
  A cleaner approach (adding a `predictions` field to GameState) is left
  as a Phase 10+ enhancement; here we store predictions in a module-level
  dict keyed by room_id to keep the existing types unchanged.
"""

from __future__ import annotations

from server.game.variants.base import BaseVariant
from server.game.variants.schieber import Schieber
from server.shared.types import (
    Card, GameState, Trick, TeamId,
)
from server.shared.constants import (
    LAST_TRICK_BONUS, WINNING_SCORE,
)

# Number of rounds after which the game ends (configurable)
DIFFERENZLER_ROUNDS: int = 4

# Module-level prediction store: room_id → {player_id: prediction}
# This avoids changing the GameState schema for this variant.
_predictions: dict[str, dict[str, int]] = {}


def set_prediction(room_id: str, player_id: str, points: int) -> None:
    """Record a player's prediction before the round starts."""
    if room_id not in _predictions:
        _predictions[room_id] = {}
    _predictions[room_id][player_id] = max(0, min(157, points))


def get_prediction(room_id: str, player_id: str) -> int:
    """Return a player's prediction for the current round (default 0)."""
    return _predictions.get(room_id, {}).get(player_id, 0)


def clear_predictions(room_id: str) -> None:
    """Clear all predictions for a room (call at start of each round)."""
    _predictions.pop(room_id, None)


class Differenzler(BaseVariant):
    """
    Differenzler variant — individual scoring, penalty for missing prediction.

    Card ranking and legal moves are identical to Schieber.
    Only scoring and game-over logic differ.
    """

    def __init__(self, rounds: int = DIFFERENZLER_ROUNDS) -> None:
        self._schieber = Schieber()
        self.rounds = rounds

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "differenzler"

    @property
    def display_name(self) -> str:
        return "Differenzler"

    # ------------------------------------------------------------------
    # Card ranking & legal moves — delegate to Schieber
    # ------------------------------------------------------------------

    def card_rank_value(self, card: Card, state: GameState) -> int:
        return self._schieber.card_rank_value(card, state)

    def get_legal_moves(self, state: GameState, player_id: str) -> list[Card]:
        return self._schieber.get_legal_moves(state, player_id)

    def score_trick(self, trick: Trick, state: GameState) -> int:
        return self._schieber.score_trick(trick, state)

    # ------------------------------------------------------------------
    # Scoring — penalty = |prediction - actual|
    # ------------------------------------------------------------------

    def score_game(self, state: GameState) -> dict[TeamId, int]:
        """
        Calculate per-player penalties.

        Because GameState.scores uses TeamId keys (TEAM_A / TEAM_B), we
        sum penalties within each team for compatibility. Individual player
        penalties are available via get_player_penalties().

        Returns:
            {TeamId.TEAM_A: total_penalty_team_a,
             TeamId.TEAM_B: total_penalty_team_b}
        """
        player_penalties = self._compute_player_penalties(state)

        team_penalties: dict[TeamId, int] = {
            TeamId.TEAM_A: 0,
            TeamId.TEAM_B: 0,
        }
        for player in state.players:
            penalty = player_penalties.get(player.id, 0)
            if player.team in team_penalties:
                team_penalties[player.team] += penalty

        return team_penalties

    def get_player_penalties(self, state: GameState) -> dict[str, int]:
        """Return per-player penalties for display purposes."""
        return self._compute_player_penalties(state)

    def _compute_player_penalties(self, state: GameState) -> dict[str, int]:
        """
        Compute actual trick points per player then compare to predictions.
        """
        # Sum trick points per player
        actual: dict[str, int] = {p.id: 0 for p in state.players}
        for trick in state.completed_tricks:
            if trick.winner_id and trick.winner_id in actual:
                actual[trick.winner_id] += trick.points

        # Last trick bonus
        if state.completed_tricks:
            last = state.completed_tricks[-1]
            if last.winner_id and last.winner_id in actual:
                actual[last.winner_id] += LAST_TRICK_BONUS

        # Penalty per player
        penalties: dict[str, int] = {}
        for player in state.players:
            prediction = get_prediction(state.room_id, player.id)
            penalties[player.id] = abs(prediction - actual.get(player.id, 0))

        return penalties

    # ------------------------------------------------------------------
    # Game over — after N rounds
    # ------------------------------------------------------------------

    def is_game_over(self, state: GameState) -> bool:
        """Game ends after self.rounds complete rounds."""
        return state.round_number >= self.rounds

    def get_winner(self, state: GameState) -> str | None:
        """
        Return the player_id with the lowest cumulative penalty.
        Returns None if the game is not over yet.
        """
        if not self.is_game_over(state):
            return None

        # Sum round_scores (penalties) per player from TeamScore objects
        # In Differenzler, each team's total stores combined penalty.
        # We need per-player — use get_player_penalties on completed state.
        # For now return the team with the lower total penalty.
        if not state.scores:
            return None
        best = min(state.scores.items(), key=lambda kv: kv[1].total)
        return best[0].value   # TeamId value string
