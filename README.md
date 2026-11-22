# Prophecy

A digital multiplayer trick-taking card game based on the rules of *Wizard* (25th anniversary edition),
including special cards – built with Python and NiceGUI. Playable online via Render; game states and
accounts are stored in a Supabase (PostgreSQL) database.

**Live app:** https://prophecy-game.onrender.com (free Render plan: the first visit after a break can take up to a minute)

## Objectives

- Make *Wizard* playable together online: open the link on any phone or laptop, share a 4-character code, play.
- Implement the full rules correctly, including the special cards, and prove it with automatic tests.
- Never let a game get stuck: bots fill empty seats, a time limit keeps the game moving, and games survive a server restart.
- Give players a reason to come back: optional accounts with statistics, a leaderboard, profiles and friends.

## Team

| Name | Student number | GitHub |
|---|---|---|
| Erik Wischnewski | 81880 | Erikwinova |
| Moritz Gömmel | 78188 | Mou2110 |
| Keno Hartkamp | 83675 | 83675-Coder |
| Jakob Werner Prestel | 78098 | mandaguy12 |

## Responsibilities

| Part | Responsible | Content | Files |
|---|---|---|---|
| 1 · Game logic | Erikwinova | Cards, rules, trick winner, game flow, scoring, bots | `game/cards.py`, `rules.py`, `scoring.py`, `engine.py`, `bots.py` + tests |
| 2 · Accounts & database | Mou2110 | Sign-up / sign-in, password hashing, saving to SQLite / PostgreSQL | `game/accounts.py`, `game/persistence.py`, `tests/test_accounts.py` |
| 3 · Multiplayer | 83675-Coder | Lobbies, ready status, bot moves, chat, restoring after a restart, hosting | `game/lobby.py`, `tests/test_lobby.py`, `tests/test_persistence.py`, `requirements.txt`, `render.yaml` |
| 4 · User interface | mandaguy12 | Start page, lobby, game table, card design, animations, stats, server start | `views/`, `static/styles.css`, `main.py` |

The parts build on each other: 1 and 2 are independent, 3 uses 1 and 2, and the interface (4) uses everything.

```
views/ (4)  ──►  game/lobby.py (3)  ──►  game/engine.py … (1)
                        └──────────►  game/accounts.py, persistence.py (2)
```

## Installation

NiceGUI needs Python 3.11 or newer. [uv](https://docs.astral.sh/uv/) downloads the right Python version and all
packages from `requirements.txt` automatically, so it is the only thing to install:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

(Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`.) Then get the code:

```bash
git clone https://github.com/Mou2110/gruppenarbeit-programming.git
cd gruppenarbeit-programming
```

No database setup is needed locally: a SQLite file is created on the first start.

## Running the app

```bash
uv run --python 3.13 --with-requirements requirements.txt python main.py
```

Then open http://localhost:8080 in the browser. As a guest, every browser tab is a separate player;
**Practice against bots** lets you pick a table of 3–6 players and fills the other seats with computer opponents.
Locally the data is stored in a SQLite file; online it is stored in PostgreSQL (Supabase) via `DATABASE_URL`.

## Tests

```bash
uv run --python 3.13 --with-requirements requirements.txt pytest
```

GitHub runs all tests on every push (tab "Actions"), and `main` only gets changes that pass them.

**What the tests cover:** the game rules and scoring, bots, accounts and passwords, lobbies (joining, ready,
leaving, bots taking over, chat limits), saving and restoring games, and the leaderboard and stats numbers.
For each of these there are tests for allowed actions, rejected actions (wrong turn, invalid bid, unknown
player, wrong password) and edge cases (ties, too few players, empty data).

**What they do not cover:** how the pages look (layout, colours, phone vs. laptop) is checked by hand in the
browser. The logic behind the pages is tested, and a few page tests check that the start page, the rules and the
"Play again" / invite flows show the right buttons and texts.

## Working together

1. Accept the invitation to the repository and clone it (e.g. with GitHub Desktop).
2. Create a new branch for every change – do not work directly on `main`.
3. Commit, publish the branch and open a **pull request** into `main`.
4. Merge once the others have reviewed it and all tests pass.

## Card artwork

The special-card illustrations and the four suit motifs are AI-generated artwork
created for this project with OpenAI's image generation tool. The app adds card
ranks and labels separately. The prophet portrait on the start page is AI-generated as well. The CR7 bonus card (`static/card-art/cr7.svg`) is a simple
vector drawing made for this project, not a photo.
The Wizard cards (`static/card-art/wizard-moritz.jpg`) show team member Moritz as a wizard: an AI-generated
portrait made with ChatGPT from his own photo, with his consent.
The Jester cards (`static/card-art/jester-erik.jpg`) show team member Erik as a jester: a complete AI-generated card
(frame, "J" and name included) made with ChatGPT from his own photo, with his consent.

## Features

- Wizard rules with the special cards Shapeshifter, Dragon, Fairy, Bomb, Werewolf, Juggler and Cloud
- Clairvoyance in round 1; bids must not add up to the number of tricks
- Lobbies with a 4-character code, bots and chat
- Games survive server restarts; a player who leaves is replaced by a bot and counts as last place
- Time limit per move, chosen by the host for each lobby with a dial: off or 0:30–5:00 in half minutes (default 2:00); the countdown appears in the last 30 seconds. Against bots only there is no time limit
- "Play again" at the end of a game, and the rules can be opened during the game
- Optional accounts with statistics and "Your games" to rejoin
- Leaderboard: win rate by default (at least 5 finished games), sortable by every statistic, ties share a place
- Player profiles and, on the stats page, the last 10 games as a form row with win streaks
- Friends list with online status; friends who are online can be invited into a lobby with a popup
- Optional bonus card CR7: always wins the trick, even against the Bomb
