/**
 * client/static/js/sounds.js
 * ---------------------------
 * Sound effect system using the Web Audio API.
 *
 * Generates all sounds procedurally — no audio files required.
 * This keeps the project self-contained and avoids licensing issues.
 *
 * Sounds:
 *   card_hover    — soft tick when hovering a card
 *   card_select   — click/tap when selecting a card
 *   card_play     — swoosh when playing a card
 *   trick_win     — chime when winning a trick
 *   trump_chosen  — brief fanfare when trump is set
 *   game_over_win — celebratory flourish
 *   game_over_loss— low resolution chord
 *   error         — buzzer for illegal move
 *   round_end     — gentle resolution
 *
 * Usage:
 *   playSound('card_play')
 *   setSoundEnabled(false)
 *   isSoundEnabled()         → true/false
 *
 * Volume is scaled 0–1. Sounds auto-disable if AudioContext is not supported.
 */

let _audioCtx = null;
let _enabled  = true;
let _volume   = 0.5;

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

function _getCtx() {
  if (_audioCtx) return _audioCtx;
  try {
    _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  } catch {
    _audioCtx = null;
  }
  return _audioCtx;
}

// Resume context on first user interaction (browser autoplay policy)
document.addEventListener('click', () => {
  const ctx = _getCtx();
  if (ctx && ctx.state === 'suspended') ctx.resume();
}, { once: true });

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function setSoundEnabled(enabled) {
  _enabled = !!enabled;
  localStorage.setItem('jass_sound', _enabled ? '1' : '0');
}

function isSoundEnabled() { return _enabled; }

function setSoundVolume(v) { _volume = Math.max(0, Math.min(1, v)); }

/**
 * Play a named sound effect.
 * @param {string} name  — one of the sound keys listed above
 */
function playSound(name) {
  if (!_enabled) return;
  const ctx = _getCtx();
  if (!ctx) return;

  try {
    switch (name) {
      case 'card_hover':   _playTick(ctx, 1800, 0.04, 0.04); break;
      case 'card_select':  _playTick(ctx, 1200, 0.09, 0.08); break;
      case 'card_play':    _playSwoosh(ctx);                   break;
      case 'trick_win':    _playChime(ctx);                    break;
      case 'trump_chosen': _playFanfare(ctx);                  break;
      case 'game_over_win':_playVictory(ctx);                  break;
      case 'game_over_loss':_playDefeat(ctx);                  break;
      case 'error':        _playBuzzer(ctx);                   break;
      case 'round_end':    _playResolution(ctx);               break;
    }
  } catch (e) {
    // Silently ignore audio errors
  }
}

// ---------------------------------------------------------------------------
// Restore preference
// ---------------------------------------------------------------------------

const saved = localStorage.getItem('jass_sound');
if (saved === '0') _enabled = false;

// ---------------------------------------------------------------------------
// Sound generators
// ---------------------------------------------------------------------------

/** Short sine tick — hover / select */
function _playTick(ctx, freq, gainPeak, duration) {
  const osc   = ctx.createOscillator();
  const gain  = ctx.createGain();
  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.type = 'sine';
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0, ctx.currentTime);
  gain.gain.linearRampToValueAtTime(gainPeak * _volume, ctx.currentTime + 0.005);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

  osc.start(ctx.currentTime);
  osc.stop(ctx.currentTime + duration + 0.01);
}

/** Swoosh — card played */
function _playSwoosh(ctx) {
  const bufSize = ctx.sampleRate * 0.15;
  const buf     = ctx.createBuffer(1, bufSize, ctx.sampleRate);
  const data    = buf.getChannelData(0);
  for (let i = 0; i < bufSize; i++) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / bufSize);
  }

  const src    = ctx.createBufferSource();
  const filter = ctx.createBiquadFilter();
  const gain   = ctx.createGain();

  src.buffer = buf;
  filter.type = 'bandpass';
  filter.frequency.value = 800;
  filter.Q.value = 0.5;
  gain.gain.value = 0.18 * _volume;

  src.connect(filter);
  filter.connect(gain);
  gain.connect(ctx.destination);
  src.start();
}

/** Short chime sequence — trick won */
function _playChime(ctx) {
  const notes = [523.25, 659.25, 783.99];  // C5, E5, G5
  notes.forEach((freq, i) => {
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.type = 'triangle';
    osc.frequency.value = freq;
    const t = ctx.currentTime + i * 0.12;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(0.15 * _volume, t + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.4);

    osc.start(t);
    osc.stop(t + 0.41);
  });
}

/** Two-note fanfare — trump chosen */
function _playFanfare(ctx) {
  [[392, 0], [523.25, 0.18]].forEach(([freq, delay]) => {
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.type = 'square';
    osc.frequency.value = freq;
    const t = ctx.currentTime + delay;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(0.1 * _volume, t + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);

    osc.start(t);
    osc.stop(t + 0.26);
  });
}

/** Ascending arpeggio — game won */
function _playVictory(ctx) {
  [261.63, 329.63, 392, 523.25, 659.25].forEach((freq, i) => {
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.type = 'sine';
    osc.frequency.value = freq;
    const t = ctx.currentTime + i * 0.1;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(0.18 * _volume, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.5);

    osc.start(t);
    osc.stop(t + 0.51);
  });
}

/** Descending chord — game lost */
function _playDefeat(ctx) {
  [220, 196, 174.61].forEach((freq, i) => {
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.type = 'sawtooth';
    osc.frequency.value = freq;
    const t = ctx.currentTime + i * 0.2;
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(0.12 * _volume, t + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.6);

    osc.start(t);
    osc.stop(t + 0.61);
  });
}

/** Buzzer — illegal play */
function _playBuzzer(ctx) {
  const osc  = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.type = 'sawtooth';
  osc.frequency.value = 110;
  gain.gain.setValueAtTime(0.15 * _volume, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);

  osc.start(ctx.currentTime);
  osc.stop(ctx.currentTime + 0.21);
}

/** Gentle resolution chord — round end */
function _playResolution(ctx) {
  [392, 493.88, 587.33].forEach((freq, i) => {
    const osc  = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.type = 'sine';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.1 * _volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.7);

    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.71);
  });
}
