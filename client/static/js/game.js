/**
 * client/static/js/game.js
 * -------------------------
 * Game board rendering and state management.
 *
 * State machine:
 *   waiting → trump_select → playing → scoring → (next round or finished)
 *
 * Rendering:
 *   - Four seats around a felt table
 *   - Centre trick area with played cards
 *   - Player's hand at bottom (clickable when it's their turn)
 *   - Scoreboard, trump badge, status bar
 *   - Trump picker modal (when in trump_select phase)
 *   - Game over overlay
 */

// ─── Constants ──────────────────────────────────────────────────────────────

const SUIT_ICONS = {
  Eichel:  '🌰',
  Schilte: '🛡️',
  Schelle: '🔔',
  Rose:    '🌹',
  Obenabe: '▲',
  Undeufe: '▼',
};

const SUIT_SYMBOLS = {
  Eichel:  '♣',
  Schilte: '♦',
  Schelle: '♠',
  Rose:    '♥',
};

const TRUMP_MODES = [
  { key: 'Eichel',  label: 'Eichel',  icon: '🌰' },
  { key: 'Schilte', label: 'Schilte', icon: '🛡️' },
  { key: 'Schelle', label: 'Schelle', icon: '🔔' },
  { key: 'Rose',    label: 'Rose',    icon: '🌹' },
  { key: 'Obenabe', label: 'Obenabe', icon: '▲' },
  { key: 'Undeufe', label: 'Undeufe', icon: '▼' },
];

// Seat arrangement: [bottom(me), right, top, left]
// Maps seatIndex → grid position class
const SEAT_POSITIONS = ['seat-bottom', 'seat-right', 'seat-top', 'seat-left'];

// ─── State ───────────────────────────────────────────────────────────────────

let gameState = null;     // latest GameState from server
let myPlayerId = null;    // this client's player ID
let roomId = null;        // current room ID
let selectedCard = null;  // card the player has clicked (pending play)

// ─── Initialisation ──────────────────────────────────────────────────────────

function initGame(pid, rid) {
  myPlayerId = pid;
  roomId = rid;

  // Register socket event handlers
  socket.on('game_started',   onGameStarted);
  socket.on('state_updated',  onStateUpdated);
  socket.on('trick_complete', onTrickComplete);
  socket.on('round_complete', onRoundComplete);
  socket.on('game_over',      onGameOver);
  socket.on('error',          onError);

  // Connect
  socket.connect(pid);
  socket.on('__connected__', () => {
    // Re-join the room (handles both fresh join and reconnect)
    socket.send('join_room', {
      room_id: roomId,
      player_id: myPlayerId,
      player_name: getPlayerName(),
    });
  });
}

// ─── Server event handlers ───────────────────────────────────────────────────

function onGameStarted(data) {
  gameState = data.state;
  render();
  showToast('Game started!', 'info');
}

function onStateUpdated(data) {
  gameState = data.state;
  selectedCard = null;
  render();
}

function onTrickComplete(data) {
  gameState = data.state;
  selectedCard = null;

  // Show brief winner flash
  const winnerId = data.winner_id;
  const winner = gameState.players.find(p => p.id === winnerId);
  if (winner) {
    showTrickFlash(`${winner.id === myPlayerId ? 'You win' : winner.id + ' wins'} the trick (+${data.points}pts)`);
  }

  // Short delay then re-render for next trick
  setTimeout(() => render(), 1200);
}

function onRoundComplete(data) {
  showRoundBanner(data.scores, data.round_number + 1);
  // Server will start next round automatically; wait for state_updated
}

function onGameOver(data) {
  const winnerTeam = data.winner;
  const myPlayer = gameState && gameState.players.find(p => p.id === myPlayerId);
  const won = myPlayer && myPlayer.team === winnerTeam;
  showGameOver(data, won);
}

function onError(data) {
  showToast(data.message || 'An error occurred.', 'error');
}

// ─── Main render ─────────────────────────────────────────────────────────────

