# Jass — Project Construction Plan

## Overview

This document describes **what to build, in what order, and where each piece lives** in the project architecture. Every phase builds on the previous one — nothing in a later phase should be started before its dependencies are solid.

---

## Architecture Map

A quick reference for where things live before diving into phases:

```
jass/
├── server/
│   ├── main.py                  # FastAPI app entry point, mounts routes & websockets
│   ├── shared/
│   │   ├── types.py             # All Pydantic models (Card, Player, GameState, ...)
│   │   ├── constants.py         # Suits, ranks, scores, game limits
│   │   └── events.py            # WebSocket event name constants
│   ├── game/
│   │   ├── deck.py              # Deck building, shuffling, dealing
│   │   ├── rules.py             # Legal move validation
│   │   ├── scoring.py           # Trick & game scoring
│   │   ├── engine.py            # Game loop, turn management
│   │   └── variants/
│   │       ├── base.py          # Abstract variant interface
│   │       ├── schieber.py      # First variant to implement
│   │       └── coiffeur.py      # Second variant
│   ├── bots/
│   │   ├── base.py              # Abstract bot interface
│   │   ├── random_bot.py        # Trivial bot, used for testing
│   │   └── rule_based_bot.py    # Smarter bot with Jass heuristics
│   ├── rooms/
│   │   └── room_manager.py      # Lobby: create/join/leave rooms
│   └── sockets/
│       └── handlers.py          # WebSocket event routing
├── client/
│   ├── templates/               # Jinja2 HTML (home, game, tutorial)
│   └── static/
│       ├── css/main.css         # Styles
│       └── js/
│           ├── socket.js        # WS client connection
│           ├── game.js          # Rendering & state management
│           └── tutorial.js      # Tutorial step controller
└── tests/
    ├── test_deck.py
    ├── test_rules.py
    ├── test_scoring.py
    └── test_variants/
```

---

## Dependency Graph

The following shows what each layer depends on. Build strictly top-to-bottom.

```
shared/types.py & constants.py        ← foundation, no dependencies (done)
        │
        ▼
game/deck.py                          ← depends on types + constants
        │
        ▼
game/variants/base.py                 ← abstract interface, depends on types
        │
        ▼
game/rules.py + game/scoring.py       ← depend on deck + variant interface
        │
        ▼
game/variants/schieber.py             ← first concrete variant
        │
        ▼
game/engine.py                        ← orchestrates all of the above
        │
        ▼
bots/base.py → bots/random_bot.py     ← depend on engine + types
        │
        ▼
rooms/room_manager.py                 ← depends on types + engine
        │
        ▼
shared/events.py + sockets/handlers.py  ← depend on everything above
        │
        ▼
server/main.py                        ← wires it all together
        │
        ▼
client/static/js/ + client/templates/ ← depend on events.py for WS contract
        │
        ▼
Tutorial, additional variants, better bots   ← built last, on stable base
```

---

## Phase 1 — Foundation (Data & Types)

**Goal:** Define the shared vocabulary the entire codebase speaks.  
**Files:** `server/shared/types.py`, `server/shared/constants.py`

Nothing else can be written without this. Every other module imports from here.

### What to implement

- `Card` — suit + rank, Pydantic model
- `Player` — id, name, hand (list of Cards), is_bot flag
- `Trick` — list of cards played, winner id
- `Room` — id, list of players, max_players
- `GameState` — the complete snapshot of a game at any moment: room, players, current trick, all tricks, trump suit, whose turn, variant name, scores, game_over flag
- `Variant` — lightweight model, name only (logic lives in variant classes)
- `constants.py` — SUITS, RANKS, MAX_PLAYERS, WINNING_SCORE

### Done when

- All models import cleanly with no errors
- A `GameState` can be instantiated and serialized to JSON via `.model_dump()`

---

## Phase 2 — Deck

**Goal:** Build, shuffle, and deal a valid 36-card Swiss Jass deck.  
**File:** `server/game/deck.py`

### What to implement

- `build_deck()` → produces exactly 36 cards (9 ranks × 4 suits)
- `shuffle(deck)` → returns a shuffled copy
- `deal(deck, num_players)` → splits deck into equal hands

### Tests: `tests/test_deck.py`

- Deck has 36 cards
- No duplicate cards
- Deal to 4 players gives 9 cards each
- Shuffle changes order (probabilistic — run several times)

### Done when

All tests pass.

---

## Phase 3 — Variant Interface & First Variant (Schieber)

**Goal:** Define the contract every game variant must fulfill, then implement Schieber.  
**Files:** `server/game/variants/base.py`, `server/game/variants/schieber.py`

### What to implement in `base.py`

