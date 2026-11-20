"""Test how the table displays trump and chosen suits."""
import pytest

from game.cards import Card, Kind, Suit
from game.rules import Play
from views.table import _trick_html, _trump_html


@pytest.mark.parametrize('revealed', [Card('olive-8', Kind.NUMBER, Suit.OLIVE, 8),
                                      Card('cloud', Kind.CLOUD)])
def test_trump_shows_the_suit_without_the_revealed_card(revealed):
    html = _trump_html({'phase': 'playing', 'trump': Suit.OLIVE, 'trump_card': revealed})
    assert '<span class="trump-symbol s-olive">' in html
    assert '<span class="ts">Olive</span>' in html
    assert html.count('<svg') == 1
    assert 'class="card ' not in html


@pytest.mark.parametrize('phase, trump, label', [
    ('choosing_trump', None, 'Choosing…'),
    ('werewolf', Suit.OLIVE, 'Choosing…'),
    ('playing', None, 'No trump'),
])
def test_trump_without_a_confirmed_suit_shows_only_its_status(phase, trump, label):
    html = _trump_html({'phase': phase, 'trump': trump, 'trump_card': Card('wizard', Kind.WIZARD)})
    assert f'<span class="ts">{label}</span>' in html
    assert '<svg' not in html
    assert 'class="card ' not in html


@pytest.mark.parametrize('kind', [Kind.JUGGLER, Kind.CLOUD])
@pytest.mark.parametrize('chosen', [None, Suit.SARDINE])
def test_trick_labels_the_chosen_suit_below_the_card(kind, chosen):
    view = {'phase': 'playing', 'trump': Suit.OLIVE, 'my_index': 0,
            'players': [{'name': name} for name in ('Ana', 'Marta', 'Tiago')],
            'trick': [Play(0, Card(kind.value, kind), suit=chosen)]}
    html = _trick_html(view, paused=False)
    assert f'art-{kind.value}' in html
    assert '<svg' not in html
    if chosen is None:
        assert 'class="as"' not in html
    else:
        assert '<span class="as">as Sardine</span>' in html
