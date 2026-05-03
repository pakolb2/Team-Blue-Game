"""
server/shared/timing.py
-----------------------
Runtime pacing constants for WebSocket-driven game flow.

The engine and room manager stay deterministic and fast. The socket layer
uses these values to decide how long a rendered action remains visible before
the next automatic bot or round action is applied.

Values can be overridden for tests or deployments with environment variables:
    JASS_BOT_ACTION_DELAY_SECONDS
    JASS_TRICK_COMPLETE_PAUSE_SECONDS
    JASS_ROUND_START_PAUSE_SECONDS
"""

from __future__ import annotations

import os


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, value)


BOT_ACTION_DELAY_SECONDS: float = _env_float(
    "JASS_BOT_ACTION_DELAY_SECONDS", 1.0
)
TRICK_COMPLETE_PAUSE_SECONDS: float = _env_float(
    "JASS_TRICK_COMPLETE_PAUSE_SECONDS", 5.0
)
ROUND_START_PAUSE_SECONDS: float = _env_float(
    "JASS_ROUND_START_PAUSE_SECONDS", 10.0
)

# Safety bound so a broken bot or variant can never keep a handler alive forever.
MAX_AUTOMATED_ACTIONS_PER_RUN: int = 40
