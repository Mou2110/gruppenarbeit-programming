# Prophecy

A digital multiplayer trick-taking card game based on the rules of *Wizard* (25th anniversary edition),
including special cards – built with Python and NiceGUI. Playable online via Render; game states and
accounts are stored in a Supabase (PostgreSQL) database.

**Live app:** TODO: add the Render URL here

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

## Running the app

NiceGUI needs Python 3.11 or newer. [uv](https://docs.astral.sh/uv/) takes care of that:

```bash
uv run --python 3.13 --with-requirements requirements.txt python main.py
```

Then open http://localhost:8080 in the browser. Every browser tab is a separate player;
**Practice against bots** starts a game against three computer opponents right away.
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

**What they do not cover:** the page layout itself (`views/start.py`, `views/lobby.py`, `views/table.py`)
is checked by hand in the browser, not by automatic tests. The logic behind the pages is tested.

## Working together

1. Accept the invitation to the repository and clone it (e.g. with GitHub Desktop).
2. Create a new branch for every change – do not work directly on `main`.
3. Commit, publish the branch and open a **pull request** into `main`.
4. Merge once the others have reviewed it and all tests pass.

## Features

- Wizard rules with the special cards Shapeshifter, Dragon, Fairy, Bomb, Werewolf, Juggler and Cloud
- Clairvoyance in round 1; bids must not add up to the number of tricks
- Lobbies with a 4-character code, bots and chat
- Games survive server restarts; if a player is away, the game waits for them
- Optional accounts with statistics and "Your games" to rejoin
- Leaderboard: win rate by default (at least 5 finished games), sortable by every statistic, ties share a place
- Player profiles and, on the stats page, the last 10 games as a form row with win streaks
