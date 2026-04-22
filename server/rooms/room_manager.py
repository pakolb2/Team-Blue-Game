from typing import Dict
from server.shared.types import Room


class RoomManager:
    """Manages creation, joining, and deletion of game rooms."""

    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def create_room(self, room_id: str) -> Room:
        raise NotImplementedError

    def get_room(self, room_id: str) -> Room:
        raise NotImplementedError

    def delete_room(self, room_id: str) -> None:
        raise NotImplementedError
