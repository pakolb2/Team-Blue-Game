"""
server/game/scoring.py
-----------------------
Scoring helpers used by the GameEngine.

These functions sit between the engine and the variant's scoring logic,
adding cross-variant responsibilities:
  - Applying trick points back onto the Trick object
  - Accumulating round scores into TeamScore objects on GameState
  - Detecting and handling "Match" (one team wins all tricks)
  - Updating season totals across rounds

The variant's score_trick() and score_game() do the raw maths.
This module applies those results to the GameState.

Public API:
    score_completed_trick(trick, state, variant)  → Trick  (with points set)
    apply_round_scores(state, variant)            → GameState  (scores updated)
    get_round_winner(round_scores)                → TeamId | None
    get_game_winner(state)                        → TeamId | None
    round_score_summary(state)                    → dict  (human-readable)
"""

from __future__ import annotations

from server.shared.types import (
    GameState, Trick, TeamId, TeamScore, GamePhase,
)
from server.game.variants.base import BaseVariant
from server.shared.constants import WINNING_SCORE


# ---------------------------------------------------------------------------
# Trick scoring
# ---------------------------------------------------------------------------

def score_completed_trick(
    trick: Trick,
    state: GameState,
    variant: BaseVariant,
) -> Trick:
    """
    Calculate the point value of a completed trick and return a new Trick
    object with `points` populated.

    Does NOT modify game state — the engine applies the returned trick.

    Args:
        trick:   A completed trick (trick.is_complete must be True)
        state:   Current game state (needed for trump mode)
        variant: Active variant (provides scoring rules)

    Returns:
        A copy of the trick with `points` set.

    Raises:
        ValueError: If the trick is not complete.
    """
    if not trick.is_complete:
        raise ValueError(
            f"Cannot score an incomplete trick "
            f"({len(trick.entries)}/4 cards played)."
        )

    points = variant.score_trick(trick, state)
    return trick.model_copy(update={"points": points})


# ---------------------------------------------------------------------------
# Round / game scoring
# ---------------------------------------------------------------------------

def apply_round_scores(
    state: GameState,
    variant: BaseVariant,
) -> GameState:
    """
    Calculate round scores for all teams, add them to the running totals,
    and return an updated GameState.

    Steps:
      1. Ask the variant for the raw round scores (dict[TeamId, int])
      2. Initialise TeamScore entries if this is the first round
      3. Add round scores to the running totals
      4. Check if the game is now over (variant.is_game_over)
      5. Set state.winner if applicable

    Does NOT mutate `state` — returns a new GameState via model_copy.
    """
    round_scores: dict[TeamId, int] = variant.score_game(state)

    # Deep-copy the scores dict so we don't mutate the original
    updated_scores: dict[TeamId, TeamScore] = {}

    for team in TeamId:
        existing = state.scores.get(team)
        if existing is None:
            existing = TeamScore(team=team)

        # model_copy produces a new object — safe to mutate
        updated = existing.model_copy(deep=True)
        round_pts = round_scores.get(team, 0)
        updated.add_round(round_pts)
        updated_scores[team] = updated

    # Build the updated state
    new_state = state.model_copy(update={"scores": updated_scores})

    # Check for game over
    if variant.is_game_over(new_state):
        winner = get_game_winner(new_state)
        new_state = new_state.model_copy(update={
            "game_over": True,
            "winner": winner,
            "phase": GamePhase.FINISHED,
        })

    return new_state


def get_round_winner(round_scores: dict[TeamId, int]) -> TeamId | None:
    """
    Return the team with the higher score in a single round.
    Returns None if the scores are equal (shouldn't happen in standard Jass).
    """
    if not round_scores:
        return None

    sorted_teams = sorted(round_scores.items(), key=lambda x: x[1], reverse=True)
    if sorted_teams[0][1] == sorted_teams[1][1]:
        return None   # tie — very rare
    return sorted_teams[0][0]


def get_game_winner(state: GameState) -> TeamId | None:
    """
    Return the TeamId of the team that has won the overall game,
    or None if no team has reached WINNING_SCORE yet.

    If both teams are at or above WINNING_SCORE (crossed it in the same round),
    the team with the higher total wins.
    """
    if not state.scores:
        return None

    qualifying = {
        team: ts for team, ts in state.scores.items()
        if ts.total >= WINNING_SCORE
    }

    if not qualifying:
        return None

    # Both teams crossed 1000 in the same round — higher total wins
    return max(qualifying.items(), key=lambda x: x[1].total)[0]


# ---------------------------------------------------------------------------
# Summaries (used for WebSocket state_updated / game_over events)
# ---------------------------------------------------------------------------

def round_score_summary(state: GameState) -> dict:
    """
    Return a human-readable summary of scores for the current/last round.
    Used when broadcasting the game_over or round_complete event.

    Returns:
        {
            "team_a": { "round": int, "total": int },
            "team_b": { "round": int, "total": int },
            "round_winner": "team_a" | "team_b" | None,
            "game_winner":  "team_a" | "team_b" | None,
        }
    """
    summary: dict = {}

    for team in TeamId:
        ts = state.scores.get(team)
        last_round = ts.round_scores[-1] if ts and ts.round_scores else 0
        total = ts.total if ts else 0
        summary[team.value] = {"round": last_round, "total": total}

    round_scores_raw = {
        team: (state.scores[team].round_scores[-1]
               if state.scores.get(team) and state.scores[team].round_scores
               else 0)
        for team in TeamId
    }

    summary["round_winner"] = (
        get_round_winner(round_scores_raw).value
        if get_round_winner(round_scores_raw) else None
    )
    summary["game_winner"] = (
        get_game_winner(state).value
        if get_game_winner(state) else None
    )

    return summary


def tricks_per_team(state: GameState) -> dict[TeamId, int]:
    """
    Count how many completed tricks each team has won this round.
    Useful for mid-round display and bot decision-making.
    """
    counts: dict[TeamId, int] = {TeamId.TEAM_A: 0, TeamId.TEAM_B: 0}
    for trick in state.completed_tricks:
        if trick.winner_id:
            team = state.get_player_team(trick.winner_id)
            if team:
                counts[team] += 1
    return counts


def points_per_team(state: GameState) -> dict[TeamId, int]:
    """
    Sum trick points earned so far this round per team.
    Does NOT include the last-trick bonus or match bonus (those are end-of-round).
    Useful for mid-round score display.
    """
    pts: dict[TeamId, int] = {TeamId.TEAM_A: 0, TeamId.TEAM_B: 0}
    for trick in state.completed_tricks:
        if trick.winner_id:
            team = state.get_player_team(trick.winner_id)
            if team:
                pts[team] += trick.points
    return pts
