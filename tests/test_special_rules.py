"""Rule tests for all special cards – case by case, following the anniversary edition rulebook."""
import pytest

from game.cards import SPECIAL_KINDS, Card, Kind, Suit, build_deck
from game.rules import (
    Play, dealer_chooses_trump, lead_suit, legal_cards, trick_has_bomb, trick_winner, trump_from_card,
)

SEA, SARDINE, OLIVE, SUN = Suit.SEA, Suit.SARDINE, Suit.OLIVE, Suit.SUN


def num(suit, value):
    return Card(id=f'{suit.value}-{value}', kind=Kind.NUMBER, suit=suit, value=value)


def special(kind):
    return Card(id=kind.value, kind=kind)


WIZ, WIZ2 = Card('wizard-1', Kind.WIZARD), Card('wizard-2', Kind.WIZARD)
JES, JES2 = Card('jester-1', Kind.JESTER), Card('jester-2', Kind.JESTER)
SHIFT, DRAGON, FAIRY, BOMB, WOLF, JUGGLER, CLOUD = (special(k) for k in SPECIAL_KINDS)


def trick(*items):
    """Builds a trick: cards or (card, choice) – the choice is a suit or 'wizard'/'jester'."""
    plays = []
    for i, item in enumerate(items):
        if isinstance(item, tuple):
            card, choice = item
            if choice in ('wizard', 'jester'):
                plays.append(Play(i, card, as_wizard=choice == 'wizard'))
            else:
                plays.append(Play(i, card, suit=choice))
        else:
            plays.append(Play(i, item))
    return plays


# ---------------------------------------------------------------- Deck

def test_full_deck_has_67_unique_cards():
    deck = build_deck(SPECIAL_KINDS)
    assert len(deck) == 67
    assert len({c.id for c in deck}) == 67


def test_partial_special_cards_and_duplicates():
    assert len(build_deck([Kind.DRAGON, Kind.FAIRY])) == 62
    assert len(build_deck([Kind.BOMB, Kind.BOMB])) == 61


def test_only_special_kinds_allowed():
    with pytest.raises(ValueError):
        build_deck([Kind.WIZARD])


# ---------------------------------------------------------------- Trump card

@pytest.mark.parametrize('card', [WIZ, SHIFT, DRAGON, WOLF, JUGGLER, CLOUD])
def test_dealer_chooses_trump_for(card):
    assert dealer_chooses_trump(card)
    assert trump_from_card(card) is None


@pytest.mark.parametrize('card', [JES, FAIRY, BOMB])
def test_no_trump_for(card):
    assert not dealer_chooses_trump(card)
    assert trump_from_card(card) is None


def test_number_card_sets_trump():
    assert trump_from_card(num(SUN, 4)) == SUN
    assert not dealer_chooses_trump(num(SUN, 4))


# ---------------------------------------------------------------- Shapeshifter

def test_shapeshifter_as_wizard_wins():
    assert trick_winner(trick(num(SEA, 13), (SHIFT, 'wizard')), trump=SEA) == 1


def test_shapeshifter_as_wizard_after_wizard_loses():
    assert trick_winner(trick(WIZ, (SHIFT, 'wizard')), trump=None) == 0
    assert trick_winner(trick((SHIFT, 'wizard'), WIZ), trump=None) == 0


def test_shapeshifter_as_jester_loses():
    assert trick_winner(trick((SHIFT, 'jester'), num(SEA, 2)), trump=None) == 1


def test_shapeshifter_lead_behaves_like_its_role():
    assert lead_suit(trick((SHIFT, 'jester'), num(SUN, 2))) == SUN
    assert lead_suit(trick((SHIFT, 'wizard'), num(SUN, 2))) is None


def test_only_jesters_and_shapeshifter_as_jester_first_wins():
    assert trick_winner(trick((SHIFT, 'jester'), JES), trump=None) == 0


# ---------------------------------------------------------------- Dragon and Fairy

def test_dragon_beats_wizards():
    assert trick_winner(trick(WIZ, DRAGON, WIZ2), trump=SUN) == 1


def test_dragon_lead_is_free_play():
    assert lead_suit(trick(DRAGON, num(SEA, 3))) is None
    assert lead_suit(trick(JES, DRAGON, num(SEA, 3))) is None


def test_fairy_loses_every_trick_without_dragon():
    assert trick_winner(trick(FAIRY, num(SEA, 2)), trump=None) == 1
    assert trick_winner(trick(FAIRY, JES), trump=None) == 1          # even against the Jester
    assert trick_winner(trick(FAIRY, num(SEA, 4), num(SUN, 13)), trump=None) == 1


