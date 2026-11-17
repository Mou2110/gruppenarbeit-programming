"""Tests for the leaderboard: who is listed, in which order, and with which numbers.

Two parts are tested:
- rank() in game/leaderboard.py: the ranking rule, without a database.
- leaderboard_rows() in game/persistence.py: adding up each account's finished games
  (locally with SQLite in a test folder, never the real database).
"""
import pytest

from game.leaderboard import rank
from game.persistence import SqliteStore


def row(name, games, wins, points=0, best=0, rounds=0, correct=0):
    """One player's totals, as leaderboard_rows() returns them."""
    return {'account': name.lower(), 'name': name, 'games': games, 'wins': wins,
            'points': points, 'best': best, 'rounds': rounds, 'correct': correct}


def names(board):
    return [entry['name'] for entry in board]


# ---------------------------------------------------------------- Ranking rule (no database)

def test_by_default_a_higher_win_rate_ranks_first_even_with_fewer_wins():
    board = rank([row('Erik', games=12, wins=7), row('Lena', games=8, wins=6)])
    assert names(board) == ['Lena', 'Erik']      # 75 % beats 58 %
    assert [e['place'] for e in board] == [1, 2]


def test_same_value_more_games_ranks_first():
    board = rank([row('Ana', games=6, wins=3), row('Ben', games=10, wins=5)])
    assert names(board) == ['Ben', 'Ana']        # both 50 %, Ben has played more
    assert [e['place'] for e in board] == [1, 2]


def test_full_tie_shares_the_place_and_the_next_place_is_skipped():
    board = rank([row('Cem', games=6, wins=1), row('Ben', games=6, wins=3), row('Ana', games=6, wins=3)])
    assert names(board) == ['Ana', 'Ben', 'Cem']  # equal players in alphabetical order
    assert [e['place'] for e in board] == [1, 1, 3]


# Two players where each one is better in some statistics:
#   A: 3 of 10 games won (30 %), 1000 points (100 per game), 150 rounds (6.7 per round), 90 bids hit (60 %), best 150
#   B: 2 of  5 games won (40 %),  600 points (120 per game),  60 rounds (10 per round),  30 bids hit (50 %), best 180
@pytest.mark.parametrize('sort_by, first', [
    ('win_rate', 'B'),
    ('wins', 'A'),
    ('games', 'A'),
    ('avg_score', 'B'),
    ('avg_per_round', 'B'),
    ('bid_rate', 'A'),
    ('best_score', 'B'),
])
def test_the_leaderboard_can_be_sorted_by_each_statistic(sort_by, first):
    rows = [row('A', games=10, wins=3, points=1000, best=150, rounds=150, correct=90),
            row('B', games=5, wins=2, points=600, best=180, rounds=60, correct=30)]
    assert rank(rows, sort_by)[0]['name'] == first


def test_an_unknown_statistic_is_rejected():
    with pytest.raises(ValueError):
        rank([row('Lena', games=5, wins=1)], 'password')


def test_numbers_are_rounded_like_on_the_stats_page():
    entry = rank([row('Lena', games=6, wins=2, points=500, best=120, rounds=60, correct=40)])[0]
    assert entry['games'] == 6
    assert entry['wins'] == 2
    assert entry['win_rate'] == 33        # 2 of 6
    assert entry['avg_score'] == 83       # 500 / 6
    assert entry['avg_per_round'] == 8.3  # 500 / 60, one decimal
    assert entry['best_score'] == 120
    assert entry['bid_rate'] == 67        # 40 of 60 bids hit


def test_no_rounds_gives_zero_instead_of_an_error():
    entry = rank([row('Lena', games=5, wins=0, rounds=0, correct=0)])[0]
    assert entry['bid_rate'] == 0
    assert entry['avg_per_round'] == 0


def test_nobody_listed_gives_an_empty_leaderboard():
    assert rank([]) == []


# ---------------------------------------------------------------- Adding up games (database)

def play(store, code, rounds, *players):
    """Record one finished game. Each player is (name, score, account, correct)."""
    store.record_game(code, rounds, [{'name': name, 'score': score, 'account': account, 'correct': correct}
                                     for name, score, account, correct in players])


def test_rows_add_up_all_finished_games_of_each_account(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Lena', 'secret123')
    store.register('Erik', 'secret123')
    play(store, 'AAAA', 10, ('Lena', 120, 'lena', 7), ('Erik', 80, 'erik', 5))
    play(store, 'BBBB', 10, ('Lena', 60, 'lena', 4), ('Erik', 90, 'erik', 6))
    play(store, 'CCCC', 10, ('Lena', 100, 'lena', 6), ('Erik', 100, 'erik', 6))   # tie: both place 1
    store.flush()
    rows = {r['name']: r for r in store.leaderboard_rows(min_games=1)}
    assert rows['Lena'] == {'account': 'lena', 'name': 'Lena', 'games': 3, 'wins': 2, 'points': 280,
                            'best': 120, 'rounds': 30, 'correct': 17}
    assert rows['Erik'] == {'account': 'erik', 'name': 'Erik', 'games': 3, 'wins': 2, 'points': 270,
                            'best': 100, 'rounds': 30, 'correct': 17}


def test_by_default_players_need_five_games_to_be_listed(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Lena', 'secret123')
    store.register('Erik', 'secret123')
    for code in ('AAAA', 'BBBB', 'CCCC', 'DDDD', 'EEEE'):
        play(store, code, 5, ('Lena', 50, 'lena', 3))
    for code in ('FFFF', 'GGGG', 'HHHH', 'IIII'):
        play(store, code, 5, ('Erik', 90, 'erik', 5))
    store.flush()
    assert [r['name'] for r in store.leaderboard_rows()] == ['Lena']   # Erik has only 4 games


def test_guests_and_bots_never_appear(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Lena', 'secret123')
    play(store, 'AAAA', 5, ('Lena', 50, 'lena', 3), ('Guest', 90, None, 5), ('Bot Anna', 70, None, 4))
    store.flush()
    assert [r['name'] for r in store.leaderboard_rows(min_games=1)] == ['Lena']


def test_the_name_shown_is_the_account_username_not_the_name_typed_in_the_game(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Lena', 'secret123')
    play(store, 'AAAA', 5, ('Lenchen', 50, 'lena', 3))
    store.flush()
    assert [r['name'] for r in store.leaderboard_rows(min_games=1)] == ['Lena']


def test_no_finished_games_gives_no_rows(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Lena', 'secret123')
    assert store.leaderboard_rows(min_games=1) == []
