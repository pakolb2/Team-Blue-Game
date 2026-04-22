class Event:
    """WebSocket event name constants shared by server and client JS."""

    # Client -> Server
    JOIN_ROOM = "join_room"
    LEAVE_ROOM = "leave_room"
    START_GAME = "start_game"
    PLAY_CARD = "play_card"
    CHOOSE_TRUMP = "choose_trump"

    # Server -> Client
    ROOM_UPDATED = "room_updated"
    GAME_STARTED = "game_started"
    STATE_UPDATED = "state_updated"
    TRICK_COMPLETE = "trick_complete"
    GAME_OVER = "game_over"
    ERROR = "error"
