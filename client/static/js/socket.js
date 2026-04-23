/**
 * client/static/js/socket.js
 * ---------------------------
 * WebSocket client.
 *
 * Manages the connection lifecycle and provides a clean API for
 * sending events and registering listeners.
 *
 * Usage:
 *   import { socket } from './socket.js';   (or just include before game.js)
 *   socket.on('state_updated', handler);
 *   socket.send('play_card', { room_id, card_suit, card_rank });
 */

const RECONNECT_DELAY_MS = 2000;
const MAX_RECONNECT_ATTEMPTS = 8;

class JassSocket {
  constructor() {
    this._ws = null;
    this._listeners = {};          // event_type → [handler, ...]
    this._reconnectAttempts = 0;
    this._playerId = null;
    this._intentionalClose = false;
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Connect to the server WebSocket.
   * @param {string} playerId  – unique ID for this client session
   */
  connect(playerId) {
    this._playerId = playerId;
    this._intentionalClose = false;
    this._open();
  }

  /** Send a typed event to the server. */
  send(type, payload = {}) {
    if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
      console.warn('[socket] Cannot send — not connected.', type, payload);
      return;
    }
    this._ws.send(JSON.stringify({ type, ...payload }));
  }

  /** Register a handler for a server event type. */
  on(eventType, handler) {
    if (!this._listeners[eventType]) this._listeners[eventType] = [];
    this._listeners[eventType].push(handler);
  }

  /** Remove a handler (or all handlers for an event type). */
  off(eventType, handler) {
    if (!handler) {
      delete this._listeners[eventType];
      return;
    }
    this._listeners[eventType] = (this._listeners[eventType] || [])
      .filter(h => h !== handler);
  }

  /** Gracefully disconnect. */
  disconnect() {
    this._intentionalClose = true;
    if (this._ws) this._ws.close();
  }

  get connected() {
    return this._ws && this._ws.readyState === WebSocket.OPEN;
  }

  // -------------------------------------------------------------------------
  // Internal
  // -------------------------------------------------------------------------

  _open() {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${location.host}/ws/${this._playerId}`;
    this._ws = new WebSocket(url);

    this._ws.onopen = () => {
      console.log('[socket] Connected as', this._playerId);
      this._reconnectAttempts = 0;
      this._emit('__connected__', {});
    };

    this._ws.onmessage = (evt) => {
      let data;
      try { data = JSON.parse(evt.data); }
      catch { console.error('[socket] Invalid JSON:', evt.data); return; }
      this._emit(data.type, data);
    };

    this._ws.onclose = () => {
      this._emit('__disconnected__', {});
      if (!this._intentionalClose) this._scheduleReconnect();
    };

    this._ws.onerror = (err) => {
      console.error('[socket] WebSocket error', err);
    };
  }

  _emit(eventType, data) {
    (this._listeners[eventType] || []).forEach(h => {
      try { h(data); } catch (e) { console.error('[socket] Handler error:', e); }
    });
    // Also emit wildcard
    (this._listeners['*'] || []).forEach(h => {
      try { h(eventType, data); } catch (e) { console.error('[socket] Handler error:', e); }
    });
  }

  _scheduleReconnect() {
    if (this._reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error('[socket] Max reconnect attempts reached.');
      this._emit('__reconnect_failed__', {});
      return;
    }
    this._reconnectAttempts++;
    const delay = RECONNECT_DELAY_MS * this._reconnectAttempts;
    console.log(`[socket] Reconnecting in ${delay}ms (attempt ${this._reconnectAttempts})`);
    setTimeout(() => this._open(), delay);
  }
}

// Singleton — all modules share one connection
const socket = new JassSocket();


// -------------------------------------------------------------------------
// Player ID persistence
// -------------------------------------------------------------------------

/**
 * Get or create a persistent player ID stored in localStorage.
 * This lets the player reconnect to a game after a page refresh.
 */
function getOrCreatePlayerId() {
  let id = localStorage.getItem('jass_player_id');
  if (!id) {
    id = 'p_' + crypto.randomUUID().replace(/-/g, '').slice(0, 12);
    localStorage.setItem('jass_player_id', id);
  }
  return id;
}

function getPlayerName() {
  return localStorage.getItem('jass_player_name') || 'Player';
}

function setPlayerName(name) {
  localStorage.setItem('jass_player_name', name.trim() || 'Player');
}

function getCurrentRoomId() {
  return localStorage.getItem('jass_room_id');
}

function setCurrentRoomId(roomId) {
  if (roomId) localStorage.setItem('jass_room_id', roomId);
  else localStorage.removeItem('jass_room_id');
}
