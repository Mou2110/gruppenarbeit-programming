"""Bots do not waste their strong cards (play-testing, 23.11.: "the bots play their specials far too early,
and when one plays a Wizard the next one just adds another").

All levels: a bot that still needs tricks wins as cheaply as possible, and throws its weakest card when it
cannot win the trick anyway; a bot that leads keeps its Wizards and Dragon while a sure number card will do.
"""
from game import bots
from game.cards import Card, Kind, Suit
from game.rules import Play


def card(text: str) -> Card:
    """'sea-5', 'wizard-1', 'jester-1', 'dragon' ... -> the card."""
    if text.split('-')[0] in [s.value for s in Suit]:
        suit, value = text.split('-')
        return Card(id=text, kind=Kind.NUMBER, suit=Suit(suit), value=int(value))
    return Card(id=text, kind=Kind(text.split('-')[0]))


def make_view(hand, players, me=0, trick=(), trump=None, round_number=5):
    """A view as game.view_for returns it, with only the keys the bots read. players: (bid, won, score)."""
    hand = [card(c) for c in hand]
    return {'round': round_number, 'my_index': me, 'my_hand': hand, 'my_hand_size': len(hand),
            'playable': [c.id for c in hand], 'trump': trump,
            'trick': [Play(player=seat, card=card(c)) for seat, c in trick],
            'players': [{'bid': bid, 'bid_change': 0, 'tricks_won': won, 'score': score, 'cards_left': len(hand)}
                        for bid, won, score in players]}


NEEDS_TWO = [(2, 0, 0), (1, 0, 0), (1, 0, 0)]      # seat 0 (the bot) bid 2 and has won nothing yet
NEEDS_NONE = [(0, 0, 0), (1, 0, 0), (1, 0, 0)]


def played(view):
    return bots.choose_card(view)[0]


def test_no_second_wizard_on_a_trick_that_a_wizard_already_wins():
    view = make_view(['wizard-2', 'sea-3', 'olive-9'], NEEDS_TWO, trick=[(1, 'wizard-1')])
    assert played(view) != 'wizard-2'                # it cannot win this trick, keep the Wizard


def test_when_it_cannot_win_it_throws_its_weakest_number_card():
    view = make_view(['wizard-2', 'sea-3', 'olive-9'], NEEDS_TWO, trick=[(1, 'dragon')])
    assert played(view) == 'sea-3'                   # nothing beats the Dragon here: keep the Wizard and the 9


def test_it_wins_with_the_cheapest_card_that_is_enough():
    view = make_view(['wizard-2', 'sea-13', 'sea-11'], NEEDS_TWO, trick=[(1, 'sea-5')])
    assert played(view) == 'sea-11'                  # the 11 already beats the 5, keep the 13 and the Wizard


def test_when_leading_it_plays_a_sure_number_card_before_a_wizard():
    view = make_view(['wizard-2', 'olive-13', 'sea-4'], NEEDS_TWO)
    assert played(view) == 'olive-13'


def test_a_bot_that_wants_no_tricks_gets_rid_of_a_wizard_that_loses_anyway():
    view = make_view(['wizard-2', 'jester-1', 'sea-12'], NEEDS_NONE, trick=[(1, 'wizard-1')])
    assert played(view) == 'wizard-2'                # the earlier Wizard wins, so this one is safe to dump


def test_a_bot_that_wants_no_tricks_leads_a_low_card_and_keeps_its_jester():
    view = make_view(['jester-1', 'sea-2', 'olive-12'], NEEDS_NONE)
    assert played(view) == 'sea-2'
