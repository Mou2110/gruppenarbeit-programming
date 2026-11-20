"""Tests for the sound when CR7 is played: every player hears "Siuuu" once, at the moment the card lands.

The browser remembers in which game (game_number) and round it last cheered, so a rematch starts fresh.
"""
from game.cards import Card, Kind, Suit
from game.rules import Play
from views.table import SIUUU_JS, cheer_for_cr7

CR7 = Card('cr7', Kind.CR7)
SEA = Card('sea-5', Kind.NUMBER, Suit.SEA, 5)


def view(round_number=3, trick=(), last_trick=()):
    return {'round': round_number, 'trick': list(trick), 'last_trick': list(last_trick)}


def test_siuuu_plays_when_cr7_lands_in_the_trick():
    state = {}
    assert cheer_for_cr7(view(trick=[Play(0, SEA), Play(1, CR7)]), state, 1) is True


def test_siuuu_plays_only_once_even_if_the_table_is_redrawn():
    state = {}
    v = view(trick=[Play(0, CR7)])
    assert cheer_for_cr7(v, state, 1) is True
    assert cheer_for_cr7(v, state, 1) is False            # same trick redrawn after another move
    assert cheer_for_cr7(view(trick=[Play(0, CR7), Play(1, SEA)]), state, 1) is False


def test_siuuu_plays_again_when_cr7_comes_up_in_a_later_round():
    state = {}
    cheer_for_cr7(view(round_number=3, trick=[Play(0, CR7)]), state, 1)
    assert cheer_for_cr7(view(round_number=5, trick=[Play(2, CR7)]), state, 1) is True


def test_no_sound_without_cr7():
    assert cheer_for_cr7(view(trick=[Play(0, SEA)]), {}, 1) is False


def test_siuuu_also_plays_when_cr7_was_the_last_card_of_the_trick():
    # The trick is complete at once and is shown as last_trick during the short pause.
    assert cheer_for_cr7(view(last_trick=[Play(0, SEA), Play(1, CR7)]), {}, 1) is True


def test_the_sound_is_spoken_by_the_browser_no_audio_file():
    assert 'speechSynthesis' in SIUUU_JS and 'Siuuu' in SIUUU_JS


def test_siuuu_plays_again_after_a_rematch_in_the_same_round_number():
    # Found by Jakob: CR7 in round 3 of game 1, then again in round 3 of the rematch.
    state = {}
    assert cheer_for_cr7(view(round_number=3, trick=[Play(0, CR7)]), state, 1) is True
    assert cheer_for_cr7(view(round_number=3, trick=[Play(1, CR7)]), state, 2) is True


def test_every_new_game_in_a_lobby_gets_a_new_number():
    from game.engine import Phase
    from game.lobby import LobbyRegistry
    lobby = LobbyRegistry(clock=lambda: 1000.0).create('host', 'Erik')
    lobby.join('p2', 'Marta')
    for member_id in ('host', 'p2'):
        lobby.connect(member_id)
    lobby.add_bot('host')
    lobby.set_ready('host', True)
    lobby.set_ready('p2', True)
    first = lobby.game_number
    lobby.game.phase = Phase.GAME_OVER
    lobby.play_again('host')
    lobby.play_again('p2')                             # rematch
    assert lobby.game_number == first + 1


def test_lobbies_saved_before_game_numbers_existed_still_work():
    import pickle
    from game.lobby import LobbyRegistry
    lobby = LobbyRegistry(clock=lambda: 1000.0).create('host', 'Erik')
    lobby.__dict__.pop('game_number', None)            # like an old saved lobby
    assert pickle.loads(pickle.dumps(lobby)).game_number == 0
