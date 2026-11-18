"""Tests for the numbers on the stats page (summary() in views/stats.py).

Each result is one finished game of the signed-in player, as the database returns it.
"""
from game.leaderboard import rank
from views.stats import summary


def result(place, score, rounds=10, correct=5):
    return {'place': place, 'score': score, 'rounds': rounds, 'correct': correct}


def test_no_games_gives_zeros_instead_of_an_error():
    assert summary([]) == {'games': 0, 'wins': 0, 'win_rate': 0, 'avg_score': 0, 'best_score': 0, 'bid_rate': 0}


def test_games_wins_average_best_and_bids_are_counted():
    results = [result(1, 120, correct=8), result(3, -20, correct=3), result(1, 90, correct=7), result(2, 42, correct=6)]
    assert summary(results) == {
        'games': 4,
        'wins': 2,            # place 1 twice
        'win_rate': 50,
        'avg_score': 58,      # (120 - 20 + 90 + 42) / 4
        'best_score': 120,
        'bid_rate': 60,       # 24 of 40 bids hit
    }


def test_a_shared_first_place_counts_as_a_win():
    # Two players with the same top score both get place 1 (see persistence._write_game).
    s = summary([result(1, 80), result(1, 60), result(4, -10)])
    assert s['wins'] == 2
    assert s['win_rate'] == 67


def test_best_score_can_be_negative():
    # Only bad games: the best score is the least bad one, not 0.
    assert summary([result(3, -30), result(4, -10)])['best_score'] == -10


def test_rates_are_rounded_to_whole_percent():
    s = summary([result(1, 10, rounds=1, correct=1), result(2, 0, rounds=1, correct=0),
                 result(2, 0, rounds=1, correct=0)])
    assert s['win_rate'] == 33    # 1 of 3
    assert s['bid_rate'] == 33    # 1 of 3


def test_no_rounds_gives_a_bid_rate_of_zero_instead_of_an_error():
    assert summary([result(1, 0, rounds=0, correct=0)])['bid_rate'] == 0


def test_stats_page_and_leaderboard_show_the_same_numbers():
    results = [result(1, 120, correct=8), result(3, -20, correct=3), result(1, 90, correct=7),
               result(2, 42, correct=6), result(4, 15, correct=4)]
    row = {'account': 'lena', 'name': 'Lena', 'games': 5, 'wins': 2, 'points': 247, 'best': 120,
           'rounds': 50, 'correct': 28}
    on_stats_page = summary(results)
    on_leaderboard = rank([row])[0]
    for key in ('games', 'wins', 'win_rate', 'avg_score', 'best_score', 'bid_rate'):
        assert on_stats_page[key] == on_leaderboard[key], key
