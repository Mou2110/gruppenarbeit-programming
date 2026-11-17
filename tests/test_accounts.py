"""Tests for accounts: sign-up, sign-in, sessions and protection against password guessing.

Needs only game/accounts.py and game/persistence.py (locally with SQLite in a test folder).
"""
import pytest

from game.accounts import AccountError, password_matches, hash_password
from game.persistence import SqliteStore


def test_password_hash_is_salted_and_checkable():
    first, second = hash_password('secret123'), hash_password('secret123')
    assert first != second                       # a different salt every time
    assert password_matches('secret123', first) and not password_matches('wrong', first)


def test_accounts_register_login_and_sessions(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    assert store.register('Erik', 'secret123') == ('erik', 'Erik')
    with pytest.raises(AccountError):
        store.register('ERIK', 'other123')           # upper/lower case does not matter
    with pytest.raises(AccountError):
        store.register('ab', 'secret123')            # too short
    with pytest.raises(AccountError):
        store.register('Bob', '123')                 # password too short
    assert store.login('erik', 'secret123') == ('erik', 'Erik')
    with pytest.raises(AccountError):
        store.login('Erik', 'wrong-password')
    token = store.new_session('erik')
    assert store.session_account(token) == ('erik', 'Erik')
    assert store.session_account('made-up-token') is None
    store.end_session(token)
    assert store.session_account(token) is None
    # the password is not stored in plain text in the database
    assert 'secret123' not in str(store._with_retry('SELECT password FROM accounts'))


def test_too_many_wrong_passwords_lock_the_account_for_a_while(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Erik', 'secret123')
    for _ in range(5):
        with pytest.raises(AccountError):
            store.login('Erik', 'nope-nope')
    with pytest.raises(AccountError, match='Too many'):
        store.login('Erik', 'secret123')
