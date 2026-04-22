from fastapi import WebSocket
from server.shared.events import Event


async def handle_event(websocket: WebSocket, event: dict) -> None:
    """Route incoming WebSocket events to the correct handler."""
    event_type = event.get("type")

    if event_type == Event.JOIN_ROOM:
        pass  # TODO
    elif event_type == Event.PLAY_CARD:
        pass  # TODO
    elif event_type == Event.START_GAME:
        pass  # TODO
    else:
        await websocket.send_json({"type": "error", "message": f"Unknown event: {event_type}"})
