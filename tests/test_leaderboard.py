"""Tests for the leaderboard: who is listed, in which order, and with which numbers.

Two parts are tested:
- rank() in game/leaderboard.py: the ranking rule, without a database.
- leaderboard_rows() in game/persistence.py: adding up each account's finished games
  (locally with SQLite in a test folder, never the real database).
"""
from game.leaderboard import rank
from game.persistence import SqliteStore


def row(name, games, wins, points=0, best=0, rounds=0, correct=0):
    """One player's totals, as leaderboard_rows() returns them."""
    return {'account': name.lower(), 'name': name, 'games': games, 'wins': wins,
            'points': points, 'best': best, 'rounds': rounds, 'correct': correct}


def names(board):
    return [entry['name'] for entry in board]


# ---------------------------------------------------------------- Ranking rule (no database)

def test_higher_win_rate_ranks_first_even_with_fewer_wins():
    board = rank([row('Erik', games=12, wins=7), row('Lena', games=4, wins=3)])
    assert names(board) == ['Lena', 'Erik']      # 75 % beats 58 %
    assert [e['place'] for e in board] == [1, 2]


def test_same_win_rate_more_wins_ranks_first():
    board = rank([row('Ana', games=4, wins=2), row('Ben', games=10, wins=5)])
    assert names(board) == ['Ben', 'Ana']        # both 50 %, Ben has more wins


def test_same_win_rate_and_wins_higher_average_ranks_first():
    board = rank([row('Ana', games=4, wins=2, points=400), row('Ben', games=4, wins=2, points=480)])
    assert names(board) == ['Ben', 'Ana']        # average 120 beats 100


def test_full_tie_shares_the_place_and_the_next_place_is_skipped():
    board = rank([row('Cem', games=4, wins=1, points=100),
                  row('Ben', games=4, wins=2, points=400),
                  row('Ana', games=4, wins=2, points=400)])
    assert names(board) == ['Ana', 'Ben', 'Cem']  # equal players in alphabetical order
    assert [e['place'] for e in board] == [1, 1, 3]


def test_numbers_are_rounded_like_on_the_stats_page():
    entry = rank([row('Lena', games=3, wins=1, points=250, best=120, rounds=30, correct=20)])[0]
    assert entry['games'] == 3
    assert entry['wins'] == 1
    assert entry['win_rate'] == 33       # 1 of 3
    assert entry['avg_score'] == 83      # 250 / 3
    assert entry['best_score'] == 120
    assert entry['bid_rate'] == 67       # 20 of 30 bids hit


def test_no_rounds_gives_a_bid_rate_of_zero_instead_of_an_error():
    entry = rank([row('Lena', games=3, wins=0, rounds=0, correct=0)])[0]
    assert entry['bid_rate'] == 0


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
    rows = {r['name']: r for r in store.leaderboard_rows()}
    assert rows['Lena'] == {'account': 'lena', 'name': 'Lena', 'games': 3, 'wins': 2, 'points': 280,
                            'best': 120, 'rounds': 30, 'correct': 17}
    assert rows['Erik'] == {'account': 'erik', 'name': 'Erik', 'games': 3, 'wins': 2, 'points': 270,
                            'best': 100, 'rounds': 30, 'correct': 17}


def test_players_with_fewer_than_three_games_are_not_listed(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Lena', 'secret123')
    store.register('Erik', 'secret123')
    for code in ('AAAA', 'BBBB', 'CCCC'):
        play(store, code, 5, ('Lena', 50, 'lena', 3))
    for code in ('DDDD', 'EEEE'):
        play(store, code, 5, ('Erik', 90, 'erik', 5))
    store.flush()
    assert [r['name'] for r in store.leaderboard_rows()] == ['Lena']


def test_guests_and_bots_never_appear(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Lena', 'secret123')
    for code in ('AAAA', 'BBBB', 'CCCC'):
        play(store, code, 5, ('Lena', 50, 'lena', 3), ('Guest', 90, None, 5), ('Bot Anna', 70, None, 4))
    store.flush()
    assert [r['name'] for r in store.leaderboard_rows()] == ['Lena']


def test_the_name_shown_is_the_account_username_not_the_name_typed_in_the_game(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Lena', 'secret123')
    for code in ('AAAA', 'BBBB', 'CCCC'):
        play(store, code, 5, ('Lenchen', 50, 'lena', 3))
    store.flush()
    assert [r['name'] for r in store.leaderboard_rows()] == ['Lena']


def test_no_finished_games_gives_no_rows(tmp_path):
    store = SqliteStore(tmp_path / 'db.sqlite')
    store.register('Lena', 'secret123')
    assert store.leaderboard_rows() == []
