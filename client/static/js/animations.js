/**
 * client/static/js/animations.js
 * --------------------------------
 * Card and UI animations for Phase 11.
 *
 * All animations use the Web Animations API where possible (better
 * performance than JS-driven setInterval, no layout thrashing).
 * CSS keyframes are the fallback for simpler effects.
 *
 * Public API:
 *   animateDeal(cardElements)          — fan cards in from deck position
 *   animateCardPlay(cardEl, targetPos) — fly card from hand to trick centre
 *   animateTrickCollect(trickEl, winnerId, seatEl) — sweep trick to winner
 *   animateScoreReveal(scoreEl, from, to) — count-up score animation
 *   animateShake(el)                   — error shake (illegal play)
 *   animateWinnerPulse(seatEl)         — pulse winner seat on trick win
 *   animateGameOver(overlayEl)         — cinematic game-over entrance
 */

// ---------------------------------------------------------------------------
// Timing constants
// ---------------------------------------------------------------------------

const DEAL_DURATION_MS       = 280;
const DEAL_STAGGER_MS        = 60;
const PLAY_CARD_DURATION_MS  = 220;
const COLLECT_DURATION_MS    = 500;
const SCORE_COUNT_DURATION   = 900;
const SHAKE_DURATION_MS      = 400;
const WINNER_PULSE_DURATION  = 600;

// ---------------------------------------------------------------------------
// Deal animation
// ---------------------------------------------------------------------------

/**
 * Animate a set of card elements dealing in from the top-left (deck position).
 * Cards start invisible off-screen and fly to their natural positions.
 *
 * @param {NodeList|Element[]} cardElements
 * @param {number} [staggerMs] - delay between each card
 */
function animateDeal(cardElements, staggerMs = DEAL_STAGGER_MS) {
  const cards = Array.from(cardElements);
  cards.forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(-40px) scale(0.7)';

    setTimeout(() => {
      card.animate([
        { opacity: 0, transform: 'translateY(-40px) scale(0.7)' },
        { opacity: 1, transform: 'translateY(0)   scale(1)',
          easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)' },
      ], {
        duration: DEAL_DURATION_MS,
        fill: 'forwards',
      });
    }, i * staggerMs);
  });
}

// ---------------------------------------------------------------------------
// Card play animation
// ---------------------------------------------------------------------------

/**
 * Animate a card flying from its current position to a target position.
 * Used when a player plays a card into the trick area.
 *
 * @param {Element} cardEl        - the card element to animate
 * @param {{ x: number, y: number }} targetPos - page coords of the trick slot
 * @param {function} [onComplete] - callback when animation ends
 */
function animateCardPlay(cardEl, targetPos, onComplete) {
  const rect = cardEl.getBoundingClientRect();
  const dx = targetPos.x - rect.left;
  const dy = targetPos.y - rect.top;

  const anim = cardEl.animate([
    { transform: 'translate(0, 0) scale(1)',       opacity: 1 },
    { transform: `translate(${dx}px, ${dy}px) scale(0.95)`, opacity: 0.9 },
  ], {
    duration: PLAY_CARD_DURATION_MS,
    easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    fill: 'forwards',
  });

  if (onComplete) anim.onfinish = onComplete;
  return anim;
}

// ---------------------------------------------------------------------------
// Trick collection animation
// ---------------------------------------------------------------------------

/**
 * Sweep all cards in the trick area toward the winner's seat.
 *
 * @param {Element}  trickEl   - the .trick-area container
 * @param {string}   winnerId  - player_id of the winner
 * @param {Element}  winnerSeatEl - the winner's seat element
 * @param {function} [onComplete]
 */
function animateTrickCollect(trickEl, winnerId, winnerSeatEl, onComplete) {
  if (!trickEl || !winnerSeatEl) {
    if (onComplete) onComplete();
    return;
  }

  const trickCards = trickEl.querySelectorAll('.trick-card-slot');
  const seatRect   = winnerSeatEl.getBoundingClientRect();
  const targetX    = seatRect.left + seatRect.width  / 2;
  const targetY    = seatRect.top  + seatRect.height / 2;

  const animations = [];
  trickCards.forEach(slot => {
    const rect = slot.getBoundingClientRect();
    const dx = targetX - (rect.left + rect.width  / 2);
    const dy = targetY - (rect.top  + rect.height / 2);

    const anim = slot.animate([
      { transform: 'translate(0,0) scale(1)',            opacity: 1 },
      { transform: `translate(${dx}px,${dy}px) scale(0.4)`, opacity: 0 },
    ], {
      duration: COLLECT_DURATION_MS,
      easing: 'cubic-bezier(0.55, 0, 1, 0.45)',
      fill: 'forwards',
    });
    animations.push(anim);
  });

  if (onComplete && animations.length > 0) {
    animations[animations.length - 1].onfinish = onComplete;
  } else if (onComplete) {
    onComplete();
  }
}

