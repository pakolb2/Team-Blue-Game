/**
 * client/static/js/tutorial.js
 * ------------------------------
 * Step-by-step Jass tutorial controller.
 *
 * Each step has: title, badge, body HTML, optional card demo.
 * Navigation: nextStep() / prevStep() / goToStep(n).
 */

const TUTORIAL_STEPS = [
  {
    badge: 'The Basics',
    title: 'Welcome to Jass',
    body: `
      <p>Jass is the national card game of Switzerland, played by millions
      across the country. This tutorial will teach you the standard
      <em>Schieber</em> variant — the most popular form of the game.</p>
      <p>Jass is a trick-taking game for <strong>4 players</strong> in
      two teams: players seated opposite each other are partners.
      Seats 0 &amp; 2 form Team A; seats 1 &amp; 3 form Team B.</p>
    `,
  },
  {
    badge: 'The Deck',
    title: 'The Swiss Jass Deck',
    body: `
      <p>The game uses a special <strong>36-card deck</strong> — the standard
      52-card deck with all 2s, 3s, 4s, and 5s removed. This leaves
      9 ranks per suit: 6, 7, 8, 9, 10, J, Q, K, A.</p>
      <p>There are four suits, each with a distinct symbol:</p>
    `,
    cardDemo: [
      { suit: 'Eichel',  rank: 'A', label: 'Eichel (Acorns) ♣' },
      { suit: 'Schilte', rank: 'A', label: 'Schilte (Shields) ♦' },
      { suit: 'Schelle', rank: 'A', label: 'Schelle (Bells) ♠' },
      { suit: 'Rose',    rank: 'A', label: 'Rose (Roses) ♥' },
    ],
  },
  {
    badge: 'Trump',
    title: 'Choosing Trump',
    body: `
      <p>At the start of each round, one player (rotating each round) chooses
      <strong>trump</strong>. Trump cards beat all non-trump cards, regardless
      of rank.</p>
      <p>You can choose any of the four suits as trump, or one of two special
      modes with no trump suit:</p>
      <ul>
        <li><strong>Obenabe</strong> — no trump; Aces are highest.</li>
        <li><strong>Undeufe</strong> — no trump; 6s are highest (everything reversed).</li>
      </ul>
    `,
  },
  {
    badge: 'Trump Cards',
    title: 'Buur &amp; Nell — the Power Cards',
    body: `
      <p>When a suit is trump, two cards become extra-powerful:</p>
      <ul>
        <li><strong>Buur</strong> — the Jack of trumps. Worth <strong>20 points</strong>
            and the highest card in the game. Nothing beats it.</li>
        <li><strong>Nell</strong> — the Nine of trumps. Worth <strong>14 points</strong>
            and second only to the Buur.</li>
      </ul>
      <p>All other trump cards keep their normal rank order.</p>
    `,
    cardDemo: [
      { suit: 'Eichel', rank: 'J', label: 'Buur (20 pts)', classes: 'is-buur' },
      { suit: 'Eichel', rank: '9', label: 'Nell (14 pts)', classes: 'is-nell' },
    ],
  },
  {
    badge: 'Playing',
    title: 'Playing a Trick',
    body: `
      <p>Each trick consists of one card from each player, played clockwise.
      The player who wins the trick leads the next one.</p>
      <p>The key rule: <strong>you must follow suit</strong> if you can.
      If the lead card is Eichel, you must play an Eichel card if you have one.</p>
      <p>If you cannot follow suit, you may play any card — including trump.</p>
      <p>One exception: <strong>the Buur can always be played</strong>, even if
      you could follow the lead suit. You are never forced to sacrifice it.</p>
    `,
  },
  {
    badge: 'Winning',
    title: 'Who Wins Each Trick?',
    body: `
      <p>The highest card of the lead suit wins — unless someone played trump.
      The highest trump card wins over all non-trump cards.</p>
      <p>Within trump: Buur &gt; Nell &gt; A &gt; K &gt; Q &gt; 10 &gt; 8 &gt; 7 &gt; 6</p>
      <p>Within a normal suit: A &gt; K &gt; Q &gt; J &gt; 10 &gt; 9 &gt; 8 &gt; 7 &gt; 6</p>
      <p>Cards of a third suit (not lead, not trump) <em>never win</em>.</p>
    `,
  },
  {
    badge: 'Scoring',
    title: 'Card Point Values',
    body: `
      <p>After all 9 tricks are played, the teams score the card values in the
      tricks they won:</p>
      <ul>
        <li>Ace: 11 pts &nbsp;·&nbsp; Ten: 10 pts &nbsp;·&nbsp; King: 4 pts</li>
        <li>Queen: 3 pts &nbsp;·&nbsp; Jack: 2 pts &nbsp;·&nbsp; 9/8/7/6: 0 pts</li>
        <li>Trump Jack (Buur): 20 pts &nbsp;·&nbsp; Trump Nine (Nell): 14 pts</li>
      </ul>
      <p><strong>Last trick bonus:</strong> +5 points for winning the final trick.</p>
      <p><strong>Match bonus:</strong> +100 points if you win all 9 tricks.</p>
      <p>Total available per round: 157 points (or 257 with match bonus).</p>
    `,
  },
  {
    badge: 'Winning the Game',
    title: 'Reaching 1000',
    body: `
      <p>The game is played over multiple rounds. The first team to reach
      <strong>1000 points</strong> wins the game.</p>
      <p>If both teams cross 1000 in the same round, the team with the
      higher total wins.</p>
      <p>A typical game lasts 6–9 rounds depending on how the cards fall.</p>
    `,
  },
  {
    badge: 'Strategy',
    title: 'Basic Tips',
    body: `
      <ul>
        <li>Choose trump if you hold <strong>Buur + Nell</strong> — that's 34 points secured.</li>
        <li>When your partner is winning a trick, throw in a <strong>high-value card</strong>
            to gift them points.</li>
        <li>Avoid leading into suits where opponents are strong.</li>
        <li>Save the Buur for when it wins a high-value trick, not just any trick.</li>
        <li>In Obenabe, load up on Aces before choosing. In Undeufe, Sixes are gold.</li>
      </ul>
    `,
  },
  {
    badge: 'Ready!',
    title: "You're Ready to Play",
    body: `
      <p>That covers everything you need to know to play Schieber Jass.
      The best way to learn is to play — the rules will become second nature
      after a few rounds.</p>
      <p>Head to the lobby to create a room and play against bots,
      or share the room code with friends for a LAN game.</p>
    `,
  },
];

