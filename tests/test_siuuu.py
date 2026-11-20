"""Tests for the sound when CR7 is played: every player hears "Siuuu" once, at the moment the card lands."""
from game.cards import Card, Kind, Suit
from game.rules import Play
from views.table import SIUUU_JS, cheer_for_cr7

CR7 = Card('cr7', Kind.CR7)
SEA = Card('sea-5', Kind.NUMBER, Suit.SEA, 5)


def view(round_number=3, trick=(), last_trick=()):
    return {'round': round_number, 'trick': list(trick), 'last_trick': list(last_trick)}


def test_siuuu_plays_when_cr7_lands_in_the_trick():
    state = {}
    assert cheer_for_cr7(view(trick=[Play(0, SEA), Play(1, CR7)]), state) is True


def test_siuuu_plays_only_once_even_if_the_table_is_redrawn():
    state = {}
    v = view(trick=[Play(0, CR7)])
    assert cheer_for_cr7(v, state) is True
    assert cheer_for_cr7(v, state) is False            # same trick redrawn after another move
    assert cheer_for_cr7(view(trick=[Play(0, CR7), Play(1, SEA)]), state) is False


def test_siuuu_plays_again_when_cr7_comes_up_in_a_later_round():
    state = {}
    cheer_for_cr7(view(round_number=3, trick=[Play(0, CR7)]), state)
    assert cheer_for_cr7(view(round_number=5, trick=[Play(2, CR7)]), state) is True


def test_no_sound_without_cr7():
    assert cheer_for_cr7(view(trick=[Play(0, SEA)]), {}) is False


def test_siuuu_also_plays_when_cr7_was_the_last_card_of_the_trick():
    # The trick is complete at once and is shown as last_trick during the short pause.
    assert cheer_for_cr7(view(last_trick=[Play(0, SEA), Play(1, CR7)]), {}) is True


def test_the_sound_is_spoken_by_the_browser_no_audio_file():
    assert 'speechSynthesis' in SIUUU_JS and 'Siuuu' in SIUUU_JS
