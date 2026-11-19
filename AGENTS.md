# Project rules for coding agents

These rules apply to every task in this project. Every coding agent (Claude Code, Codex, …) follows them.
Change this file only through a pull request, like any other file.

## The project

Prophecy: a multiplayer card game after the rules of Wizard, built with Python and NiceGUI.
`game/` holds the game logic, accounts, lobbies and database code; `views/` holds the pages; `main.py` starts the server.
Locally the data is stored in SQLite; online (Render) it is stored in PostgreSQL (Supabase) via `DATABASE_URL`.

## Commands

NiceGUI needs Python 3.11 or newer.

- Run the app with: `uv run --python 3.13 --with-requirements requirements.txt python main.py`
- Run the tests with: `uv run --python 3.13 --with-requirements requirements.txt pytest`

## Rules

- Work on a new branch. Never commit to `main` directly; every change goes through a pull request,
  and someone other than the author reviews and merges it.
- Write the tests first and see them fail, then write the code.
- Before finishing a task, run all tests and paste the output.
- Never edit files in `tests/` unless the task says so.
- Never create or edit `.env` files or other files with secrets. Never write passwords, keys or database
  addresses into the code.
- Escape all text that users type (names, chat) before it goes into HTML, with `esc()` from `views/common.py`.
- Do not add new packages without asking. Every package in `requirements.txt` has a fixed version.
- Code, comments and messages in the app are in English.