let currentStep = 0;

// ─── Initialisation ──────────────────────────────────────────────────────────

function initTutorial() {
  renderStep(0);
}

// ─── Navigation ──────────────────────────────────────────────────────────────

function nextStep() {
  if (currentStep < TUTORIAL_STEPS.length - 1) {
    goToStep(currentStep + 1);
  }
}

function prevStep() {
  if (currentStep > 0) {
    goToStep(currentStep - 1);
  }
}

function goToStep(n) {
  currentStep = Math.max(0, Math.min(n, TUTORIAL_STEPS.length - 1));
  renderStep(currentStep);
}

// ─── Rendering ───────────────────────────────────────────────────────────────

function renderStep(n) {
  const step = TUTORIAL_STEPS[n];
  const container = document.getElementById('tutorial-content');
  if (!container) return;

  const isLast = n === TUTORIAL_STEPS.length - 1;
  const cardDemoHTML = step.cardDemo
    ? `<div class="tutorial-card-demo">
        ${step.cardDemo.map(cd => `
          <div style="text-align:center">
            ${buildTutorialCard(cd)}
            <div style="margin-top:.5rem;font-size:.8rem;color:var(--cream-400)">
              ${escHtml(cd.label)}
            </div>
          </div>
        `).join('')}
       </div>`
    : '';

  container.innerHTML = `
    <div class="tutorial-step active">
      <div class="tutorial-header">
        <span class="tutorial-step-badge">
          Step ${n + 1} / ${TUTORIAL_STEPS.length} — ${step.badge}
        </span>
        <h2 class="tutorial-title">${step.title}</h2>
      </div>
      <div class="tutorial-body">
        ${step.body}
        ${cardDemoHTML}
      </div>
      <div class="tutorial-nav">
        <button class="btn btn-secondary" onclick="prevStep()"
          ${n === 0 ? 'disabled' : ''}>← Back</button>

        <div class="tutorial-progress">
          ${TUTORIAL_STEPS.map((_, i) =>
            `<div class="tutorial-dot ${i === n ? 'active' : ''}"
                  onclick="goToStep(${i})" style="cursor:pointer"></div>`
          ).join('')}
        </div>

        ${isLast
          ? `<a href="/" class="btn btn-primary">Play Now →</a>`
          : `<button class="btn btn-primary" onclick="nextStep()">Next →</button>`
        }
      </div>
    </div>
  `;
}

function buildTutorialCard(cd) {
  const SUIT_SYMBOLS = { Eichel:'♣', Schilte:'♦', Schelle:'♠', Rose:'♥' };
  const sym = SUIT_SYMBOLS[cd.suit] || cd.suit[0];
  const classes = ['card', `suit-${cd.suit}`, cd.classes || ''].filter(Boolean).join(' ');
  return `
    <div class="${classes}" style="margin:0 auto">
      <div class="card-rank-top">
        <span>${escHtml(cd.rank)}</span>
        <span class="card-suit-icon">${sym}</span>
      </div>
      <div class="card-suit-center">${sym}</div>
      <div class="card-rank-bot">
        <span>${escHtml(cd.rank)}</span>
        <span class="card-suit-icon">${sym}</span>
      </div>
    </div>
  `;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
