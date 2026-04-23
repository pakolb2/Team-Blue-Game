"""
server/sockets/__init__.py
---------------------------
WebSocket layer.

    from server.sockets.handlers import ConnectionManager, handle_event

One ConnectionManager instance is created at app startup alongside
the RoomManager. Both are shared across all WebSocket connections.
"""
