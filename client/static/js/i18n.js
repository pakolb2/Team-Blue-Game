/**
 * client/static/js/i18n.js
 * --------------------------
 * Multilingual support for DE / FR / IT / EN.
 * Swiss national languages — Jass is played across all four.
 *
 * Usage:
 *   t('choose_trump')           → "Trumpf wählen"  (in German)
 *   t('score_label', {n: 850})  → "850 Punkte"
 *   setLocale('fr')
 *   getLocale()                 → 'fr'
 */

const TRANSLATIONS = {
  en: {
    // Navigation
    lobby:           'Lobby',
    how_to_play:     'How to Play',

    // Lobby
    your_name:       'Your Name',
    name_placeholder:'Enter your name…',
    create_room:     'Create New Room',
    join_room:       'Join Room',
    room_code:       'Room Code',
    room_code_hint:  'e.g. A3B9C1',
    open_rooms:      'Open Rooms',
    no_open_rooms:   'No open rooms yet.\nCreate one above!',
    players_count:   '{n}/{max} players',
    join:            'Join',
    copy_code:       'Copy Code',
    copied:          'Copied!',
    start_game:      'Start Game',
    waiting_for:     'Waiting for players…',
    share_code_hint: 'Share the room code with friends, or start with bots filling empty seats.',
    room_code_label: 'Room Code',
    bot_label:       '(bot)',
    ready:           'ready',
    away:            'away',
    empty_seat:      'Empty seat',

    // Game board
    score:           'Score',
    trump:           'Trump',
    tricks:          'Tricks',
    status:          'Status',
    log:             'Log',
    you:             'You',
    team_a:          'Team A',
    team_b:          'Team B',
    choosing_trump:  'Choosing trump…',

    // Phases
    phase_waiting:      'Waiting for players…',
    phase_trump_select: 'Choosing trump…',
    phase_playing:      'Playing',
    phase_scoring:      'Round complete',
    phase_finished:     'Game over',

    // Status messages
    your_turn_trump:   'Your turn to choose trump.',
    waiting_trump:     '{player} is choosing trump…',
    your_turn_play:    'Your turn — click a card to select it.',
    selected_card:     'Click {rank} of {suit} again to play, or choose a different card.',
    waiting_play:      'Waiting for {player}…',
    round_starting:    'Next round starting…',

    // Trump picker
    choose_trump:    'Choose Trump',
    trump_eichel:    'Eichel',
    trump_schilte:   'Schilte',
    trump_schelle:   'Schelle',
    trump_rose:      'Rose',
    trump_obenabe:   'Obenabe',
    trump_undeufe:   'Undeufe',

    // Card suit names
    suit_eichel:     'Eichel',
    suit_schilte:    'Schilte',
    suit_schelle:    'Schelle',
    suit_rose:       'Rose',

    // Toasts / notifications
    game_started:    'Game started!',
    trick_won:       '{player} wins the trick (+{pts} pts)',
    you_win_trick:   'You win the trick (+{pts} pts)',
    round_complete:  'Round {n} complete',
    card_selected:   '{rank} of {suit} selected — click again to play',
    reconnecting:    'Reconnecting…',
    disconnected:    'Disconnected from server.',
    connected:       'Connected.',

    // Round banner
    round_complete_title: 'Round {n} complete',
    scores_summary:  'Team A: {a} (+{ar})  ·  Team B: {b} (+{br})',
    dismiss:         'Dismiss',

    // Game over
    victory:         '🏆 Victory!',
    game_over:       'Game Over',
    team_a_wins:     'Team A wins',
    team_b_wins:     'Team B wins',
    return_lobby:    'Return to Lobby',

    // Tricks counter
    tricks_of:       '{n} / 9',

    // Errors
    err_no_room:     'Room not found.',
    err_not_turn:    "It's not your turn.",
    err_illegal:     'That card is not legal to play.',
    err_internal:    'An internal error occurred.',

    // Log entries
    log_game_started:   'Game started — good luck!',
    log_trick:          'Trick → {winner} (+{pts} pts)',
    log_round:          'Round complete. A={a} B={b}',
    log_game_over:      '🏆 Game over! Winner: {winner}',
  },

  de: {
    lobby:           'Lobby',
    how_to_play:     'Spielregeln',
    your_name:       'Dein Name',
    name_placeholder:'Name eingeben…',
    create_room:     'Neuen Raum erstellen',
    join_room:       'Raum beitreten',
    room_code:       'Raumcode',
    room_code_hint:  'z.B. A3B9C1',
    open_rooms:      'Offene Räume',
    no_open_rooms:   'Noch keine offenen Räume.\nOben einen erstellen!',
    players_count:   '{n}/{max} Spieler',
    join:            'Beitreten',
    copy_code:       'Code kopieren',
    copied:          'Kopiert!',
    start_game:      'Spiel starten',
    waiting_for:     'Warte auf Spieler…',
    share_code_hint: 'Teile den Raumcode mit Freunden oder starte mit Bots.',
    room_code_label: 'Raumcode',
    bot_label:       '(Bot)',
    ready:           'bereit',
    away:            'weg',
    empty_seat:      'Freier Platz',
    score:           'Punkte',
    trump:           'Trumpf',
    tricks:          'Stiche',
    status:          'Status',
    log:             'Verlauf',
    you:             'Du',
    team_a:          'Team A',
    team_b:          'Team B',
    choosing_trump:  'Trumpf wird gewählt…',
    phase_waiting:      'Warte auf Spieler…',
    phase_trump_select: 'Trumpf wird gewählt…',
    phase_playing:      'Spielen',
    phase_scoring:      'Runde abgeschlossen',
    phase_finished:     'Spiel vorbei',
    your_turn_trump:   'Du bist dran — wähle Trumpf.',
    waiting_trump:     '{player} wählt Trumpf…',
    your_turn_play:    'Du bist dran — klicke eine Karte.',
    selected_card:     'Nochmals klicken zum Ausspielen oder andere Karte wählen.',
    waiting_play:      'Warte auf {player}…',
    round_starting:    'Nächste Runde startet…',
    choose_trump:    'Trumpf wählen',
    trump_eichel:    'Eicheln',
    trump_schilte:   'Schilten',
    trump_schelle:   'Schellen',
    trump_rose:      'Rosen',
    trump_obenabe:   'Obenabe',
    trump_undeufe:   'Undenufe',
    suit_eichel:     'Eicheln',
    suit_schilte:    'Schilten',
    suit_schelle:    'Schellen',
    suit_rose:       'Rosen',
    game_started:    'Spiel gestartet!',
    trick_won:       '{player} gewinnt den Stich (+{pts} Pkt.)',
    you_win_trick:   'Du gewinnst den Stich (+{pts} Pkt.)',
    round_complete:  'Runde {n} abgeschlossen',
    card_selected:   '{rank} von {suit} gewählt — nochmals klicken',
    reconnecting:    'Verbindung wird wiederhergestellt…',
    disconnected:    'Verbindung zum Server unterbrochen.',
    connected:       'Verbunden.',
    round_complete_title: 'Runde {n} abgeschlossen',
    scores_summary:  'Team A: {a} (+{ar})  ·  Team B: {b} (+{br})',
    dismiss:         'Schliessen',
    victory:         '🏆 Gewonnen!',
    game_over:       'Spiel vorbei',
    team_a_wins:     'Team A gewinnt',
    team_b_wins:     'Team B gewinnt',
    return_lobby:    'Zur Lobby',
    tricks_of:       '{n} / 9',
    err_no_room:     'Raum nicht gefunden.',
    err_not_turn:    'Du bist nicht dran.',
    err_illegal:     'Diese Karte darf nicht gespielt werden.',
    err_internal:    'Ein interner Fehler ist aufgetreten.',
    log_game_started:   'Spiel gestartet — viel Glück!',
    log_trick:          'Stich → {winner} (+{pts} Pkt.)',
    log_round:          'Runde abgeschlossen. A={a} B={b}',
    log_game_over:      '🏆 Spiel vorbei! Gewinner: {winner}',
  },

  fr: {
    lobby:           'Salon',
    how_to_play:     'Règles du jeu',
    your_name:       'Votre nom',
    name_placeholder:'Entrez votre nom…',
    create_room:     'Créer une salle',
    join_room:       'Rejoindre',
    room_code:       'Code de salle',
    room_code_hint:  'ex. A3B9C1',
    open_rooms:      'Salles ouvertes',
    no_open_rooms:   'Aucune salle ouverte.\nCréez-en une ci-dessus !',
    players_count:   '{n}/{max} joueurs',
    join:            'Rejoindre',
    copy_code:       'Copier le code',
    copied:          'Copié !',
    start_game:      'Lancer la partie',
    waiting_for:     'En attente de joueurs…',
    share_code_hint: 'Partagez le code avec vos amis ou jouez contre des bots.',
    room_code_label: 'Code de salle',
    bot_label:       '(bot)',
    ready:           'prêt',
    away:            'absent',
    empty_seat:      'Place libre',
    score:           'Score',
    trump:           'Atout',
    tricks:          'Plis',
    status:          'Statut',
    log:             'Journal',
    you:             'Vous',
    team_a:          'Équipe A',
    team_b:          'Équipe B',
    choosing_trump:  'Choix de l\'atout…',
    phase_waiting:      'En attente de joueurs…',
    phase_trump_select: 'Choix de l\'atout…',
    phase_playing:      'En jeu',
    phase_scoring:      'Manche terminée',
    phase_finished:     'Partie terminée',
    your_turn_trump:   'C\'est votre tour — choisissez l\'atout.',
    waiting_trump:     '{player} choisit l\'atout…',
    your_turn_play:    'C\'est votre tour — cliquez une carte.',
    selected_card:     'Recliquez pour jouer ou choisissez une autre carte.',
    waiting_play:      'En attente de {player}…',
    round_starting:    'Prochaine manche en cours…',
    choose_trump:    'Choisir l\'atout',
    trump_eichel:    'Glands',
    trump_schilte:   'Écus',
    trump_schelle:   'Cloches',
    trump_rose:      'Roses',
    trump_obenabe:   'Obenabe',
    trump_undeufe:   'Undeufe',
    suit_eichel:     'Glands',
    suit_schilte:    'Écus',
    suit_schelle:    'Cloches',
    suit_rose:       'Roses',
    game_started:    'Partie commencée !',
    trick_won:       '{player} remporte le pli (+{pts} pts)',
    you_win_trick:   'Vous remportez le pli (+{pts} pts)',
    round_complete:  'Manche {n} terminée',
    card_selected:   '{rank} de {suit} sélectionné — recliquez pour jouer',
    reconnecting:    'Reconnexion en cours…',
    disconnected:    'Déconnecté du serveur.',
    connected:       'Connecté.',
    round_complete_title: 'Manche {n} terminée',
    scores_summary:  'Équipe A : {a} (+{ar})  ·  Équipe B : {b} (+{br})',
    dismiss:         'Fermer',
    victory:         '🏆 Victoire !',
    game_over:       'Partie terminée',
    team_a_wins:     'L\'équipe A gagne',
    team_b_wins:     'L\'équipe B gagne',
    return_lobby:    'Retour au salon',
    tricks_of:       '{n} / 9',
    err_no_room:     'Salle introuvable.',
    err_not_turn:    'Ce n\'est pas votre tour.',
    err_illegal:     'Cette carte ne peut pas être jouée.',
    err_internal:    'Une erreur interne est survenue.',
    log_game_started:   'Partie commencée — bonne chance !',
    log_trick:          'Pli → {winner} (+{pts} pts)',
    log_round:          'Manche terminée. A={a} B={b}',
    log_game_over:      '🏆 Partie terminée ! Gagnant : {winner}',
  },

  it: {
    lobby:           'Sala d\'attesa',
    how_to_play:     'Regole del gioco',
    your_name:       'Il tuo nome',
    name_placeholder:'Inserisci il nome…',
    create_room:     'Crea una stanza',
    join_room:       'Unisciti',
    room_code:       'Codice stanza',
    room_code_hint:  'es. A3B9C1',
    open_rooms:      'Stanze aperte',
    no_open_rooms:   'Nessuna stanza aperta.\nCreane una sopra!',
    players_count:   '{n}/{max} giocatori',
    join:            'Unisciti',
    copy_code:       'Copia codice',
    copied:          'Copiato!',
    start_game:      'Inizia partita',
    waiting_for:     'In attesa di giocatori…',
    share_code_hint: 'Condividi il codice con gli amici o gioca contro i bot.',
    room_code_label: 'Codice stanza',
    bot_label:       '(bot)',
    ready:           'pronto',
    away:            'assente',
    empty_seat:      'Posto libero',
    score:           'Punteggio',
    trump:           'Briscola',
    tricks:          'Prese',
    status:          'Stato',
    log:             'Diario',
    you:             'Tu',
    team_a:          'Squadra A',
    team_b:          'Squadra B',
    choosing_trump:  'Scelta della briscola…',
    phase_waiting:      'In attesa di giocatori…',
    phase_trump_select: 'Scelta della briscola…',
    phase_playing:      'In gioco',
    phase_scoring:      'Mano terminata',
    phase_finished:     'Partita terminata',
    your_turn_trump:   'Tocca a te — scegli la briscola.',
    waiting_trump:     '{player} sceglie la briscola…',
    your_turn_play:    'Tocca a te — clicca una carta.',
    selected_card:     'Clicca di nuovo per giocare o scegli un\'altra carta.',
    waiting_play:      'In attesa di {player}…',
    round_starting:    'Prossima mano in arrivo…',
    choose_trump:    'Scegli la briscola',
    trump_eichel:    'Ghiande',
    trump_schilte:   'Scudi',
    trump_schelle:   'Campane',
    trump_rose:      'Rose',
    trump_obenabe:   'Obenabe',
    trump_undeufe:   'Undeufe',
    suit_eichel:     'Ghiande',
    suit_schilte:    'Scudi',
    suit_schelle:    'Campane',
    suit_rose:       'Rose',
    game_started:    'Partita iniziata!',
    trick_won:       '{player} vince la presa (+{pts} pt)',
    you_win_trick:   'Hai vinto la presa (+{pts} pt)',
    round_complete:  'Mano {n} terminata',
    card_selected:   '{rank} di {suit} selezionato — clicca di nuovo per giocare',
    reconnecting:    'Riconnessione in corso…',
    disconnected:    'Disconnesso dal server.',
    connected:       'Connesso.',
    round_complete_title: 'Mano {n} terminata',
    scores_summary:  'Squadra A: {a} (+{ar})  ·  Squadra B: {b} (+{br})',
    dismiss:         'Chiudi',
    victory:         '🏆 Vittoria!',
    game_over:       'Partita terminata',
    team_a_wins:     'Vince la Squadra A',
    team_b_wins:     'Vince la Squadra B',
    return_lobby:    'Torna alla sala',
    tricks_of:       '{n} / 9',
    err_no_room:     'Stanza non trovata.',
    err_not_turn:    'Non è il tuo turno.',
    err_illegal:     'Questa carta non può essere giocata.',
    err_internal:    'Si è verificato un errore interno.',
    log_game_started:   'Partita iniziata — buona fortuna!',
    log_trick:          'Presa → {winner} (+{pts} pt)',
    log_round:          'Mano terminata. A={a} B={b}',
    log_game_over:      '🏆 Partita terminata! Vincitore: {winner}',
  },
};