// ---------------------------------------------------------------------------
// Score count-up animation
// ---------------------------------------------------------------------------

/**
 * Animate a score display from `from` to `to` over ~900ms.
 * Uses requestAnimationFrame for smooth number transitions.
 *
 * @param {Element} el        - element whose textContent to update
 * @param {number}  from      - starting value
 * @param {number}  to        - ending value
 * @param {number}  [durationMs]
 */
function animateScoreReveal(el, from, to, durationMs = SCORE_COUNT_DURATION) {
  if (!el) return;
  const start = performance.now();
  const diff  = to - from;

  function step(now) {
    const elapsed  = now - start;
    const progress = Math.min(elapsed / durationMs, 1);
    // Ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(from + diff * eased);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ---------------------------------------------------------------------------
// Error shake
// ---------------------------------------------------------------------------

/**
 * Shake an element to indicate an error (e.g. illegal card play attempt).
 *
 * @param {Element} el
 */
function animateShake(el) {
  if (!el) return;
  el.animate([
    { transform: 'translateX(0)' },
    { transform: 'translateX(-8px)' },
    { transform: 'translateX(8px)' },
    { transform: 'translateX(-6px)' },
    { transform: 'translateX(6px)' },
    { transform: 'translateX(-3px)' },
    { transform: 'translateX(0)' },
  ], {
    duration: SHAKE_DURATION_MS,
    easing: 'ease-in-out',
  });
}

// ---------------------------------------------------------------------------
// Winner pulse
// ---------------------------------------------------------------------------

/**
 * Pulse the winning player's seat highlight when they take a trick.
 *
 * @param {Element} seatEl
 */
function animateWinnerPulse(seatEl) {
  if (!seatEl) return;
  seatEl.animate([
    { boxShadow: '0 0 0 0 rgba(232,184,75,0)' },
    { boxShadow: '0 0 0 16px rgba(232,184,75,0.4)' },
    { boxShadow: '0 0 0 0 rgba(232,184,75,0)' },
  ], {
    duration: WINNER_PULSE_DURATION,
    easing: 'ease-out',
  });
}

// ---------------------------------------------------------------------------
// Game over entrance
// ---------------------------------------------------------------------------

/**
 * Cinematic entrance for the game-over overlay.
 * Box scales and fades in from below.
 *
 * @param {Element} overlayEl
 * @param {Element} boxEl      - the inner .game-over-box
 */
function animateGameOver(overlayEl, boxEl) {
  if (overlayEl) {
    overlayEl.animate([
      { opacity: 0 },
      { opacity: 1 },
    ], { duration: 400, fill: 'forwards' });
  }
  if (boxEl) {
    boxEl.animate([
      { opacity: 0, transform: 'translateY(32px) scale(0.92)' },
      { opacity: 1, transform: 'translateY(0)    scale(1)',
        easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)' },
    ], { duration: 500, delay: 150, fill: 'forwards' });
  }
}

// ---------------------------------------------------------------------------
// Card hover sound hook (calls into sounds.js if loaded)
// ---------------------------------------------------------------------------

/**
 * Attach hover/click sound hooks to card elements.
 * Safe to call even if sounds.js is not loaded.
 *
 * @param {NodeList|Element[]} cardElements
 */
function attachCardSounds(cardElements) {
  Array.from(cardElements).forEach(card => {
    card.addEventListener('mouseenter', () => {
      if (typeof playSound === 'function') playSound('card_hover');
    });
    card.addEventListener('click', () => {
      if (typeof playSound === 'function') playSound('card_select');
    });
  });
}

// ---------------------------------------------------------------------------
// Utility: get centre coords of an element (page-relative)
// ---------------------------------------------------------------------------

function getCentre(el) {
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}
