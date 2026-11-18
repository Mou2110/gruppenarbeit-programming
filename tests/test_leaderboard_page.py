"""Tests for the logic of the leaderboard page (views/leaderboard.py).

The page itself only draws what these helpers return:
- sort_key(): which statistic the address asks for (?sort=...)
- games_needed(): how many more games a signed-in player needs to appear
- display_value(): how the chosen statistic is written on the right of each row
- view_rows(): the rows of the page (place, name, games and wins, value, own row, first place)
"""
import pytest

from game.leaderboard import SORT_KEYS, rank
from views.leaderboard import SORT_LABELS, display_value, games_needed, sort_key, view_rows


def row(name, games, wins, points=0, best=0, rounds=0, correct=0):
    return {'account': name.lower(), 'name': name, 'games': games, 'wins': wins,
            'points': points, 'best': best, 'rounds': rounds, 'correct': correct}


# ---------------------------------------------------------------- Sorting from the address

@pytest.mark.parametrize('asked', ['bid_rate', 'avg_per_round', 'best_score'])
def test_a_known_statistic_in_the_address_is_used(asked):
    assert sort_key(asked) == asked


@pytest.mark.parametrize('asked', [None, '', 'password', 'WIN_RATE', "'; DROP TABLE results; --"])
def test_a_missing_or_unknown_statistic_falls_back_to_win_rate(asked):
    assert sort_key(asked) == 'win_rate'


def test_every_statistic_has_a_button_label():
    assert set(SORT_LABELS) == set(SORT_KEYS)


# ---------------------------------------------------------------- Games still needed

@pytest.mark.parametrize('played, needed', [(0, 5), (3, 2), (4, 1), (5, 0), (12, 0)])
def test_games_needed_to_appear_on_the_leaderboard(played, needed):
    assert games_needed(played) == needed


# ---------------------------------------------------------------- Value on the right

@pytest.mark.parametrize('sort_by, value, shown', [
    ('win_rate', 58, '58 %'),
    ('bid_rate', 67, '67 %'),
    ('avg_per_round', 8.3, '8.3'),
    ('avg_per_round', 8.0, '8.0'),
    ('avg_score', 83, '83'),
    ('best_score', -10, '-10'),
    ('wins', 7, '7'),
    ('games', 12, '12'),
])
def test_the_chosen_value_is_written_with_its_unit(sort_by, value, shown):
    assert display_value({sort_by: value}, sort_by) == shown


# ---------------------------------------------------------------- Rows of the page

def test_rows_show_place_name_games_wins_and_the_chosen_value():
    board = rank([row('Erik', games=12, wins=7), row('Lena', games=8, wins=6)])
    rows = view_rows(board, 'win_rate', me=None)
    assert [(r['place'], r['name'], r['detail'], r['value']) for r in rows] == [
        (1, 'Lena', '8 games · 6 wins', '75 %'),
        (2, 'Erik', '12 games · 7 wins', '58 %'),
    ]


def test_one_win_is_written_in_singular():
    rows = view_rows(rank([row('Lena', games=5, wins=1)]), 'win_rate', me=None)
    assert rows[0]['detail'] == '5 games · 1 win'


def test_only_the_signed_in_players_own_row_is_marked():
    board = rank([row('Erik', games=12, wins=7), row('Lena', games=8, wins=6)])
    rows = view_rows(board, 'win_rate', me='erik')
    assert [r['me'] for r in rows] == [False, True]


def test_guests_have_no_own_row():
    rows = view_rows(rank([row('Lena', games=8, wins=6)]), 'win_rate', me=None)
    assert rows[0]['me'] is False


def test_everyone_on_first_place_is_marked_as_top_also_when_shared():
    board = rank([row('Cem', games=6, wins=1), row('Ben', games=6, wins=3), row('Ana', games=6, wins=3)])
    rows = view_rows(board, 'win_rate', me=None)
    assert [(r['name'], r['top']) for r in rows] == [('Ana', True), ('Ben', True), ('Cem', False)]


def test_nobody_listed_gives_no_rows():
    assert view_rows([], 'win_rate', me='lena') == []