Abstract class `BaseVariant` with these abstract methods:
- `get_legal_moves(state, player_id) → list[Card]`
- `score_trick(trick, state) → int`
- `score_game(state) → dict`
- `is_game_over(state) → bool`

### What to implement in `schieber.py`

Schieber is the standard variant and the best starting point — implement the full rule set:
- Trump suit selection (Schellen, Eichel, Rose, Schilte, Obenabe, Undeufe)
- Card ranking (trump cards rank differently, Nell and Buur are special)
- Legal move rules (must follow suit, can trump, etc.)
- Trick-point values per card (including trump bonuses)
- "Weis" (declarations) — can be deferred to a later phase
- Winning condition: first team to 1000 points

### Tests: `tests/test_variants/test_schieber.py`

- Trump card beats non-trump of the same suit
- Buur (J of trump) beats all other trump cards
- Nell (9 of trump) beats all trump except Buur
- Legal moves correctly exclude illegal plays
- Trick scoring returns correct point totals

### Done when

Schieber passes all rule tests and a complete game can be simulated in a Python script with no UI.

---

## Phase 4 — Rules & Scoring Helpers

**Goal:** Extract reusable rule and scoring logic that variants share.  
**Files:** `server/game/rules.py`, `server/game/scoring.py`

Schieber will reveal common patterns. Refactor shared logic here so later variants don't duplicate it.

### What to implement

`rules.py`:
- `get_legal_moves(state, player_id, variant) → list[Card]` — delegates to variant, adds common checks
- `is_legal(state, player_id, card, variant) → bool`

`scoring.py`:
- `score_trick(trick, variant) → int`
- `score_game(tricks, variant) → dict`
- `add_last_trick_bonus(score) → int` — the +5 for taking the last trick

### Done when

Schieber uses these helpers and all existing tests still pass.

---

## Phase 5 — Game Engine

**Goal:** The authoritative game loop that drives a full game from start to finish.  
**File:** `server/game/engine.py`

This is the core of the server. The engine holds game state, validates actions, advances turns, and emits state updates.

### What to implement

- `GameEngine(state, variant)` — constructor takes initial state and variant instance
- `start()` — deals cards, picks first player, sets phase to "trump selection"
- `set_trump(player_id, suit)` — records trump choice, advances to playing phase
- `play_card(player_id, card)` — validates legality, applies card to trick, advances turn; if trick complete, scores it and starts next trick; if game over, finalizes scores
- `get_state_for_player(player_id)` — returns a view of GameState with other players' hands hidden

### Done when

A complete 4-player Schieber game can be run end-to-end in a Python script: deal → set trump → play 36 cards → final scores.

---

## Phase 6 — Bots

**Goal:** AI players that can fill seats so solo and partial-lobby play works.  
**Files:** `server/bots/base.py`, `server/bots/random_bot.py`, `server/bots/rule_based_bot.py`

Bots implement the same interface as human players. The engine never needs to know if it's talking to a human or a bot.

### What to implement

`base.py`:
- `BaseBot(player_id)` — abstract, one method: `choose_card(state, legal_moves) → Card`

`random_bot.py`:
- `RandomBot` — picks a random card from legal_moves. Simple but useful for testing.

`rule_based_bot.py` (implement after RandomBot works):
- Play the highest-value trump when winning is certain
- Avoid gifting high-value cards to opponents
- Play low cards when partner is winning the trick
- Trump only when necessary

### Done when

A full 4-bot game runs to completion with valid moves and correct scoring.

---

## Phase 7 — Room Manager

**Goal:** Manage lobbies — players creating and joining game rooms.  
**File:** `server/rooms/room_manager.py`

### What to implement

- `create_room(room_id) → Room`
- `join_room(room_id, player) → Room`
- `leave_room(room_id, player_id) → Room`
- `get_room(room_id) → Room`
- `fill_with_bots(room_id)` — adds RandomBots to empty seats
- `delete_room(room_id)`
- `list_rooms() → list[Room]` — for the lobby browser

### Done when

Multiple rooms can be created, players can join/leave, and bots fill empty seats.

---

## Phase 8 — WebSocket Layer

**Goal:** Connect all server logic to the network so clients can play.  
**Files:** `server/shared/events.py`, `server/sockets/handlers.py`, `server/main.py`

### What to implement

`events.py` — define string constants for every event type:
- Client → Server: `join_room`, `leave_room`, `start_game`, `play_card`, `choose_trump`
- Server → Client: `room_updated`, `game_started`, `state_updated`, `trick_complete`, `game_over`, `error`

`handlers.py`:
- `handle_event(websocket, event)` — routes incoming events to room manager or game engine
- `broadcast(room_id, event)` — sends an event to all players in a room
- Each player gets only their own hand (use `get_state_for_player`)

