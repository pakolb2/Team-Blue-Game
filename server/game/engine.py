from server.shared.types import GameState


class GameEngine:
    """Main game loop. Drives turn order, delegates to the active variant for rules and scoring."""

    def __init__(self, state: GameState):
        self.state = state

    def start(self) -> None:
        raise NotImplementedError

    def play_card(self, player_id: str, card_index: int) -> GameState:
        raise NotImplementedError