function render() {
  if (!gameState) return;

  renderSeats();
  renderTrick();
  renderMyHand();
  renderScoreboard();
  renderTrump();
  renderStatus();

  // Show trump picker if needed
  const phase = gameState.phase;
  if (phase === 'trump_select' && gameState.trump_player_id === myPlayerId) {
    showTrumpPicker();
  } else {
    hideTrumpPicker();
  }
}

// ─── Seats ───────────────────────────────────────────────────────────────────

function renderSeats() {
  const players = gameState.players;
  const myIdx = players.findIndex(p => p.id === myPlayerId);
  if (myIdx === -1) return;

  // Rotate so my player is always at seat-bottom (index 0)
  const ordered = [];
  for (let i = 0; i < 4; i++) {
    ordered.push(players[(myIdx + i) % players.length]);
  }

  // Clear and rebuild opponent seats (skip index 0 = self)
  ['seat-top', 'seat-left', 'seat-right'].forEach(cls => {
    const el = document.querySelector(`.${cls}`);
    if (el) el.innerHTML = '';
  });

  // Index 1 → right, 2 → top, 3 → left
  const posMap = { 1: 'seat-right', 2: 'seat-top', 3: 'seat-left' };
  for (let i = 1; i < 4; i++) {
    const player = ordered[i];
    if (!player) continue;
    const slot = document.querySelector(`.${posMap[i]}`);
    if (!slot) continue;

    const isActive = gameState.current_player_id === player.id;
    const teamCls = player.team === 'team_a' ? 'seat-team-a' : 'seat-team-b';

    slot.innerHTML = `
      <div class="seat ${teamCls} ${isActive ? 'seat-active' : ''}">
        <div class="seat-indicator"></div>
        <div class="seat-name">${escHtml(player.id)}</div>
        <div class="mini-hand ${i === 2 ? '' : 'mini-hand-v'}">
          ${Array.from({ length: player.hand_count }, () =>
            `<div class="card card-back"></div>`
          ).join('')}
        </div>
      </div>
    `;
  }
}

// ─── Current trick ───────────────────────────────────────────────────────────

function renderTrick() {
  const trickEl = document.querySelector('.trick-area');
  if (!trickEl) return;

  const trick = gameState.current_trick;
  const players = gameState.players;
  const myIdx = players.findIndex(p => p.id === myPlayerId);

  // Clear existing played cards
  trickEl.querySelectorAll('.trick-card-slot').forEach(el => el.remove());

  if (!trick || !trick.entries || trick.entries.length === 0) return;

  trick.entries.forEach((entry) => {
    const playerIdx = players.findIndex(p => p.id === entry.player_id);
    // Position relative to me (0 = me = bottom, 1 = right, 2 = top, 3 = left)
    const relIdx = ((playerIdx - myIdx) + 4) % 4;
    const slotCls = `trick-slot-${relIdx}`;

    const slot = document.createElement('div');
    slot.className = `trick-card-slot ${slotCls}`;
    slot.innerHTML = buildCardHTML(entry.card, ['played']);
    trickEl.appendChild(slot);
  });
}

// ─── My hand ─────────────────────────────────────────────────────────────────

function renderMyHand() {
  const handEl = document.querySelector('.my-hand');
  if (!handEl) return;

  const me = gameState.players.find(p => p.id === myPlayerId);
  if (!me || !me.hand) { handEl.innerHTML = ''; return; }

  const isMyTurn = gameState.current_player_id === myPlayerId
                   && gameState.phase === 'playing';

  handEl.innerHTML = me.hand.map(card => {
    const isSelected = selectedCard &&
      selectedCard.suit === card.suit && selectedCard.rank === card.rank;
    const extraClasses = [
      isMyTurn ? 'playable' : 'not-turn',
      isSelected ? 'selected' : '',
    ];
    return `<div class="card-wrap" data-suit="${card.suit}" data-rank="${card.rank}">
      ${buildCardHTML(card, extraClasses)}
    </div>`;
  }).join('');

  // Attach click handlers
  if (isMyTurn) {
    handEl.querySelectorAll('.card-wrap').forEach(wrap => {
      wrap.querySelector('.card').addEventListener('click', () => {
        const suit = wrap.dataset.suit;
        const rank = wrap.dataset.rank;
        onCardClick(suit, rank);
      });
    });
  }
}

