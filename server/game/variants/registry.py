"""
server/game/variants/registry.py
---------------------------------
Central registry for Jass variants.

Room and socket orchestration should not import concrete variants directly.
Register new variants here, together with any room-scoped cleanup hooks they
need, and the rest of the application can stay variant-neutral.
"""

from __future__ import annotations

from collections.abc import Callable

from server.game.variants.base import BaseVariant
from server.game.variants.schieber import Schieber
from server.game.variants.differenzler import Differenzler, clear_predictions
from server.game.variants.coiffeur import Coiffeur, clear_tracker


VARIANT_REGISTRY: dict[str, BaseVariant] = {
    "schieber": Schieber(),
    "differenzler": Differenzler(),
    "coiffeur": Coiffeur(),
}

_ROOM_STATE_CLEANUPS: tuple[Callable[[str], None], ...] = (
    clear_predictions,
    clear_tracker,
)


def get_variant(name: str) -> BaseVariant:
    """Return the registered variant matching ``name`` case-insensitively."""
    key = (name or "").lower()
    variant = VARIANT_REGISTRY.get(key)
    if variant is None:
        available = ", ".join(sorted(VARIANT_REGISTRY.keys()))
        raise ValueError(f"Unknown variant '{name}'. Available: {available}.")
    return variant


def clear_room_variant_state(room_id: str) -> None:
    """
    Clear all room-scoped side stores owned by registered variants.

    Current Differenzler and Coiffeur implementations keep prediction/mode
    trackers outside GameState. Keeping cleanup here avoids hardcoding those
    implementation details in RoomManager.
    """
    for cleanup in _ROOM_STATE_CLEANUPS:
        cleanup(room_id)
