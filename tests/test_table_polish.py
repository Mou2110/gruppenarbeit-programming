"""Play-testing polish on the game table (22.11.): card explanations, trump in the middle, clearer trick winner."""
from game.cards import OPTIONAL_KINDS, Card, Kind, Suit
from game.rules import Play
from views.table import CARD_INFO, _leader, _table_trump_html, _trick_html, hand_card_html


def num(suit, value):
    return Card(f'{suit.value}-{value}', Kind.NUMBER, suit, value)


def view(**changes):
    v = {'phase': 'playing', 'trump': Suit.SEA, 'trump_card': num(Suit.SEA, 5), 'trick': [], 'last_trick': [],
         'players': [{'name': n} for n in ('Me', 'Ana', 'Ben')], 'my_index': 0}
    v.update(changes)
    return v


def test_every_special_card_and_wizard_and_jester_has_an_explanation():
    for kind in (Kind.WIZARD, Kind.JESTER, *OPTIONAL_KINDS):
        name, text = CARD_INFO[kind.value]
        assert name and len(text) > 10


def test_special_cards_in_the_hand_get_a_question_mark_number_cards_do_not():
    assert 'class="card-info" data-kind="dragon"' in hand_card_html(Card('dragon', Kind.DRAGON))
    assert 'card-info' not in hand_card_html(num(Suit.SUN, 3))


def test_trump_card_and_suit_lie_in_the_middle_of_the_table():
    assert 'Trump: Sea' in _table_trump_html(view())
    assert 'No trump' in _table_trump_html(view(trump=None, trump_card=Card('jester', Kind.JESTER)))
    assert 'Trump: choosing' in _table_trump_html(view(phase='choosing_trump', trump=None))
    assert 'no-trump-card' in _table_trump_html(view(trump=None, trump_card=None))   # last round, no card left


def test_the_leading_card_is_marked_and_its_player_gets_the_crown():
    trick = [Play(0, num(Suit.SEA, 3)), Play(1, num(Suit.SEA, 9)), Play(2, num(Suit.SUN, 12))]
    v = view(trick=trick)
    html = _trick_html(v, paused=False)
    assert html.count(' best') == 1 and 'Leading' in html
    assert _leader(v, paused=False) == 1                       # Sea is trump: the Sea 9 leads


def test_after_the_trick_the_cards_slide_to_the_winner():
    trick = [Play(0, num(Suit.SEA, 3)), Play(1, num(Suit.SEA, 9)), Play(2, num(Suit.SUN, 12))]
    html = _trick_html(view(last_trick=trick), paused=True)
    assert html.count('collect') == 3 and '--to-x' in html
    assert _trick_html(view(last_trick=trick), paused=False) == ''   # pause over: table is empty


def test_nobody_gets_the_crown_on_an_empty_table():
    assert _leader(view(), paused=False) is None
