"""End of the game: a podium for the first three (winner with a crown) and every player's place in the table."""
from views.table import podium_html, standings


def player(pid, name, score):
    return {'id': pid, 'name': name, 'score': score}


PLAYERS = [player('a', 'Ana', 130), player('b', 'Ben', 190), player('c', 'Cleo', -70), player('d', 'Dan', -150)]


def test_places_follow_the_total_score():
    assert [(place, p['name']) for place, p in standings(PLAYERS)] == [(1, 'Ben'), (2, 'Ana'), (3, 'Cleo'), (4, 'Dan')]


def test_equal_scores_share_a_place():
    tied = [player('a', 'Ana', 100), player('b', 'Ben', 100), player('c', 'Cleo', 50)]
    assert [place for place, _ in standings(tied)] == [1, 1, 3]


def test_podium_shows_second_first_third_and_only_the_winner_wears_the_crown():
    html = podium_html(standings(PLAYERS), me='z')
    assert html.index('Ana') < html.index('Ben') < html.index('Cleo')       # 2nd left, 1st middle, 3rd right
    assert html.count('podium-crown') == 1 and 'Dan' not in html            # only the first three stand on it
    assert '>You<' in podium_html(standings(PLAYERS), me='a')               # the viewer sees "You"


def test_podium_escapes_names():
    html = podium_html(standings([player('a', '<b>x</b>', 10), player('b', 'Ben', 5), player('c', 'Cleo', 1)]), me='z')
    assert '&lt;b&gt;x&lt;/b&gt;' in html and '<b>x</b>' not in html
