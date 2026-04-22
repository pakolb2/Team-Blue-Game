# Project Description
    The Game: Swiss Jass

## Content
1. Mission
2. Scope
3. Objectives and success criteria
4. Inputs/Outputs
5. Constraints
6. Risks & mitigation strategies


## 1. Mission
    A short description of one or a few sentences, structured similar to:
    We will build X for Y to enable Z under constraints C.


The goal is to build a web-based implementation of the traditional Swiss card game Jass with all its different game modes for players familiar with or new to the game, enabling local and LAN multiplayer (as well as solo play against bots), supporting multiple game variants and a built-in tutorial.


## 2. Scope
    You will outline the scope, the ”what” and ”how much” of the project:

- In scope 
  - Full implementation of Jass game logic including
    - 2 vs 4 players modes
    - different game modes (Schieber, Differenzler, obe abe, une ufe, ...) 
    - special add-on rules
  - Web-based GUI playable in a browser
  - Local multiplayer (2–4 players on one device, hot-seat style)
  - LAN/local network multiplayer (players on different devices on the same network)
  - (on line/different network multiplayer)
  - there should be a tutorial to learn the game 
  (--> bot opponents needed?)

? Persistent user accounts, leaderboards, or statistics



- Out of scope / non-goals
    - Responsive mobile layout / phone screen support
      - working on diffenrent device sizes (phone vs computer)
    - Native mobile app or app store distribution
      - workin locally on different OS (windows vs MacOS, linuxOS,...)    
    - Online/global multiplayer across different networks`



  
## 3. Objectives and success criteria
    You will define SMART objectives; 
    Specific, Measurable,Achievable, Relevant, and Time-bound.

    The objectives will directly address your projects’ Scientific: 


    - Validity:
    May include analytic benchmarking, error tolerance, application on known datasets, reproducibility, ...

    - Operational performance: 
    Runtime/memory targets, readabilityand reusability,multi-platform operability...

- Validity:
  - All Jass game rules are correctly implemented and verified against known rule references produce correct outcomes in tests
  - A player unfamiliar with Jass can complete the tutorial and play a full game without external help
  - (Bot opponents make legal moves in 100% of cases and play a reasonable strategy (no random-only bots))


- Operational performance:
  - Codebase is modular enough that adding a new game variant requires minimal changes
  - The game interface is fully navigable via keyboard alone (tab focus, arrow keys for card selection, enter to play)
  - ? and all interactive elements have descriptive ARIA labels, meeting WCAG 2.1 AA accessibility standards
  - ? Game state updates (card plays, score changes) render in under 200ms on a local network 





## 4. Inputs/Outputs
    Early on, you will specify (not a full list):
    - Data formats: For example, NetCDF, GeoTIFF, HDF5, CSV, shapefiles, . . .
    - Scale: image size, grid size, timesteps, file sizes, . . .
    - Units/coordinates: meters vs degrees, reference frames, time bases, . . .
    - Metadata: rasters/vectors, plots, reports, logs, . . . or anything produced as outcome of the project.

    While this may change along the way, it will drive the boundaries of
    your project and focus your work.

Inputs:

- Player mouse/touch/key interactions (card selection, trump declaration, game mode choice)
- Game configuration: number of players (2 or 4), chosen Jass variant, add-on rules toggle
- ? Network messages between clients in LAN multiplayer 


Outputs:
- Rendered game table showing cards, scores, current trick, and trump suit in the browser
- Real-time game state synchronization to all connected clients (LAN mode)
- End-of-round and end-of-game score summaries
Tutorial step-by-step UI overlays and prompts

**Scale**: 
36-card Swiss Jass deck, 2 or 4 players, sessions lasting 20–60 minutes, no persistent storage required beyond a single session.




## 5. Constraints
    You will come up with constraints for your project, including, but
    not limited to:
    - Compute: CPU/GPU, RAM limits, . . .
    - Runtime: interactive vs batch
    - Dependencies: libraries, licensing, . . .
    - Data governance: sensitive/embargoed data
    - Platform: Windows, mac, Linux, . . .

- **Platform**: Runs in modern desktop browsers only (Chrome, Firefox, Safari); no mobile layout required
- **Runtime**: Interactive (real-time); all game actions must feel instantaneous locally
- **Dependencies**: Open-source libraries only (e.g. a JS framework for UI, a WebSocket library for LAN); no paid APIs or services
- **Networking**: Session persistence: No persistent storage (database) — game state lives only in memory for the duration of a session; if the host disconnects, the game is lost.
- **Dependencies/Licensing**: All assets (card graphics, fonts, sounds) must be freely licensed (CC0 or similar) — no proprietary artwork.


## 6. Risks & mitigation strategies
    You will come up with potential risks and possible mitigation plans.

| *Risk*                            | *Mitigation* |
| -------------------------         | -----------  |
| Jass rule complexity causing logic bugs           | Write unit tests for each rule variant early; validate against a published Jass rule reference    |
| LAN WebSocket synchronization issues (out-of-order messages, dropped connections)       |   Use a simple authoritative server model (one player hosts); implement a reconnect/rejoin flow    |
|Game state synchronization bugs (clients getting out of sync mid-game e.g. after a brief disconnect)      |   Treat the host as the single source of truth; clients only render, never decide.    |



    
