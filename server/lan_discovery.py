"""
server/lan_discovery.py
------------------------
LAN discovery helpers for Phase 11.

Enables players on the same local network to find each other without
sharing a URL manually. Two mechanisms are provided:

1. HTTP broadcast endpoint (/api/lan/announce)
   The host polls their local IP and exposes it. Other clients on the
   same LAN visit the same IP and port directly.

2. UDP broadcast listener (optional, background thread)
   The server broadcasts a UDP packet on port 4445 every 5 seconds.
   Clients can listen for it and auto-discover the server's IP.
   This is entirely optional — the HTTP endpoint works without it.

Usage (in main.py):
    from server.lan_discovery import router as lan_router, start_udp_broadcast
    app.include_router(lan_router)
    # Optional UDP:
    # start_udp_broadcast(port=4445)

The frontend JS (in home.html) polls /api/lan/servers every 3 seconds
and shows any discovered servers in the lobby.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import logging
from typing import Optional

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router — HTTP LAN discovery endpoints
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/lan", tags=["LAN Discovery"])

# In-memory registry of announced servers
# {ip: {"ip": str, "port": int, "name": str, "last_seen": float}}
_announced: dict[str, dict] = {}
_STALE_SECONDS = 15   # remove servers not heard from in 15s


def _prune_stale() -> None:
    now = time.time()
    stale = [ip for ip, info in _announced.items()
             if now - info["last_seen"] > _STALE_SECONDS]
    for ip in stale:
        del _announced[ip]


@router.get("/servers")
async def list_lan_servers() -> dict:
    """
    Return a list of Jass servers currently active on the LAN.

    The client polls this endpoint periodically.
    Each server announces itself via POST /api/lan/announce.
    """
    _prune_stale()
    return {"servers": list(_announced.values())}


@router.post("/announce")
async def announce_server(name: str = "Jass Game") -> dict:
    """
    Self-announce this server to the LAN discovery list.

    Typically called once at startup and then every ~10s by the host client.
    The IP is inferred from the connecting request (loopback in tests,
    real LAN IP when called from within the LAN).
    """
    ip = _get_local_ip()
    port = 8000  # default uvicorn port

    _announced[ip] = {
        "ip":        ip,
        "port":      port,
        "name":      name[:40],
        "last_seen": time.time(),
    }
    logger.info(f"LAN announce: {ip}:{port} ({name})")
    return {"announced": True, "ip": ip, "port": port}


@router.delete("/announce")
async def deannounce_server() -> dict:
    """Remove this server from the LAN discovery list (on shutdown)."""
    ip = _get_local_ip()
    _announced.pop(ip, None)
    return {"removed": True}


# ---------------------------------------------------------------------------
# UDP broadcast (optional background thread)
# ---------------------------------------------------------------------------

_udp_thread: Optional[threading.Thread] = None
_udp_stop = threading.Event()


def start_udp_broadcast(port: int = 4445, interval: int = 5) -> None:
    """
    Start a background thread that broadcasts UDP packets on the LAN.
    Clients can discover the server without knowing its IP.

    Packet payload: JSON {"type":"jass_server","ip":"...","port":8000}
    """
    global _udp_thread
    if _udp_thread and _udp_thread.is_alive():
        return

    _udp_stop.clear()
    _udp_thread = threading.Thread(
        target=_udp_broadcast_loop,
        args=(port, interval),
        daemon=True,
        name="jass-udp-broadcast",
    )
    _udp_thread.start()
    logger.info(f"UDP LAN broadcast started on port {port}")


def stop_udp_broadcast() -> None:
    """Stop the UDP broadcast thread."""
    _udp_stop.set()


def _udp_broadcast_loop(port: int, interval: int) -> None:
    """Broadcast UDP packets until stopped."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(1)

        ip = _get_local_ip()
        payload = json.dumps({
            "type":    "jass_server",
            "ip":      ip,
            "port":    8000,
            "version": "1.0",
        }).encode()

        while not _udp_stop.is_set():
            try:
                sock.sendto(payload, ('<broadcast>', port))
            except Exception as e:
                logger.debug(f"UDP broadcast error: {e}")
            _udp_stop.wait(interval)

    except Exception as e:
        logger.error(f"UDP broadcast thread failed: {e}")
    finally:
        try: sock.close()
        except: pass


# ---------------------------------------------------------------------------
# UDP listener (client-side, run in browser via JS — this is just a reference)
# ---------------------------------------------------------------------------

def _get_local_ip() -> str:
    """
    Return the machine's LAN IP address (not loopback).
    Falls back to 127.0.0.1 if detection fails.
    """
    try:
        # Connect to an external address to determine the correct interface
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
