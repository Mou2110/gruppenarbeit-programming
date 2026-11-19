"""Save game states permanently, so that a server restart does not delete any lobby or game.

If the environment variable DATABASE_URL is set (online on Render: the Supabase database),
everything is saved in PostgreSQL. Otherwise it goes into the local file data/prophecy.db (SQLite).

Saving happens in a separate background thread, so the game never has to wait for the database.
"""
from __future__ import annotations

import json
import logging
import os
import pickle
import queue
import sqlite3
import threading
import time
from pathlib import Path

from . import accounts
from .accounts import AccountError
from .leaderboard import MIN_GAMES

log = logging.getLogger('prophecy.persistence')

KEEP_HOURS = 24  # lobbies not changed for this long are no longer loaded at startup

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS lobbies (
           code TEXT PRIMARY KEY,
           data {blob} NOT NULL,
           updated_at {time} NOT NULL
       )""",
    """CREATE TABLE IF NOT EXISTS accounts (
           key TEXT PRIMARY KEY,
           username TEXT NOT NULL,
           password TEXT NOT NULL,
           created_at {time} NOT NULL
       )""",
    """CREATE TABLE IF NOT EXISTS sessions (
           token TEXT PRIMARY KEY,
           account TEXT NOT NULL,
           created_at {time} NOT NULL
       )""",
    """CREATE TABLE IF NOT EXISTS results (
           id {serial},
           account TEXT NOT NULL,
           code TEXT NOT NULL,
           finished_at {time} NOT NULL,
           name TEXT NOT NULL,
           score INTEGER NOT NULL,
           place INTEGER NOT NULL,
           players INTEGER NOT NULL,
           rounds INTEGER NOT NULL,
           correct INTEGER NOT NULL
       )""",
    """CREATE TABLE IF NOT EXISTS finished_games (
           id {serial},
           code TEXT NOT NULL,
           finished_at {time} NOT NULL,
           rounds INTEGER NOT NULL,
           players TEXT NOT NULL
       )""",
]


class Store:
    """Shared logic: queue + background thread. Subclasses only provide the connection."""

    placeholder = '?'
    types = {'blob': 'BLOB', 'time': 'REAL', 'serial': 'INTEGER PRIMARY KEY AUTOINCREMENT'}

    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._conn = None
        self._lock = threading.RLock()   # game thread and background thread share the connection
        self.failed_logins = accounts.FailedLogins()
        self._thread = threading.Thread(target=self._run, name='prophecy-store', daemon=True)
        self._thread.start()

    # ---------------------------------------------------------------- Connection

    def _connect(self):
        raise NotImplementedError

    def _db(self):
        if self._conn is None:
            self._conn = self._connect()
            for statement in SCHEMA:
                self._execute(statement.format(**self.types))
        return self._conn

    def _execute(self, sql: str, params: tuple = ()) -> list:
        cursor = self._conn.cursor()
        cursor.execute(sql.replace('?', self.placeholder), params)
        rows = cursor.fetchall() if cursor.description else []
        self._conn.commit()
        return rows

    def _with_retry(self, sql: str, params: tuple = ()) -> list:
        """Run one statement. If the connection drops, reconnect once and try again."""
        with self._lock:
            for attempt in range(2):
                try:
                    self._db()
                    return self._execute(sql, params)
                except Exception as error:
                    if self._is_duplicate(error):
                        raise AccountError('That username is already taken.') from error
                    try:
                        if self._conn is not None:
                            self._conn.close()
                    except Exception:
                        pass
                    self._conn = None
                    if attempt:
                        raise
        return []

    @staticmethod
    def _is_duplicate(error: Exception) -> bool:
        name = type(error).__name__
        return name == 'UniqueViolation' or (name == 'IntegrityError' and 'UNIQUE' in str(error))

    # ---------------------------------------------------------------- Writing (in the background)

    def save_lobby(self, code: str, data: bytes) -> None:
        self._queue.put(('save', code, data))

    def delete_lobby(self, code: str) -> None:
        self._queue.put(('delete', code, None))

    def record_game(self, code: str, rounds: int, players: list[dict]) -> None:
        self._queue.put(('game', code, (rounds, json.dumps(players))))

    def flush(self, timeout: float = 5.0) -> None:
        """Waits until everything is written (e.g. when the server shuts down)."""
        done = threading.Event()
        self._queue.put(('flush', None, done))
        done.wait(timeout)

    def _run(self) -> None:
        while True:
            jobs = [self._queue.get()]
            while not self._queue.empty():   # collect everything that has arrived in the meantime
                jobs.append(self._queue.get())
            latest: dict[str, tuple] = {}    # per lobby, only the newest state counts
            for job in jobs:
                kind, code, payload = job
                if kind in ('save', 'delete'):
                    latest[code] = job
            for job in jobs:
                kind, code, payload = job
                try:
                    if kind in ('save', 'delete') and latest.get(code) is job:
                        if kind == 'save':
                            self._upsert(code, payload)
                        else:
                            self._with_retry('DELETE FROM lobbies WHERE code = ?', (code,))
                    elif kind == 'game':
                        self._write_game(code, *payload)
                except Exception:
                    log.exception('Could not write %s for lobby %s', kind, code)
                if kind == 'flush':
                    payload.set()

    def _write_game(self, code: str, rounds: int, players_json: str) -> None:
        now = time.time()
        self._with_retry('INSERT INTO finished_games (code, finished_at, rounds, players) VALUES (?, ?, ?, ?)',
                         (code, now, rounds, players_json))
        players = json.loads(players_json)
        stayed = [p for p in players if not p.get('left')]
        for p in players:
            if p.get('account'):
                # Whoever left the game for good is last; everyone else is ranked among those who stayed.
                place = len(players) if p.get('left') else 1 + sum(other['score'] > p['score'] for other in stayed)
                self._with_retry('INSERT INTO results (account, code, finished_at, name, score, place, players, '
                                 'rounds, correct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                 (p['account'], code, now, p['name'], p['score'], place, len(players),
                                  rounds, p.get('correct', 0)))

    # ---------------------------------------------------------------- Accounts (directly, not in the background)

    def register(self, username: str, password: str) -> tuple[str, str]:
        """Create a new account. Returns (key, display name)."""
        username = accounts.check_username(username)
        accounts.check_password(password)
        key = accounts.username_key(username)
        if self._with_retry('SELECT key FROM accounts WHERE key = ?', (key,)):
            raise AccountError('That username is already taken.')
        self._with_retry('INSERT INTO accounts (key, username, password, created_at) VALUES (?, ?, ?, ?)',
                         (key, username, accounts.hash_password(password), time.time()))
        return key, username

    def login(self, username: str, password: str) -> tuple[str, str]:
        key = accounts.username_key(username)
        self.failed_logins.check(key)
        rows = self._with_retry('SELECT username, password FROM accounts WHERE key = ?', (key,))
        if not rows or not accounts.password_matches(password, rows[0][1]):
            self.failed_logins.failed(key)
            raise AccountError('Wrong username or password.')
        self.failed_logins.succeeded(key)
        return key, rows[0][0]

    def new_session(self, key: str) -> str:
        token = accounts.new_token()
        self._with_retry('INSERT INTO sessions (token, account, created_at) VALUES (?, ?, ?)',
                         (accounts.token_hash(token), key, time.time()))
        return token

    def session_account(self, token: str) -> tuple[str, str] | None:
        """Which account does this sign-in token belong to? (key, display name) or None."""
        if not token:
            return None
        rows = self._with_retry('SELECT a.key, a.username FROM sessions s JOIN accounts a ON a.key = s.account '
                                'WHERE s.token = ?', (accounts.token_hash(token),))
        return (rows[0][0], rows[0][1]) if rows else None

    def end_session(self, token: str) -> None:
        self._with_retry('DELETE FROM sessions WHERE token = ?', (accounts.token_hash(token),))

    def results_for(self, key: str) -> list[dict]:
        rows = self._with_retry('SELECT code, finished_at, name, score, place, players, rounds, correct '
                                'FROM results WHERE account = ? ORDER BY finished_at DESC', (key,))
        names = ('code', 'finished_at', 'name', 'score', 'place', 'players', 'rounds', 'correct')
        return [dict(zip(names, row)) for row in rows]

    def leaderboard_rows(self, min_games: int = MIN_GAMES) -> list[dict]:
        """Each account's totals over all finished games, for accounts with at least min_games games.

        Guests and bots have no account, so they never appear. The name is the account's username.
        """
        rows = self._with_retry('SELECT r.account, a.username, COUNT(*), '
                                'SUM(CASE WHEN r.place = 1 THEN 1 ELSE 0 END), SUM(r.score), MAX(r.score), '
                                'SUM(r.rounds), SUM(r.correct) '
                                'FROM results r JOIN accounts a ON a.key = r.account '
                                'GROUP BY r.account, a.username HAVING COUNT(*) >= ? '
                                'ORDER BY r.account', (min_games,))
        names = ('account', 'name', 'games', 'wins', 'points', 'best', 'rounds', 'correct')
        return [dict(zip(names, row)) for row in rows]

    def _upsert(self, code: str, data: bytes) -> None:
        self._with_retry('INSERT INTO lobbies (code, data, updated_at) VALUES (?, ?, ?) '
                         'ON CONFLICT (code) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at',
                         (code, data, time.time()))

    # ---------------------------------------------------------------- Reading (at startup)

    def load_lobbies(self) -> dict[str, object]:
        """Load all current lobbies. Anything that can no longer be loaded (old code version) is skipped."""
        result: dict[str, object] = {}
        try:
            cutoff = time.time() - KEEP_HOURS * 3600
            self._with_retry('DELETE FROM lobbies WHERE updated_at < ?', (cutoff,))
            rows = self._with_retry('SELECT code, data FROM lobbies')
        except Exception:
            log.exception('Could not load saved lobbies')
            return result
        for code, data in rows:
            try:
                result[code] = pickle.loads(bytes(data))
            except Exception:
                log.warning('Saved lobby %s could not be restored, skipping it', code)
        return result

    def finished_games(self, limit: int = 50) -> list[dict]:
        rows = self._with_retry('SELECT code, finished_at, rounds, players FROM finished_games '
                                'ORDER BY finished_at DESC LIMIT ?', (limit,))
        return [{'code': c, 'finished_at': t, 'rounds': r, 'players': json.loads(p)} for c, t, r, p in rows]


class SqliteStore(Store):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__()

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path, check_same_thread=False)


class PostgresStore(Store):
    placeholder = '%s'
    types = {'blob': 'BYTEA', 'time': 'DOUBLE PRECISION', 'serial': 'BIGSERIAL PRIMARY KEY'}

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__()

    def _connect(self):
        import psycopg  # only needed when an online database is really used
        return psycopg.connect(self.url, connect_timeout=10)


def make_store(base: Path) -> Store:
    url = os.environ.get('DATABASE_URL', '').strip()
    if url:
        log.info('Saving games in PostgreSQL')
        return PostgresStore(url)
    log.info('Saving games locally in data/prophecy.db')
    return SqliteStore(base / 'data' / 'prophecy.db')
