from server.shared.types import Card, GameState


def get_legal_moves(state: GameState, player_id: str) -> list[Card]:
    """Return the list of cards a player is legally allowed to play."""
    raise NotImplementedError


def is_legal(state: GameState, player_id: str, card: Card) -> bool:
    """Check whether a specific card play is legal."""
    raise NotImplementedError
