"""Test how the table displays chosen suits on played cards (the trump card itself: see test_table_polish.py)."""
import pytest

from game.cards import Card, Kind, Suit
from game.rules import Play
from views.table import _trick_html


@pytest.mark.parametrize('kind', [Kind.JUGGLER, Kind.CLOUD])
@pytest.mark.parametrize('chosen', [None, Suit.SARDINE])
def test_played_special_cards_keep_their_existing_suit_badge(kind, chosen):
    view = {'phase': 'playing', 'trump': Suit.OLIVE, 'my_index': 0,
            'players': [{'name': name} for name in ('Ana', 'Marta', 'Tiago')],
            'trick': [Play(0, Card(kind.value, kind), suit=chosen)]}
    html = _trick_html(view, paused=False)
    assert f'art-{kind.value}' in html
    assert 'class="as"' not in html
    if chosen is None:
        assert 'class="chosen-suit' not in html
    else:
        assert 'class="chosen-suit s-sardine"' in html



def test_a_newly_played_card_glides_in_from_its_players_seat():
    view = {'phase': 'playing', 'trump': None, 'my_index': 0,
            'players': [{'name': name} for name in ('Me', 'Ana', 'Ben', 'Cem')],
            'trick': [Play(2, Card('sea-3', Kind.NUMBER, Suit.SEA, 3)), Play(0, Card('sun-5', Kind.NUMBER, Suit.SUN, 5))]}
    ben, me = _trick_html(view, paused=False, seen={'sea-3'}).split('<div class="tslot')[1:]
    assert 'enter' not in ben.split('"')[0]                  # already on the table: no animation again
    assert 'enter' in me.split('"')[0] and '--fy:1.60' in me  # my own card comes up from my hand below
    ben, me = _trick_html(view, paused=False, seen={'sun-5'}).split('<div class="tslot')[1:]
    assert '--fx:0.000;--fy:-1.000' in ben                   # Ben sits opposite me: his card comes from the top