// ─── Card click ──────────────────────────────────────────────────────────────

function onCardClick(suit, rank) {
  if (gameState.phase !== 'playing') return;
  if (gameState.current_player_id !== myPlayerId) return;

  // If already selected → play it
  if (selectedCard && selectedCard.suit === suit && selectedCard.rank === rank) {
    playCard(suit, rank);
    return;
  }

  // First click → select it
  selectedCard = { suit, rank };
  renderMyHand();
  showToast(`${rank} of ${suit} selected — click again to play`, 'info');
}

function playCard(suit, rank) {
  socket.send('play_card', {
    room_id: roomId,
    player_id: myPlayerId,
    card_suit: suit,
    card_rank: rank,
  });
  selectedCard = null;
}

// ─── Scoreboard ──────────────────────────────────────────────────────────────

function renderScoreboard() {
  const el = document.querySelector('.scoreboard');
  if (!el || !gameState.scores) return;

  const teams = ['team_a', 'team_b'];
  el.innerHTML = teams.map(team => {
    const score = gameState.scores[team];
    const total = score ? score.total : 0;
    const last  = score && score.round_scores.length
      ? score.round_scores[score.round_scores.length - 1] : 0;
    return `
      <div class="score-team score-${team}">
        <div class="score-team-name">${team === 'team_a' ? 'Team A' : 'Team B'}</div>
        <div class="score-total">${total}</div>
        <div class="score-round">${last > 0 ? `+${last} this round` : ''}</div>
      </div>
    `;
  }).join('');
}

// ─── Trump badge ─────────────────────────────────────────────────────────────

function renderTrump() {
  const el = document.querySelector('.trump-display');
  if (!el) return;

  if (!gameState.trump_mode) {
    el.innerHTML = '<span class="trump-badge">Choosing trump…</span>';
    return;
  }
  const icon = SUIT_ICONS[gameState.trump_mode] || '?';
  el.innerHTML = `
    <span class="trump-badge">
      <span class="trump-icon">${icon}</span>
      ${escHtml(gameState.trump_mode)}
    </span>
  `;
}

// ─── Status bar ──────────────────────────────────────────────────────────────

function renderStatus() {
  const el = document.querySelector('.status-bar');
  if (!el) return;

  const phase = gameState.phase;
  const current = gameState.current_player_id;

  if (phase === 'trump_select') {
    if (current === myPlayerId) {
      el.textContent = 'Your turn to choose trump.';
      el.className = 'status-bar highlight';
    } else {
      el.textContent = `${current} is choosing trump…`;
      el.className = 'status-bar';
    }
    return;
  }

  if (phase === 'playing') {
    if (current === myPlayerId) {
      el.textContent = selectedCard
        ? `Click ${selectedCard.rank} of ${selectedCard.suit} again to play, or choose a different card.`
        : 'Your turn — click a card to select it.';
      el.className = 'status-bar highlight';
    } else {
      el.textContent = `Waiting for ${current}…`;
      el.className = 'status-bar';
    }
    return;
  }

  if (phase === 'scoring') {
    el.textContent = 'Round complete — next round starting…';
    el.className = 'status-bar';
    return;
  }

  el.textContent = '';
  el.className = 'status-bar';
}

// ─── Trump picker modal ───────────────────────────────────────────────────────

function showTrumpPicker() {
  let overlay = document.getElementById('trump-picker');
  if (overlay) return; // already shown

  overlay = document.createElement('div');
  overlay.id = 'trump-picker';
  overlay.className = 'trump-picker';
  overlay.innerHTML = `
    <div class="trump-picker-box">
      <div class="trump-picker-title">Choose Trump</div>
      <div class="trump-options">
        ${TRUMP_MODES.map(m => `
          <div class="trump-option" data-mode="${m.key}">
            <span class="trump-option-icon">${m.icon}</span>
            <span class="trump-option-label">${m.label}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  overlay.querySelectorAll('.trump-option').forEach(opt => {
    opt.addEventListener('click', () => {
      chooseTrump(opt.dataset.mode);
      hideTrumpPicker();
    });
  });

  document.body.appendChild(overlay);
}