`main.py`:
- Mount `/ws/{room_id}` WebSocket endpoint
- Serve Jinja2 templates at `/`, `/game/{room_id}`, `/tutorial`
- Register handlers



### Done when

Two browser tabs can connect, join the same room, and play a complete game against bots via WebSocket messages logged to the console.

The server is now fully functional. 

Run it with  

        uvicorn server.main:app --reload 

and it will accept WebSocket connections.

---

## Phase 9 — Frontend

**Goal:** A playable game UI in the browser.  
**Files:** `client/templates/`, `client/static/js/`, `client/static/css/`

Build the UI after the WebSocket layer is stable — the event contract is the API.

### Templates (Jinja2)

- `home.html` — create room, join room by ID, browse open rooms
- `game.html` — game board layout, loads `socket.js` and `game.js`
- `tutorial.html` — step-by-step Jass rules guide, loads `tutorial.js`

### JavaScript

`socket.js`:
- Open WebSocket connection to `/ws/{room_id}`
- `sendEvent(type, payload)` helper
- Route incoming events to `game.js` handler functions

`game.js`:
- `render(state)` — draw the table, hands, current trick, scores
- Handle `state_updated` → call render
- Handle `trick_complete` → animate trick being taken
- Handle `game_over` → show score screen
- Card click → `sendEvent('play_card', { card })`
- Trump selection UI

`tutorial.js`:
- Step array with text + optional card illustration
- `nextStep()` / `prevStep()` navigation

### CSS (`main.css`)

- Green felt table background
- Card layout for 4-player positions (bottom = you, others around the table)
- Hand display with fan/spread layout
- Responsive for desktop and tablet

### Done when

A human player can open the browser, create a room, play a complete Schieber game against 3 bots, and see the final scores.

--> maybe take all the files out of the folders to work

run 

        uvicorn server.main:app --reload
        
open 

        http://localhost:8000 
        
and you have a fully playable game. 

---

## Phase 10 — Additional Variants

**Goal:** Add Coiffeur, Differenzler, and optionally Molotow.  
**Files:** `server/game/variants/coiffeur.py`, `server/game/variants/differenzler.py`

Each variant only needs to implement `BaseVariant`. The engine, room manager, and sockets don't change.

### Coiffeur

Each player must play every game type (Obenabe, Undeufe, each suit as trump) once over the course of the game. Points are doubled on a second play of the same type ("Coiffeur"). Needs a tracker for which types each player has used.

### Differenzler

Each player predicts their score before the round. Points are awarded or deducted based on the difference between prediction and actual score. Requires a "prediction" phase before card play.

### Done when

Both variants can be selected from the lobby and play to completion.

---

## Phase 11 — Polish & Tutorial

**Goal:** Make the game accessible to new players and pleasant to use.

- **Tutorial mode** — step through rules with interactive card examples
- **Animations** — card play, trick collection, score reveal
- **Sound effects** — card play, trick win, game over
- **Multilingual support** — DE/FR/IT/EN (Swiss national languages)
- **LAN discovery** — list rooms on the local network without a lobby server
- **Mobile layout** — portrait mode card hand for phone play

---

## Timeline Summary

| Phase | What | Depends On | status |
|-------|------|------------|--------|
| 1 | Types & constants | nothing | Done|
| 2 | Deck | Phase 1 | Done|
| 3 | Variant interface + Schieber | Phase 2 | Done |
| 4 | Rules & scoring helpers | Phase 3 |Done|
| 5 | Game engine | Phase 4 |Done|
| 6 | Bots | Phase 5 |Done|
| 7 | Room manager | Phase 5 |Done|
| 8 | WebSocket layer | Phases 6 + 7 |Done|
| 9 | Frontend UI | Phase 8 |Done|
| 10 | Additional variants | Phase 9 |Done|
| 11 | Polish & tutorial | Phase 10 ||

---

## Testing Strategy

- Write tests for **Phases 1–6 before writing the phase above them**. The engine is complex enough that untested lower layers will cause hard-to-trace bugs.
- The WebSocket layer (Phase 8) is best tested with integration tests that spin up the FastAPI app with `httpx` and `pytest-asyncio`.
- Frontend can be manually tested in early phases; add Playwright end-to-end tests when the UI is stable.

---

## First Steps (Today)

1. Run `python generate_jass_project.py` to scaffold the folder structure
2. Create and activate a virtual environment: `python -m venv venv && source venv/bin/activate`
3. Install dependencies: `pip install -r server/requirements.txt`
4. Start with `server/shared/types.py` — fill in all Pydantic models
5. Write `server/game/deck.py` and make `tests/test_deck.py` pass
6. Move on to `variants/base.py` and begin Schieber
