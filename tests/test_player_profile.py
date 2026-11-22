"""Tests for opening player profiles from the public leaderboard."""
import asyncio
from types import SimpleNamespace

import pytest

from game.leaderboard import rank
from views import leaderboard


def player(account='marta', name='Marta', games=5):
    return {'account': account, 'name': name, 'games': games, 'wins': 3,
            'points': 215, 'best': 81, 'rounds': 30, 'correct': 19}


def test_leaderboard_links_each_name_to_that_players_profile():
    rows = leaderboard.view_rows(rank([player(), player('jan', 'Jan', 7)]), 'wins', me='jan')
    links = {row['name']: leaderboard._row_html(row) for row in rows}

    assert '<a class="profile-link" href="/players/marta">Marta</a>' in links['Marta']
    assert '<a class="profile-link" href="/players/jan">Jan</a> <em>(you)</em>' in links['Jan']


def test_leaderboard_escapes_player_names_in_links():
    rows = leaderboard.view_rows(rank([player(name='<Marta>')]), 'wins', me=None)

    assert 'href="/players/marta">&lt;Marta&gt;</a>' in leaderboard._row_html(rows[0])


def test_profile_uses_the_requested_players_public_leaderboard_statistics():
    rows = [player('jan', 'Jan', 7), player()]
    entry = leaderboard.profile_entry(rows, 'MARTA')

    assert entry['name'] == 'Marta'
    assert {key: leaderboard.display_value(entry, key) for key in leaderboard.SORT_LABELS} == {
        'games': '5', 'wins': '3', 'win_rate': '60 %', 'avg_score': '43',
        'avg_per_round': '7.2', 'best_score': '81', 'bid_rate': '63 %',
    }


def test_a_profile_needs_only_one_finished_game_when_opened_directly():
    # Friends link to profiles even before they reach the leaderboard (5 games).
    rows = [player('jan', 'Jan', games=1)]
    assert leaderboard.profile_entry(rows, 'jan', min_games=1)['name'] == 'Jan'
    assert leaderboard.profile_entry(rows, 'jan') is None        # the leaderboard rule stays 5 games


@pytest.mark.parametrize('name', ['missing', 'not_ranked', ''])
def test_unknown_or_unlisted_players_have_no_public_profile(name):
    rows = [player(), player('not_ranked', 'Not_ranked', games=4)]
    assert leaderboard.profile_entry(rows, name) is None


def failing_query(*_):
    raise RuntimeError('Database offline')


@pytest.mark.parametrize('store, expected', [
    (None, 'Player profile unavailable'),
    (SimpleNamespace(leaderboard_rows=lambda *_: []), 'Player profile not found'),
    (SimpleNamespace(leaderboard_rows=failing_query), 'Player profile unavailable'),
])
def test_profile_errors_give_a_useful_message(monkeypatch, store, expected):
    messages = []
    monkeypatch.setattr(leaderboard.registry, 'store', store)
    monkeypatch.setattr(leaderboard, 'message_page', lambda title, detail: messages.append(title))

    async def io_bound(action, *args):
        return action(*args)

    monkeypatch.setattr(leaderboard.run, 'io_bound', io_bound)
    asyncio.run(leaderboard.profile_page('missing'))

    assert messages == [expected]
