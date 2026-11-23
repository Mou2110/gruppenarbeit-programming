# Prophecy

[![Tests](https://github.com/Mou2110/gruppenarbeit-programming/actions/workflows/tests.yml/badge.svg)](https://github.com/Mou2110/gruppenarbeit-programming/actions/workflows/tests.yml)

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

We started from four parts, one per person, and later each of us added features to their own area
(see the merged pull requests for the details).

| Part | Responsible | Started with | Added later | Main files |
|---|---|---|---|---|
| 1 · Game logic | Erikwinova | Cards, rules, trick winner, game flow, scoring, bots | Deployment on Render, seat order at the table, layout fixes, Jester card | `game/cards.py`, `rules.py`, `scoring.py`, `engine.py`, `bots.py` |
| 2 · Accounts & statistics | Mou2110 | Sign-up / sign-in, password hashing, saving to SQLite / PostgreSQL | Leaderboard, stats page (form, streaks), friends page, Play again, time limit, CR7 card, gold look of lobby and pages, table polish, Safari fix, Wizard card | `game/accounts.py`, `persistence.py`, `leaderboard.py`, `views/stats.py`, `views/leaderboard.py` |
| 3 · Multiplayer | 83675-Coder | Lobbies, ready status, bot moves, chat, restoring after a restart, hosting | Leaving counts as last place, friends list, invites, bot levels, removing players, Shapeshifter card | `game/lobby.py`, `game/presence.py`, `views/invites.py` |
| 4 · User interface | mandaguy12 | Start page, lobby, game table, card design, animations, server start | Player profiles, rules during the game, card illustrations, start page artwork, table redesign | `views/`, `static/`, `main.py` |

The parts build on each other: 1 and 2 are independent, 3 uses 1 and 2, and the interface (4) uses everything.

```
views/ (4)  ──►  game/lobby.py (3)  ──►  game/engine.py … (1)
                        └──────────►  game/accounts.py, persistence.py (2)
```

## Project structure

```
main.py                 starts the server and defines the pages (/, /lobby/<code>, /stats, /friends, /leaderboard, /players/<name>)
game/                   everything that works without a browser
  cards.py, rules.py    the cards and the rules (who wins a trick, which cards may be played)
  engine.py, scoring.py one game from dealing to the final score
  bots.py               computer players (levels: normal, spiteful, ruthless)
  lobby.py              lobbies, bots taking turns, time limit, chat, leaving, play again
  accounts.py           usernames, password hashing (scrypt), sign-in tokens, lockout after 5 wrong passwords
  persistence.py        storage: SQLite locally, PostgreSQL (Supabase) online via DATABASE_URL
  leaderboard.py        ranking and totals per account
  presence.py           who is online, invitations
views/                  the pages (NiceGUI): start, lobby, table, stats, leaderboard, rules
static/                 styles.css, card artwork, small browser effects (table-fx.js)
tests/                  automatic tests (pytest), one file per topic
```

**Where the data is stored:** lobbies and running games live in the server's memory and are saved to the database
after every change, so they survive a restart. Accounts (only the password hash), sign-in tokens (only their hash),
finished games and friends are stored in the database. Secrets such as `DATABASE_URL` are set on Render, never in
the repository.

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

GitHub runs all tests on every push and pull request (tab "Actions", badge at the top). All tests pass on `main`.

**What the tests cover:** 318 test functions in 33 files (448 test cases, because many run with several
inputs, e.g. for 3, 4, 5 and 6 players): the game rules and scoring, special cards, bots and their levels, accounts
and passwords, lobbies (joining, ready, leaving, removing players, bots taking over, chat limits, time limit),
saving and restoring games, friends and invitations, and the leaderboard and stats numbers. For each of these there
are tests for allowed actions, rejected actions (wrong turn, invalid bid, unknown player, wrong password, invalid
time limit) and edge cases (ties, too few players, empty data, a whole game played by bots).

**What they do not cover:** how the pages look (layout, colours, phone vs. laptop) is checked by hand in the
browser. The logic behind the pages is tested, and a few page tests check that pages and dialogs show the right
buttons and texts.

## Working together

1. Accept the invitation to the repository and clone it (e.g. with GitHub Desktop).
2. Create a new branch for every change – do not work directly on `main`.
3. Write the tests first, then the code (rules for coding agents: `AGENTS.md`).
4. Commit, publish the branch and open a **pull request** into `main`. GitHub runs all tests on it.
5. Usually another member reviews and merges it (`CODEOWNERS` asks the owner of the changed files).
   In the last days before the deadline we merged small fixes ourselves once the tests passed, to save time.

## Card artwork

The special-card illustrations and the four suit motifs are AI-generated artwork
created for this project with OpenAI's image generation tool. The app adds card
ranks and labels separately. The prophet portrait on the start page is AI-generated as well. The CR7 bonus card (`static/card-art/cr7.svg`) is a simple
vector drawing made for this project, not a photo.
The Wizard cards (`static/card-art/wizard-moritz.jpg`) show team member Moritz as a wizard: an AI-generated
portrait made with ChatGPT from his own photo, with his consent.
The Shapeshifter card (`static/card-art/shapeshifter-keno.jpg`) shows team member Keno, half man and half wolf
spirit: also an AI-generated portrait made with ChatGPT from his own photo, with his consent.
The Jester cards (`static/card-art/jester-erik.jpg`) show team member Erik as a jester: a complete AI-generated card
(frame, "J" and name included) made with ChatGPT from his own photo, with his consent.
The Fairy cards (`static/card-art/fairy-jakob.jpg`) show team member Jakob as the Fairy: an AI-generated portrait,
used with his consent.

## Features

**Playing**
- Wizard rules with the special cards Shapeshifter, Dragon, Fairy, Bomb, Werewolf, Juggler and Cloud, plus the optional bonus card CR7 (always wins, even against the Bomb)
- Clairvoyance in round 1; bids must not add up to the number of tricks
- Lobbies with a 4-character code or share link; the host chooses special cards, rules and the time limit, adds bots (normal, spiteful, ruthless) and can remove players
- A clear note while players are missing (a game needs 3 to 6 players)
- Practice against bots: pick the table size and the bot level, the game starts right away
- Time limit per move: off or 0:30–5:00 in half minutes (default 2:00), countdown in the last 30 seconds, none against bots only
- At the table: the trump card in the middle, the seat order, the card that is winning the trick and its player, an explanation pop-up for every special card, the rules during the game, a scoreboard with your own column highlighted, card-style buttons when choosing a suit, and at the end a podium for the first three (crown for the winner) with "Play again"
- Games survive server restarts; a player who leaves is replaced by a bot and counts as last place
- Chat in the lobby and at the table

**Accounts and statistics**
- Optional accounts; "Your games" to rejoin from any device; a failed sign-in offers to create the account
- Stats page with totals, the last 10 games as a form row ("2nd of 4") and win streaks
- Leaderboard (at least 5 finished games), sortable by every statistic, ties share a place; player profiles
- Friends page with online status; friends who are online can be invited into a lobby with a pop-up

**Look**
- One dark and gold design on every page, for phones and laptops (also checked in Safari)
- AI-generated card artwork, with all four team members on cards: the Wizard, the Jester, the Shapeshifter and the Fairy
