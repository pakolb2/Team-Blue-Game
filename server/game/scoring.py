from server.shared.types import Trick, Variant


CARD_POINTS = {
    # Filled in per variant in variant modules
}


def score_trick(trick: Trick, variant: Variant) -> int:
    """Calculate the point value of a completed trick for the given variant."""
    raise NotImplementedError


def score_game(tricks: list[Trick], variant: Variant) -> dict:
    """Calculate final scores for all players/teams at end of game."""
    raise NotImplementedError
