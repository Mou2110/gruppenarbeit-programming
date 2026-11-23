"""Bots do not waste their strong cards (play-testing, 23.11.: "the bots play their specials far too early,
and when one plays a Wizard the next one just adds another").

All levels: a bot never throws a strong card into a trick it cannot win, and uses number cards before
Wizards and the Dragon. Only Ruthless plays really cleverly (cheapest winner, dumps dangerous losers,
keeps its Jester), so the levels stay clearly different in strength.
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


def played(view, level='normal'):
    return bots.choose_card(view, level)[0]


def test_no_second_wizard_on_a_trick_that_a_wizard_already_wins():
    view = make_view(['wizard-2', 'sea-3', 'olive-9'], NEEDS_TWO, trick=[(1, 'wizard-1')])
    assert played(view) != 'wizard-2'                # it cannot win this trick, keep the Wizard


def test_when_it_cannot_win_it_throws_its_weakest_number_card():
    view = make_view(['wizard-2', 'sea-3', 'olive-9'], NEEDS_TWO, trick=[(1, 'dragon')])
    assert played(view) == 'sea-3'                   # nothing beats the Dragon here: keep the Wizard and the 9


def test_normal_wins_with_a_number_card_before_a_wizard():
    view = make_view(['wizard-2', 'sea-13', 'sea-11'], NEEDS_TWO, trick=[(1, 'sea-5')])
    assert played(view) == 'sea-13'                  # a number card that wins, the Wizard is kept


def test_ruthless_wins_with_the_cheapest_card_that_is_enough():
    view = make_view(['wizard-2', 'sea-13', 'sea-11'], NEEDS_TWO, trick=[(1, 'sea-5')])
    assert played(view, 'ruthless') == 'sea-11'      # the 11 already beats the 5, keep the 13 and the Wizard


def test_when_leading_it_plays_a_sure_number_card_before_a_wizard():
    view = make_view(['wizard-2', 'olive-13', 'sea-4'], NEEDS_TWO)
    assert played(view) == 'olive-13'


def test_ruthless_wanting_no_tricks_gets_rid_of_a_wizard_that_loses_anyway():
    view = make_view(['wizard-2', 'jester-1', 'sea-12'], NEEDS_NONE, trick=[(1, 'wizard-1')])
    assert played(view, 'ruthless') == 'wizard-2'    # the earlier Wizard wins, so this one is safe to dump


def test_ruthless_wanting_no_tricks_leads_a_low_card_and_keeps_its_jester():
    view = make_view(['jester-1', 'sea-2', 'olive-12'], NEEDS_NONE)
    assert played(view, 'ruthless') == 'sea-2'


def test_when_only_special_cards_win_it_uses_the_weakest_of_them():
    view = make_view(['cr7', 'wizard-2', 'sea-3'], NEEDS_TWO, trick=[(1, 'sea-13')])
    assert played(view) == 'wizard-2'                # the Wizard is enough, CR7 is kept


def test_a_bot_that_wants_no_tricks_loses_with_a_number_card_and_keeps_its_jester():
    view = make_view(['jester-1', 'sea-2'], NEEDS_NONE, trick=[(1, 'sea-13')])
    assert played(view) == 'sea-2'                   # the 2 loses just as well


# ---------------------------------------------------------------- the Cloud changed the bid
# Play-testing, 23.11.: "Thiago needed one more trick and played last, but played his Shapeshifter as a
# Jester although it would have won as a Wizard." His bid had been raised by one through the Cloud.

def test_a_bot_whose_bid_the_cloud_raised_still_wants_the_missing_trick():
    view = make_view(['shapeshifter', 'sea-2'], [(1, 1, 0), (1, 0, 0), (1, 1, 0)],
                     trick=[(1, 'sea-9'), (2, 'olive-4')])
    view['players'][0]['bid_change'] = 1             # bid 1, raised to 2 by the Cloud, 1 trick won
    for level in bots.LEVELS:
        card_id, _, as_wizard = bots.choose_card(view, level)
        assert (card_id, as_wizard) == ('shapeshifter', True), level


def test_a_bot_whose_bid_the_cloud_lowered_does_not_want_another_trick():
    view = make_view(['wizard-1', 'sea-2'], [(2, 1, 0), (1, 0, 0), (1, 1, 0)],
                     trick=[(1, 'sea-9'), (2, 'olive-4')])
    view['players'][0]['bid_change'] = -1            # bid 2, lowered to 1 by the Cloud, 1 trick won
    assert played(view) == 'sea-2'