// ---------------------------------------------------------------------------
// Locale management
// ---------------------------------------------------------------------------

const SUPPORTED_LOCALES = ['en', 'de', 'fr', 'it'];
const DEFAULT_LOCALE    = 'de';   // Switzerland defaults to German

let _locale = DEFAULT_LOCALE;

/** Detect the best locale from browser preferences. */
function detectLocale() {
  const saved = localStorage.getItem('jass_locale');
  if (saved && SUPPORTED_LOCALES.includes(saved)) return saved;

  const browser = navigator.language || navigator.userLanguage || '';
  const lang = browser.split('-')[0].toLowerCase();
  return SUPPORTED_LOCALES.includes(lang) ? lang : DEFAULT_LOCALE;
}

/** Get the active locale code. */
function getLocale() { return _locale; }

/**
 * Set the active locale and persist it.
 * Triggers a full re-render if the page uses data-i18n attributes.
 */
function setLocale(locale) {
  if (!SUPPORTED_LOCALES.includes(locale)) return;
  _locale = locale;
  localStorage.setItem('jass_locale', locale);
  applyI18n();
}

// ---------------------------------------------------------------------------
// Translation function
// ---------------------------------------------------------------------------

/**
 * Translate a key, substituting {variable} placeholders.
 *
 * @param {string} key      - Translation key
 * @param {object} [vars]   - Substitution variables, e.g. {n: 5, player: 'Alice'}
 * @returns {string}
 *
 * @example
 *   t('your_turn_play')              → "Your turn — click a card to select it."
 *   t('trick_won', {player:'Bob', pts:14}) → "Bob wins the trick (+14 pts)"
 */
