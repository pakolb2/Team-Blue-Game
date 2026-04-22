"""
server/game/engine.py
----------------------
The authoritative game engine. This is the heart of the server.

The engine owns the GameState and is the only place where state is mutated.
Every player action (choose trump, play card) goes through here.
The engine validates the action, applies it, advances the game, and returns
the new state. Callers (WebSocket handlers, bots) never touch state directly.

Lifecycle of a game:
  1.  Engine created:    GameEngine(players, variant)
  2.  start()            → deals cards, sets phase to TRUMP_SELECT
  3.  choose_trump()     → records trump, sets phase to PLAYING, first player leads
  4.  play_card() ×36    → each card play advances the trick; when the 4th card
                           is played the trick is scored, winner leads next trick
  5.  After 9 tricks:    round is scored, scores updated, check game_over
  6a. If game_over:      phase → FINISHED, winner set
  6b. If not game_over:  start_next_round() — redeal, rotate trump player

Public API:
    GameEngine(players, variant)
    engine.start()                         → GameState
    engine.choose_trump(player_id, mode)   → GameState
    engine.play_card(player_id, card)      → GameState
    engine.get_state_for(player_id)        → GameState   (hands hidden)
    engine.state                           → GameState   (full, server-side only)
"""

from __future__ import annotations

from server.shared.types import (
    Card, GameState, GamePhase, Player, Trick, TrickEntry,
    TeamId, TeamScore, TrumpMode,
)
from server.shared.constants import TRICKS_PER_ROUND
from server.game.variants.base import BaseVariant
from server.game.deck import deal_to_players
from server.game.rules import (
    validate_play, assign_teams, next_trump_player,
    next_player_after_trick,
)
from server.game.scoring import (
    score_completed_trick, apply_round_scores,
)


