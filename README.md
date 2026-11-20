# Prophecy

A digital multiplayer trick-taking card game based on the rules of *Wizard* (25th anniversary edition),
including special cards – built with Python and NiceGUI. Playable online via Render; game states and
accounts are stored in a Supabase (PostgreSQL) database.

## Team and responsibilities

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

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Then open http://localhost:8080 in the browser. Every browser tab is a separate player;
**Practice against bots** starts a game against three computer opponents right away.

## Tests

```bash
pytest
```

## Working together

1. Accept the invitation to the repository and clone it (e.g. with GitHub Desktop).
2. Create a new branch for every change – do not work directly on `main`.
3. Commit, publish the branch and open a **pull request** into `main`.
4. Merge once the others have reviewed it and all tests pass.

## Card artwork

The special-card illustrations and the four suit motifs are AI-generated artwork
created for this project with OpenAI's image generation tool. The app adds card
ranks and labels separately.

## Features

- Wizard rules with the special cards Shapeshifter, Dragon, Fairy, Bomb, Werewolf, Juggler and Cloud
- Clairvoyance in round 1; bids must not add up to the number of tricks
- Lobbies with a 4-character code, bots and chat
- Games survive server restarts; if a player is away, the game waits for them
- Optional accounts with statistics and "Your games" to rejoin
