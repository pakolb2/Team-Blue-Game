"""
server/game/variants/coiffeur.py
---------------------------------
Coiffeur — the multi-mode team variant of Jass.

Rules
-----
  Coiffeur is played over multiple rounds. Over the course of a game,
  each player must play every trump mode exactly once:
      Eichel, Schilte, Schelle, Rose, Obenabe, Undeufe  (6 modes × 4 players = 24 rounds)

  On each round, the designated player picks a trump mode they have NOT yet
  played. If they pick a mode they have already played, the points for that
  round are DOUBLED — this is the "coiffeur" (the penalty/bonus).

  When all players have exhausted their mode lists (or in the common 2-player
  team variant: when each team has played all 6), the game ends.
  The team with the higher cumulative score wins.

  Scoring per round:
    - Normal round: same as Schieber scoring (cards + last-trick bonus + match bonus)
    - Coiffeur round (mode already played): points × 2

Implementation notes
--------------------
  We track which modes each player has used in a module-level dict keyed
  by room_id, to avoid changing GameState schema. A production implementation
  would add a `coiffeur_tracker` field to GameState.

  The doubled-points rule is applied in score_game() by checking whether
  the current trump_mode was already played by the trump_player_id.

  Winning condition: the game ends when every mode in COIFFEUR_MODES has
  been played by every player on both teams (i.e., round_number >= 24 for
  a 4-player game where each player plays 6 modes). In practice, teams share
  their tracker so it ends at 12 rounds (6 modes × 2 teams).
  We use the team-based variant: 12 rounds total.
"""

from __future__ import annotations

from server.game.variants.base import BaseVariant
from server.game.variants.schieber import Schieber
from server.shared.types import (
    Card, GameState, Trick, TeamId, TrumpMode,
)
from server.shared.constants import (
    LAST_TRICK_BONUS, MATCH_BONUS, WINNING_SCORE,
)

# All 6 Jass trump modes (each team must play each once)
COIFFEUR_MODES: list[TrumpMode] = list(TrumpMode)

# Total rounds: 2 teams × 6 modes = 12
COIFFEUR_TOTAL_ROUNDS: int = 12

# Module-level tracker: room_id → {team_value: set[TrumpMode]}
_played_modes: dict[str, dict[str, set[TrumpMode]]] = {}


def record_mode_played(room_id: str, team: TeamId, mode: TrumpMode) -> None:
    """Record that a team has played a given trump mode this game."""
    if room_id not in _played_modes:
        _played_modes[room_id] = {TeamId.TEAM_A.value: set(), TeamId.TEAM_B.value: set()}
    _played_modes[room_id][team.value].add(mode)


def is_mode_played(room_id: str, team: TeamId, mode: TrumpMode) -> bool:
    """Return True if the team has already played this mode."""
    return mode in _played_modes.get(room_id, {}).get(team.value, set())


def get_available_modes(room_id: str, team: TeamId) -> list[TrumpMode]:
    """Return modes this team has NOT yet played."""
    played = _played_modes.get(room_id, {}).get(team.value, set())
    return [m for m in COIFFEUR_MODES if m not in played]


def clear_tracker(room_id: str) -> None:
    """Reset the mode tracker for a room (new game)."""
    _played_modes.pop(room_id, None)


class Coiffeur(BaseVariant):
    """
    Coiffeur variant — each team must play every trump mode once.
    Replaying a mode doubles the round's points (coiffeur penalty/bonus).
    """

    def __init__(self) -> None:
        self._schieber = Schieber()

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "coiffeur"

    @property
    def display_name(self) -> str:
        return "Coiffeur"

    # ------------------------------------------------------------------
    # Card ranking & legal moves — identical to Schieber
    # ------------------------------------------------------------------

    def card_rank_value(self, card: Card, state: GameState) -> int:
        return self._schieber.card_rank_value(card, state)

    def get_legal_moves(self, state: GameState, player_id: str) -> list[Card]:
        return self._schieber.get_legal_moves(state, player_id)

    def score_trick(self, trick: Trick, state: GameState) -> int:
        return self._schieber.score_trick(trick, state)

    # ------------------------------------------------------------------
    # Scoring — apply doubling if mode was already played
    # ------------------------------------------------------------------

    def score_game(self, state: GameState) -> dict[TeamId, int]:
        """
        Calculate round scores.

        Steps:
          1. Use Schieber scoring to get base round points.
          2. Determine the team of the trump chooser.
          3. If that team has already played this mode → double their points.
        """
        base_scores: dict[TeamId, int] = self._schieber.score_game(state)

        if state.trump_mode is None or state.trump_player_id is None:
            return base_scores

        # Who chose trump this round?
        trump_team = state.get_player_team(state.trump_player_id)
        if trump_team is None:
            return base_scores

        # Was this mode already played by this team?
        coiffeur = is_mode_played(state.room_id, trump_team, state.trump_mode)

        if coiffeur:
            # Double the trump team's score; opponent score unchanged
            doubled = dict(base_scores)
            doubled[trump_team] = base_scores[trump_team] * 2
            return doubled

        return base_scores

    def is_coiffeur_round(self, state: GameState) -> bool:
        """Return True if the current round triggers the Coiffeur doubling."""
        if state.trump_mode is None or state.trump_player_id is None:
            return False
        trump_team = state.get_player_team(state.trump_player_id)
        if trump_team is None:
            return False
        return is_mode_played(state.room_id, trump_team, state.trump_mode)

    # ------------------------------------------------------------------
    # Game over — after all modes played by both teams (12 rounds)
    # ------------------------------------------------------------------

    def is_game_over(self, state: GameState) -> bool:
        """
        Game ends when both teams have played all 6 modes, or after
        COIFFEUR_TOTAL_ROUNDS rounds as a safety cap.
        """
        if state.round_number >= COIFFEUR_TOTAL_ROUNDS:
            return True

        # Check if both teams have exhausted all modes
        for team in TeamId:
            if get_available_modes(state.room_id, team):
                return False  # team still has modes left
        return True

    def get_available_modes_for_team(
        self,
        room_id: str,
        team: TeamId,
    ) -> list[TrumpMode]:
        """Return modes still available for a team to play."""
        return get_available_modes(room_id, team)

    def on_round_start(self, state: GameState) -> None:
        """
        Called by the room manager at the start of each round (after trump
        is chosen) to record the mode in the tracker.
        """
        if state.trump_mode is None or state.trump_player_id is None:
            return
        trump_team = state.get_player_team(state.trump_player_id)
        if trump_team:
            record_mode_played(state.room_id, trump_team, state.trump_mode)
