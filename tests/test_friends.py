"""Tests for the friends list: signed-in players add other accounts by username."""
import pytest

from game.accounts import AccountError
from game.persistence import SqliteStore
from views import stats


@pytest.fixture
def store(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    for name in ('Erik', 'Marta', 'Jan'):
        store.register(name, 'secret123')
    return store


def test_new_account_has_no_friends(store):
    assert store.friends_of('erik') == []


def test_add_friend_by_username_ignores_upper_and_lower_case(store):
    assert store.add_friend('erik', '  MARTA ') == 'Marta'
    assert [f['name'] for f in store.friends_of('erik')] == ['Marta']


def test_adding_is_one_way(store):
    store.add_friend('erik', 'Marta')
    assert store.friends_of('marta') == []          # Marta does not have to confirm anything


def test_adding_twice_changes_nothing(store):
    store.add_friend('erik', 'Marta')
    store.add_friend('erik', 'marta')
    assert len(store.friends_of('erik')) == 1


def test_cannot_add_yourself(store):
    with pytest.raises(AccountError):
        store.add_friend('erik', 'Erik')
    assert store.friends_of('erik') == []


def test_cannot_add_an_unknown_username(store):
    with pytest.raises(AccountError):
        store.add_friend('erik', 'Nobody')
    assert store.friends_of('erik') == []


def test_remove_friend(store):
    store.add_friend('erik', 'Marta')
    store.add_friend('erik', 'Jan')
    store.remove_friend('erik', 'marta')
    assert [f['name'] for f in store.friends_of('erik')] == ['Jan']
    store.remove_friend('erik', 'marta')            # removing again does nothing


def test_friends_are_sorted_by_name_and_show_games_and_wins(store):
    store.add_friend('erik', 'Marta')
    store.add_friend('erik', 'Jan')
    store.record_game('ABCD', 15, [
        {'name': 'Marta', 'score': 90, 'account': 'marta', 'correct': 8},
        {'name': 'Jan', 'score': 40, 'account': 'jan', 'correct': 5},
    ])
    store.flush()
    assert store.friends_of('erik') == [
        {'account': 'jan', 'name': 'Jan', 'games': 1, 'wins': 0},
        {'account': 'marta', 'name': 'Marta', 'games': 1, 'wins': 1},
    ]


def test_friend_row_links_to_profile_and_escapes_the_name():
    html = stats.friend_html({'account': 'marta', 'name': '<Marta>', 'games': 7, 'wins': 1})
    assert 'href="/players/marta"' in html
    assert '&lt;Marta&gt;' in html and '<Marta>' not in html
    assert '7 games · 1 win' in html


def test_friend_without_finished_games_has_no_profile_link():
    # A profile needs at least one finished game (there is nothing to show before that).
    html = stats.friend_html({'account': 'jan', 'name': 'Jan', 'games': 0, 'wins': 0})
    assert 'href=' not in html and 'Jan' in html
    assert '0 games · 0 wins' in html


def test_friend_with_one_game_can_be_clicked():
    # Friends do not need 5 games like the leaderboard: one finished game is enough for their profile.
    html = stats.friend_html({'account': 'jan', 'name': 'Jan', 'games': 1, 'wins': 0})
    assert 'href="/players/jan"' in html