function t(key, vars = {}) {
  const dict = TRANSLATIONS[_locale] || TRANSLATIONS[DEFAULT_LOCALE];
  let str = dict[key] ?? TRANSLATIONS[DEFAULT_LOCALE][key] ?? key;

  // Replace {variable} placeholders
  Object.entries(vars).forEach(([k, v]) => {
    str = str.replaceAll(`{${k}}`, v);
  });

  return str;
}

// ---------------------------------------------------------------------------
// DOM auto-translation (data-i18n attributes)
// ---------------------------------------------------------------------------

/**
 * Translate all elements with a data-i18n attribute.
 *
 * Usage in HTML:
 *   <span data-i18n="score"></span>
 *   <button data-i18n="start_game"></button>
 *   <input data-i18n-placeholder="name_placeholder" />
 */
function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.dataset.i18nTitle);
  });
  // Update lang attribute on <html>
  document.documentElement.lang = _locale;
}

// ---------------------------------------------------------------------------
// Language switcher widget
// ---------------------------------------------------------------------------

/**
 * Build and return a language switcher element.
 * Renders as: DE · FR · IT · EN
 */
function buildLanguageSwitcher() {
  const nav = document.createElement('nav');
  nav.className = 'lang-switcher';
  nav.setAttribute('aria-label', 'Language');

  SUPPORTED_LOCALES.forEach((locale, i) => {
    if (i > 0) {
      const sep = document.createElement('span');
      sep.textContent = '·';
      sep.style.cssText = 'color:rgba(255,255,255,.25);margin:0 .3rem';
      nav.appendChild(sep);
    }

    const btn = document.createElement('button');
    btn.textContent = locale.toUpperCase();
    btn.className = `lang-btn ${locale === _locale ? 'lang-active' : ''}`;
    btn.setAttribute('data-locale', locale);
    btn.addEventListener('click', () => {
      setLocale(locale);
      // Re-render active state
      nav.querySelectorAll('.lang-btn').forEach(b => {
        b.classList.toggle('lang-active', b.dataset.locale === locale);
      });
    });
    nav.appendChild(btn);
  });

  return nav;
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

// Detect locale on load
_locale = detectLocale();

// Apply translations once DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', applyI18n);
} else {
  applyI18n();
}
