"""Test how the table displays trump and chosen suits."""
import pytest

from game.cards import Card, Kind, Suit
from game.rules import Play
from views.cards import SUIT_LABEL, card_html, suit_icon
from views.table import _trick_html, _trump_html


@pytest.mark.parametrize('revealed', [Card('olive-8', Kind.NUMBER, Suit.OLIVE, 8),
                                      Card('cloud', Kind.CLOUD)])
def test_trump_shows_the_revealed_card_next_to_the_suit(revealed):
    html = _trump_html({'phase': 'playing', 'trump': Suit.OLIVE, 'trump_card': revealed})
    assert '<span class="trump-symbol s-olive">' in html
    assert '<span class="ts">Olive</span>' in html
    assert card_html(revealed, 'sm') in html
    assert html.count('class="card ') == 1
    assert html.index(card_html(revealed, 'sm')) < html.index('class="trump-symbol')


@pytest.mark.parametrize('suit', list(Suit))
def test_trump_uses_the_same_painted_emblem_as_the_number_cards(suit):
    card = Card(f'{suit.value}-8', Kind.NUMBER, suit, 8)
    emblem = f'<span class="suit-emblem">{suit_icon(suit)}</span>'
    assert emblem in card_html(card)
    trump = _trump_html({'phase': 'playing', 'trump': suit, 'trump_card': card})
    assert f'<span class="trump-symbol s-{suit.value}">{emblem}</span>' in trump
    assert f'<span class="ts">{SUIT_LABEL[suit]}</span>' in trump


@pytest.mark.parametrize('phase, trump, label', [
    ('choosing_trump', None, 'Choosing…'),
    ('werewolf', Suit.OLIVE, 'Choosing…'),
    ('playing', None, 'No trump'),
])
def test_trump_without_a_confirmed_suit_keeps_the_revealed_card_and_status(phase, trump, label):
    revealed = Card('wizard', Kind.WIZARD)
    html = _trump_html({'phase': phase, 'trump': trump, 'trump_card': revealed})
    assert f'<span class="ts">{label}</span>' in html
    assert '<svg' not in html
    assert card_html(revealed, 'sm') in html


def test_trump_shows_no_card_when_nothing_was_revealed():
    html = _trump_html({'phase': 'playing', 'trump': None, 'trump_card': None})
    assert '<span class="ts">No trump</span>' in html
    assert 'class="card ' not in html


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
