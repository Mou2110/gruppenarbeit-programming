"""Tests for the stats page (views/stats.py): the numbers (summary), the form and the win streaks.

Each result is one finished game of the signed-in player, as the database returns it.
"""
import pytest

from game.leaderboard import rank
from views.stats import form, streak_text, summary, win_streaks


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


# ---------------------------------------------------------------- Form and win streaks
# The database returns the player's games newest first (see persistence.results_for).


def game(place, players=4):
    return {'place': place, 'players': players}


def test_no_games_gives_no_form_and_no_streaks():
    assert form([]) == []
    assert win_streaks([]) == (0, 0)


def test_form_shows_the_last_ten_games_oldest_on_the_left():
    newest_first = [game(1), game(2), game(3), game(4), game(1), game(2), game(3), game(4), game(1), game(2),
                    game(3), game(4)]   # 12 games: the two oldest (place 3 and 4) are left out
    assert [g['place'] for g in form(newest_first)] == [2, 1, 4, 3, 2, 1, 4, 3, 2, 1]


def test_form_colours_win_last_place_and_everything_in_between():
    newest_first = [game(1, players=3), game(3, players=3), game(2, players=3), game(6, players=6),
                    game(2, players=6)]
    assert [g['kind'] for g in form(newest_first)] == ['mid', 'last', 'mid', 'last', 'win']


def test_a_shared_first_place_is_a_win_in_the_form():
    assert form([game(1)])[0]['kind'] == 'win'


def test_current_streak_counts_the_newest_wins_in_a_row():
    newest_first = [game(1), game(1), game(1), game(2), game(1)]
    assert win_streaks(newest_first) == (3, 3)


def test_a_lost_newest_game_ends_the_current_streak():
    newest_first = [game(2), game(1), game(1)]
    assert win_streaks(newest_first) == (0, 2)


def test_the_best_streak_stays_after_the_streak_is_broken():
    newest_first = [game(1), game(3), game(1), game(1), game(1), game(1), game(2)]
    assert win_streaks(newest_first) == (1, 4)


def test_only_wins_makes_current_and_best_streak_equal_to_all_games():
    assert win_streaks([game(1)] * 6) == (6, 6)


@pytest.mark.parametrize('current, best, text', [
    (3, 5, 'Current streak: 3 wins in a row · Best streak: 5'),
    (1, 1, 'Current streak: 1 win in a row · Best streak: 1'),
    (0, 4, 'No current streak · Best streak: 4'),
    (0, 0, 'No wins yet'),
])
def test_streak_text(current, best, text):
    assert streak_text(current, best) == text


# ---- Form row on the stats page: places as "1st", "4th" with a short explanation (no tooltip needed on phones)

def test_places_are_written_as_ordinals():
    from views.stats import ordinal
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == \
        ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd']


def test_form_row_says_what_the_numbers_mean():
    from views.stats import form_html
    html = form_html([{'place': 4, 'players': 5}, {'place': 1, 'players': 4}])  # newest first
    assert 'Your place in each game' in html
    assert html.index('1st') < html.index('4th')                     # oldest on the left
    assert 'of 5' in html