function hideTrumpPicker() {
  const el = document.getElementById('trump-picker');
  if (el) el.remove();
}

function chooseTrump(mode) {
  socket.send('choose_trump', {
    room_id: roomId,
    player_id: myPlayerId,
    trump_mode: mode,
  });
}

// ─── Trick complete flash ─────────────────────────────────────────────────────

function showTrickFlash(message) {
  const trickEl = document.querySelector('.trick-area');
  if (!trickEl) return;

  const flash = document.createElement('div');
  flash.className = 'trick-flash';
  flash.innerHTML = `<div class="trick-flash-label">${escHtml(message)}</div>`;
  trickEl.appendChild(flash);

  setTimeout(() => flash.remove(), 1600);
}

// ─── Round complete banner ───────────────────────────────────────────────────

function showRoundBanner(scores, roundNum) {
  const existing = document.getElementById('round-banner');
  if (existing) existing.remove();

  const banner = document.createElement('div');
  banner.id = 'round-banner';
  banner.className = 'round-banner';

  const a = scores['team_a'] || { round: 0, total: 0 };
  const b = scores['team_b'] || { round: 0, total: 0 };

  banner.innerHTML = `
    <span style="font-family:var(--font-display);font-weight:700;color:var(--gold-accent)">
      Round ${roundNum} complete
    </span>
    <span style="font-size:.9rem;color:var(--cream-300)">
      Team A: <strong>${a.total}</strong> (+${a.round}) &nbsp;·&nbsp;
      Team B: <strong>${b.total}</strong> (+${b.round})
    </span>
    <button class="btn btn-sm btn-secondary" onclick="document.getElementById('round-banner').remove()">
      Dismiss
    </button>
  `;

  document.body.appendChild(banner);
  setTimeout(() => banner.remove(), 6000);
}

// ─── Game over overlay ────────────────────────────────────────────────────────

function showGameOver(data, won) {
  let overlay = document.getElementById('game-over');
  if (overlay) overlay.remove();

  overlay = document.createElement('div');
  overlay.id = 'game-over';
  overlay.className = 'game-over-overlay';

  const totals = data.final_totals || {};
  const winnerTeam = data.winner || '';

  overlay.innerHTML = `
    <div class="game-over-box">
      <div class="game-over-title">${won ? '🏆 Victory!' : 'Game Over'}</div>
      <div class="game-over-winner">
        ${winnerTeam === 'team_a' ? 'Team A wins' : 'Team B wins'}
      </div>
      <div class="game-over-scores">
        ${['team_a', 'team_b'].map(team => `
          <div class="final-score score-${team} ${team === winnerTeam ? 'winner-team' : ''}">
            <div class="final-score-label">${team === 'team_a' ? 'Team A' : 'Team B'}</div>
            <div class="final-score-pts">${totals[team] || 0}</div>
          </div>
        `).join('')}
      </div>
      <button class="btn btn-primary btn-lg" onclick="location.href='/'">
        Return to Lobby
      </button>
    </div>
  `;

  document.body.appendChild(overlay);
}

// ─── Toast notifications ──────────────────────────────────────────────────────

function showToast(message, type = 'info') {
  let container = document.querySelector('.toasts');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toasts';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = 'opacity .3s, transform .3s';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ─── Card HTML builder ────────────────────────────────────────────────────────

function buildCardHTML(card, extraClasses = []) {
  const { suit, rank } = card;
  const sym = SUIT_SYMBOLS[suit] || suit[0];
  const allClasses = ['card', `suit-${suit}`, ...extraClasses].join(' ');

  return `
    <div class="${allClasses}" title="${rank} of ${suit}">
      <div class="card-rank-top">
        <span>${escHtml(rank)}</span>
        <span class="card-suit-icon">${sym}</span>
      </div>
      <div class="card-suit-center">${sym}</div>
      <div class="card-rank-bot">
        <span>${escHtml(rank)}</span>
        <span class="card-suit-icon">${sym}</span>
      </div>
    </div>
  `;
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