class GameEngine:
    """
    Authoritative game engine for a single Jass game room.

    One engine instance lives per active room. It holds the full GameState
    (including all players' hands) and exposes a clean action API.

    The engine never sends WebSocket messages — it returns the new GameState
    and lets the socket handler broadcast it.
    """

    def __init__(self, players: list[Player], variant: BaseVariant) -> None:
        """
        Initialise the engine with a list of players and the chosen variant.

        Args:
            players: Exactly 4 Player objects in seat order (seat 0 leads first).
                     Teams are assigned automatically (seats 0&2 = Team A,
                     seats 1&3 = Team B).
            variant: The active game variant (e.g. Schieber instance).

        Raises:
            ValueError: If not exactly 4 players are provided.
        """
        if len(players) != 4:
            raise ValueError(f"GameEngine requires exactly 4 players, got {len(players)}.")

        self.variant = variant

        # Assign teams and build initial state
        seated = assign_teams(players)
        self._state = GameState(
            room_id=seated[0].id + "_game",   # placeholder — caller sets room_id
            players=seated,
            phase=GamePhase.WAITING,
            scores={
                TeamId.TEAM_A: TeamScore(team=TeamId.TEAM_A),
                TeamId.TEAM_B: TeamScore(team=TeamId.TEAM_B),
            },
        )

    @classmethod
    def for_room(
        cls,
        room_id: str,
        players: list[Player],
        variant: BaseVariant,
    ) -> "GameEngine":
        """
        Factory method — creates an engine and sets the correct room_id.
        Preferred over the constructor when room context is available.
        """
        engine = cls(players, variant)
        engine._state = engine._state.model_copy(update={"room_id": room_id})
        return engine

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> GameState:
        """Full game state — server-side only. Never send this to clients."""
        return self._state

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------

    def start(self) -> GameState:
        """
        Deal cards and move to the trump-selection phase.

        - Cards are shuffled and dealt 9 per player.
        - The player whose turn it is to pick trump is determined by
          round_number % 4 (rotates each round).
        - Phase moves to TRUMP_SELECT.

        Returns:
            Updated GameState (also stored in self._state).

        Raises:
            ValueError: If the game is already started or finished.
        """
        if self._state.phase not in (GamePhase.WAITING, GamePhase.SCORING):
            raise ValueError(
                f"Cannot start a game in phase '{self._state.phase.value}'."
            )

        # Deal cards
        players_with_cards = deal_to_players(self._state.players)

        # Determine who picks trump this round
        trump_player_id = next_trump_player(self._state)

        self._state = self._state.model_copy(update={
            "players": players_with_cards,
            "phase": GamePhase.TRUMP_SELECT,
            "trump_mode": None,
            "trump_player_id": trump_player_id,
            "current_player_id": trump_player_id,
            "current_trick": Trick(),
            "completed_tricks": [],
        })

        return self._state

    def choose_trump(self, player_id: str, mode: TrumpMode) -> GameState:
        """
        Record the trump selection and begin card play.

        Args:
            player_id: Must match state.trump_player_id.
            mode:      One of the 6 TrumpMode values.

        Returns:
            Updated GameState with phase=PLAYING and first player set.

        Raises:
            ValueError: If called in the wrong phase or by the wrong player.
        """
        if self._state.phase != GamePhase.TRUMP_SELECT:
            raise ValueError(
                f"Trump can only be chosen in TRUMP_SELECT phase, "
                f"current phase: '{self._state.phase.value}'."
            )

        if self._state.trump_player_id != player_id:
            raise ValueError(
                f"Only {self._state.trump_player_id} may choose trump, "
                f"not {player_id}."
            )

        # The player who chose trump leads the first trick
        first_player_id = player_id

        self._state = self._state.model_copy(update={
            "trump_mode": mode,
            "phase": GamePhase.PLAYING,
            "current_player_id": first_player_id,
        })

        return self._state

    def play_card(self, player_id: str, card: Card) -> GameState:
        """
        Apply a card play to the game state.

        Steps:
          1. Validate the play (phase, turn, hand, legality).
          2. Remove card from player's hand.
          3. Add card to current trick.
          4. If trick is now complete (4 cards):
               a. Score the trick.
               b. Determine the winner.
               c. Move trick to completed_tricks.
               d. If 9 tricks done: score the round, check game_over.
               e. Otherwise: winner leads the next trick.
          5. If trick is not yet complete: advance turn to next player.

        Args:
            player_id: The player making the move.
            card:      The card they are playing.

        Returns:
            Updated GameState.

        Raises:
            ValueError: If the play is invalid (propagated from validate_play).
        """
        # 1. Validate
        validate_play(self._state, player_id, card, self.variant)

        # 2. Remove card from hand
        self._state = self._remove_card_from_hand(player_id, card)

        # 3. Add card to current trick
        self._state = self._add_card_to_trick(player_id, card)

        # 4. Check if trick is complete
        if self._state.current_trick.is_complete:
            self._state = self._resolve_trick()
        else:
            # 5. Advance turn to next player
            next_pid = self._state.next_player_id(player_id)
            self._state = self._state.model_copy(
                update={"current_player_id": next_pid}
            )

        return self._state

    # ------------------------------------------------------------------
    # Client-safe state view
    # ------------------------------------------------------------------

    def get_state_for(self, player_id: str) -> GameState:
        """
        Return a copy of GameState safe to send to `player_id`.
        All other players' hands are replaced with empty lists.
        """
        return self._state.public_view(player_id)

    # ------------------------------------------------------------------
    # Round management
    # ------------------------------------------------------------------

    def start_next_round(self) -> GameState:
        """
        Begin a new round after the current one has finished scoring.
        Increments round_number, rotates trump player, redeals.

        Raises:
            ValueError: If called when the game is over or not in SCORING phase.
        """
        if self._state.game_over:
            raise ValueError("Cannot start a new round — the game is over.")

        if self._state.phase != GamePhase.SCORING:
            raise ValueError(
                f"Can only start a new round from SCORING phase, "
                f"current: '{self._state.phase.value}'."
            )

        next_round = self._state.round_number + 1
        self._state = self._state.model_copy(update={
            "round_number": next_round,
            "phase": GamePhase.WAITING,
        })

        return self.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remove_card_from_hand(self, player_id: str, card: Card) -> GameState:
        """Return a new state with `card` removed from `player_id`'s hand."""
        updated_players = []
        for player in self._state.players:
            if player.id == player_id:
                new_hand = [c for c in player.hand if c != card]
                # If multiple identical cards exist (shouldn't happen), only
                # remove the first — use a flag to ensure exactly one removal.
                if len(new_hand) == len(player.hand):
                    # Card was not found — validate_play should have caught this
                    raise ValueError(f"Card {card} not found in {player_id}'s hand.")
                # Remove exactly one occurrence
                hand_copy = list(player.hand)
                hand_copy.remove(card)
                updated_players.append(player.model_copy(update={"hand": hand_copy}))
            else:
                updated_players.append(player)

        return self._state.model_copy(update={"players": updated_players})

    def _add_card_to_trick(self, player_id: str, card: Card) -> GameState:
        """Return a new state with the card appended to the current trick."""
        new_entry = TrickEntry(player_id=player_id, card=card)
        existing = self._state.current_trick

        # Set lead_suit on the first card of the trick
        lead_suit = existing.lead_suit if existing.lead_suit else card.suit

        new_trick = existing.model_copy(update={
            "entries": existing.entries + [new_entry],
            "lead_suit": lead_suit,
        })

        return self._state.model_copy(update={"current_trick": new_trick})

    def _resolve_trick(self) -> GameState:
        """
        Called when the current trick has 4 cards.

        1. Score the trick.
        2. Determine the winner.
        3. Stamp winner_id and points onto the trick.
        4. Move it to completed_tricks.
        5. If all 9 tricks done → score the round.
        6. Otherwise → winner leads the next trick.
        """
        trick = self._state.current_trick

        # Score the trick (returns a new Trick with points set)
        scored_trick = score_completed_trick(trick, self._state, self.variant)

        # Determine winner
        winner_id = self.variant.trick_winner(scored_trick, self._state)
        final_trick = scored_trick.model_copy(update={"winner_id": winner_id})

        # Append to completed list, clear current trick
        new_completed = self._state.completed_tricks + [final_trick]
        self._state = self._state.model_copy(update={
            "current_trick": Trick(),
            "completed_tricks": new_completed,
        })

        # Check if all tricks for this round are done
        if len(new_completed) == TRICKS_PER_ROUND:
            return self._finish_round()

        # Not done yet — winner of this trick leads the next one
        self._state = self._state.model_copy(
            update={"current_player_id": winner_id}
        )
        return self._state

    def _finish_round(self) -> GameState:
        """
        Called when all 9 tricks have been played.

        1. Apply round scores to the running totals.
        2. If the game is over, phase = FINISHED.
        3. Otherwise phase = SCORING (caller calls start_next_round()).
        """
        self._state = apply_round_scores(self._state, self.variant)

        # apply_round_scores sets phase=FINISHED if game_over.
        # If the game continues, move to SCORING phase so the room
        # manager knows to prompt start_next_round().
        if not self._state.game_over:
            self._state = self._state.model_copy(
                update={"phase": GamePhase.SCORING}
            )

        return self._state
