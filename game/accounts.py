"""Accounts: check usernames, store passwords safely, create sign-in tokens.

Passwords are never stored in plain text. They are hashed with scrypt and a random salt.
Sign-in tokens live in the browser; the database only holds their hash.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

USERNAME_MIN, USERNAME_MAX = 3, 16
PASSWORD_MIN = 6
USERNAME_RE = re.compile(r'^[A-Za-z0-9_.-]+$')
ACCOUNT_PREFIX = 'acct:'          # player ids of signed-in players start with this
MAX_FAILS, LOCK_SECONDS = 5, 300  # after 5 wrong passwords, wait 5 minutes


class AccountError(Exception):
    """Sign-up or sign-in failed (the text is shown to the player)."""


def username_key(username: str) -> str:
    """Upper/lower case does not matter: 'Erik' and 'erik' are the same account."""
    return username.strip().lower()


def check_username(username: str) -> str:
    username = username.strip()
    if not USERNAME_MIN <= len(username) <= USERNAME_MAX:
        raise AccountError(f'Username must be {USERNAME_MIN}–{USERNAME_MAX} characters.')
    if not USERNAME_RE.match(username):
        raise AccountError('Use only letters, numbers, dots, dashes and underscores.')
    return username


def check_password(password: str) -> str:
    if len(password) < PASSWORD_MIN:
        raise AccountError(f'Password must be at least {PASSWORD_MIN} characters.')
    if len(password) > 200:
        raise AccountError('That password is too long.')
    return password


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f'scrypt${salt.hex()}${digest.hex()}'


def password_matches(password: str, stored: str) -> bool:
    try:
        method, salt_hex, digest_hex = stored.split('$')
    except ValueError:
        return False
    if method != 'scrypt':
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2 ** 14, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest.hex(), digest_hex)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def member_id(key: str) -> str:
    return ACCOUNT_PREFIX + key


def account_of(member_id_: str) -> str | None:
    return member_id_[len(ACCOUNT_PREFIX):] if member_id_.startswith(ACCOUNT_PREFIX) else None


class FailedLogins:
    """Slows down password guessing: after too many wrong tries, lock the account for a short time."""

    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.fails: dict[str, list[float]] = {}

    def check(self, key: str) -> None:
        recent = [t for t in self.fails.get(key, []) if self.clock() - t < LOCK_SECONDS]
        self.fails[key] = recent
        if len(recent) >= MAX_FAILS:
            raise AccountError('Too many wrong passwords. Please wait a few minutes.')

    def failed(self, key: str) -> None:
        self.fails.setdefault(key, []).append(self.clock())

    def succeeded(self, key: str) -> None:
        self.fails.pop(key, None)