def test_fairy_lead_behaves_like_jester():
    assert lead_suit(trick(FAIRY, num(SEA, 4))) == SEA
    assert lead_suit(trick(FAIRY, WIZ)) is None


def test_fairy_beats_dragon_in_any_order():
    assert trick_winner(trick(DRAGON, FAIRY), trump=None) == 1
    assert trick_winner(trick(FAIRY, WIZ, DRAGON), trump=None) == 0
    assert trick_winner(trick(WIZ, DRAGON, num(SUN, 13), FAIRY), trump=SUN) == 3


# ---------------------------------------------------------------- Bomb

def test_bomb_detected():
    assert trick_has_bomb(trick(num(SEA, 2), BOMB))
    assert not trick_has_bomb(trick(num(SEA, 2), WIZ))


def test_bomb_has_no_value_would_be_winner_still_found():
    assert trick_winner(trick(BOMB, num(SEA, 5), num(SEA, 9)), trump=None) == 2
    assert trick_winner(trick(num(SEA, 5), BOMB, num(SUN, 13)), trump=SUN) == 2


def test_bomb_lead_behaves_like_jester():
    assert lead_suit(trick(BOMB, num(OLIVE, 5))) == OLIVE


def test_bomb_with_only_jesters_and_fairy():
    assert trick_winner(trick(BOMB, JES, JES2), trump=None) == 1
    assert trick_winner(trick(JES, BOMB, FAIRY), trump=None) == 0
    assert trick_winner(trick(BOMB, FAIRY, JES), trump=None) == 2


def test_bomb_with_dragon_and_fairy():
    assert trick_winner(trick(DRAGON, BOMB, FAIRY), trump=None) == 2


# ---------------------------------------------------------------- Juggler (7½) and Cloud (9¾)

def test_juggler_is_between_seven_and_eight():
    assert trick_winner(trick((JUGGLER, SEA), num(SEA, 7)), trump=None) == 0
    assert trick_winner(trick((JUGGLER, SEA), num(SEA, 7), num(SEA, 8)), trump=None) == 2


def test_cloud_is_between_nine_and_ten():
    assert trick_winner(trick((CLOUD, SEA), num(SEA, 9)), trump=None) == 0
    assert trick_winner(trick((CLOUD, SEA), num(SEA, 10)), trump=None) == 1
    assert trick_winner(trick(num(SEA, 9), (CLOUD, SEA)), trump=None) == 1


def test_juggler_and_cloud_in_chosen_trump_suit():
    assert trick_winner(trick(num(SEA, 13), (JUGGLER, SUN)), trump=SUN) == 1
    assert trick_winner(trick(num(SUN, 8), (JUGGLER, SUN)), trump=SUN) == 0
    assert trick_winner(trick((JUGGLER, SUN), (CLOUD, SUN)), trump=SUN) == 1


def test_juggler_in_off_suit_cannot_win():
    assert trick_winner(trick(num(SEA, 2), (JUGGLER, OLIVE)), trump=None) == 0
    assert trick_winner(trick(num(SEA, 2), (CLOUD, OLIVE)), trump=SUN) == 0


def test_juggler_and_cloud_lead_set_the_suit():
    assert lead_suit(trick((JUGGLER, SUN))) == SUN
    assert lead_suit(trick((CLOUD, OLIVE), num(SEA, 13))) == OLIVE
    assert trick_winner(trick((CLOUD, OLIVE), num(SEA, 13)), trump=None) == 0


def test_juggler_after_jester_lead_sets_the_suit():
    assert lead_suit(trick(JES, (JUGGLER, OLIVE), num(SEA, 3))) == OLIVE


def test_wizard_beats_juggler_and_cloud():
    assert trick_winner(trick((CLOUD, SUN), WIZ), trump=SUN) == 1


# ---------------------------------------------------------------- Following suit

def test_special_cards_may_always_be_played():
    hand = [num(SEA, 3), num(OLIVE, 7), SHIFT, DRAGON, FAIRY, BOMB, JUGGLER, CLOUD]
    allowed = legal_cards(hand, trick(num(SEA, 9)))
    assert num(OLIVE, 7) not in allowed
    assert all(c in allowed for c in hand if c != num(OLIVE, 7))


def test_juggler_and_cloud_in_hand_do_not_count_as_suit():
    hand = [JUGGLER, CLOUD, num(OLIVE, 7)]
    assert legal_cards(hand, trick(num(SEA, 9))) == hand


def test_must_follow_suit_chosen_for_juggler_lead():
    assert legal_cards([num(SEA, 3), num(OLIVE, 7)], trick((JUGGLER, SEA))) == [num(SEA, 3)]


def test_werewolf_is_never_playable():
    assert legal_cards([WOLF, num(SEA, 3)], []) == [num(SEA, 3)]
