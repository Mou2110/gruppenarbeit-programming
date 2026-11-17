"""Automated tests for cards, rules and scoring.

Run in the terminal (with the .venv activated):  pytest
"""
from game.cards import Card, Kind, Suit, build_deck
from game.rules import (
    dealer_chooses_trump, lead_suit, legal_cards, total_rounds,
    trick_winner, trump_from_card,
)
from game.scoring import round_score


# Small helpers to keep the tests short and readable.
def num(suit: Suit, value: int) -> Card:
    return Card(id=f'{suit.value}-{value}', kind=Kind.NUMBER, suit=suit, value=value)


WIZARD = Card(id='wizard-1', kind=Kind.WIZARD)
WIZARD2 = Card(id='wizard-2', kind=Kind.WIZARD)
JESTER = Card(id='jester-1', kind=Kind.JESTER)
JESTER2 = Card(id='jester-2', kind=Kind.JESTER)


# ---------- Deck ----------

def test_deck_has_60_unique_cards():
    deck = build_deck()
    assert len(deck) == 60
    assert len({c.id for c in deck}) == 60


def test_deck_has_13_cards_per_suit_and_4_wizards_and_jesters():
    deck = build_deck()
    for suit in Suit:
        assert sum(1 for c in deck if c.suit == suit) == 13
    assert sum(1 for c in deck if c.is_wizard) == 4
    assert sum(1 for c in deck if c.is_jester) == 4


# ---------- Rounds and trump ----------

def test_total_rounds():
    assert total_rounds(3) == 20
    assert total_rounds(4) == 15
    assert total_rounds(5) == 12
    assert total_rounds(6) == 10


def test_trump_from_card():
    assert trump_from_card(num(Suit.SUN, 4)) == Suit.SUN
    assert trump_from_card(JESTER) is None
    assert trump_from_card(None) is None
    assert dealer_chooses_trump(WIZARD)
    assert not dealer_chooses_trump(num(Suit.SUN, 4))


# ---------- Following suit ----------

def test_must_follow_suit_but_wizard_and_jester_always_allowed():
    hand = [num(Suit.SEA, 3), num(Suit.OLIVE, 7), WIZARD, JESTER]
    trick = [num(Suit.SEA, 9)]
    allowed = legal_cards(hand, trick)
    assert num(Suit.SEA, 3) in allowed
    assert WIZARD in allowed and JESTER in allowed
    assert num(Suit.OLIVE, 7) not in allowed


def test_without_lead_suit_everything_is_allowed():
    hand = [num(Suit.OLIVE, 7), num(Suit.SUN, 5)]
    assert legal_cards(hand, [num(Suit.SEA, 9)]) == hand


def test_jester_lead_then_first_number_sets_suit():
    trick = [JESTER, num(Suit.SUN, 2)]
    assert lead_suit(trick) == Suit.SUN


def test_wizard_lead_means_free_play():
    assert lead_suit([WIZARD, num(Suit.SUN, 2)]) is None
    assert lead_suit([JESTER, WIZARD]) is None


# ---------- Trick winner ----------

def test_highest_of_lead_suit_wins_without_trump():
    trick = [num(Suit.SEA, 5), num(Suit.SEA, 3), JESTER]
    assert trick_winner(trick, trump=None) == 0  # example from the rulebook


def test_trump_beats_lead_suit():
    trick = [num(Suit.SEA, 13), num(Suit.SARDINE, 2)]
    assert trick_winner(trick, trump=Suit.SARDINE) == 1


def test_off_suit_card_cannot_win():
    trick = [num(Suit.SEA, 2), num(Suit.OLIVE, 13)]
    assert trick_winner(trick, trump=Suit.SUN) == 0


def test_first_wizard_wins():
    trick = [num(Suit.SEA, 13), WIZARD, WIZARD2]
    assert trick_winner(trick, trump=Suit.SEA) == 1


def test_only_jesters_first_jester_wins():
    assert trick_winner([JESTER, JESTER2], trump=None) == 0


# ---------- Scoring ----------

def test_scoring_examples_from_rulebook():
    assert round_score(bid=0, tricks_won=0) == 20
    assert round_score(bid=1, tricks_won=1) == 30
    assert round_score(bid=1, tricks_won=0) == -10
    assert round_score(bid=2, tricks_won=1) == -10
    assert round_score(bid=2, tricks_won=5) == -30
