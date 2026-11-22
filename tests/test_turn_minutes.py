"""The host chooses the time limit per move for each lobby with a dial: off, or 0:30 to 5:00 in half minutes
(default 2 minutes)."""
import pickle

import pytest

from game.lobby import TURN_CHOICES, LobbyError, LobbyRegistry


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def wait(lobby, clock, seconds, step=0.5):
    for _ in range(int(seconds / step)):
        clock.now += step
        lobby.tick()


def two_humans(minutes=None):
    """Two humans and a bot; the game has started and it is a human's move."""
    clock = FakeClock()
    lobby = LobbyRegistry(clock=clock).create('host', 'Erik')
    lobby.join('p2', 'Marta')
    lobby.add_bot('host')
    for member in ('host', 'p2'):
        lobby.connect(member)
    if minutes is not None:
        lobby.update_settings('host', turn_minutes=minutes)
    lobby.set_ready('host', True)
    lobby.set_ready('p2', True)
    for _ in range(400):
        if lobby.waiting_on():
            break
        wait(lobby, clock, 0.5)
    return lobby, clock


def progress(lobby):
    game = lobby.game
    return game.round_number, game.phase, len(game.tricks_played), len(game.trick), game.current


def test_choices_are_half_minutes_up_to_five_and_two_is_the_default():
    assert TURN_CHOICES == (0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5)
    lobby = LobbyRegistry(clock=FakeClock()).create('host', 'Erik')
    assert lobby.settings.turn_minutes == 2


@pytest.mark.parametrize('minutes', [0.5, 1, 2.5, 5])
def test_the_chosen_time_limit_is_used(minutes):
    lobby, clock = two_humans(minutes)
    assert lobby.seconds_left() == minutes * 60
    before = progress(lobby)
    wait(lobby, clock, minutes * 60 - 5)
    assert progress(lobby) == before                   # still within the time
    wait(lobby, clock, 7)
    assert progress(lobby) != before                   # time is up: the move was made


def test_five_minutes_means_no_countdown_after_two_minutes():
    lobby, clock = two_humans(5)
    wait(lobby, clock, 150)
    assert lobby.turn_timer() is None                  # 2:30 left: the countdown only shows in the last 30 s


@pytest.mark.parametrize('minutes', [0, 6, -1, 2.25, 5.5, True, '2', None.__class__])
def test_other_values_are_rejected(minutes):
    lobby = LobbyRegistry(clock=FakeClock()).create('host', 'Erik')
    with pytest.raises(LobbyError):
        lobby.update_settings('host', turn_minutes=minutes)
    assert lobby.settings.turn_minutes == 2


def test_only_the_host_can_choose_the_minutes():
    lobby = LobbyRegistry(clock=FakeClock()).create('host', 'Erik')
    lobby.join('p2', 'Marta')
    with pytest.raises(LobbyError):
        lobby.update_settings('p2', turn_minutes=5)
    assert lobby.settings.turn_minutes == 2


def test_choosing_minutes_makes_everyone_press_ready_again():
    lobby = LobbyRegistry(clock=FakeClock()).create('host', 'Erik')
    lobby.join('p2', 'Marta')
    lobby.set_ready('p2', True)
    lobby.update_settings('host', turn_minutes=4)
    assert not lobby.member('p2').ready


def test_lobbies_saved_before_the_minutes_existed_get_two_minutes():
    lobby, clock = two_humans()
    del lobby.settings.__dict__['turn_minutes']        # like an old saved lobby
    restored = pickle.loads(pickle.dumps(lobby))
    assert restored.settings.turn_minutes == 2
    assert restored.seconds_left() is not None


@pytest.mark.parametrize('dial, expected', [(0, (False, 2)), (1, (True, 0.5)), (4, (True, 2)), (5, (True, 2.5)),
                                            (10, (True, 5))])
def test_the_dial_position_turns_into_a_setting(dial, expected):
    from views.lobby import dial_to_setting
    assert dial_to_setting(dial, current_minutes=2) == expected


@pytest.mark.parametrize('on, minutes, dial', [(False, 3, 0), (True, 0.5, 1), (True, 2, 4), (True, 5, 10)])
def test_the_setting_turns_into_a_dial_position(on, minutes, dial):
    from views.lobby import setting_to_dial
    assert setting_to_dial(on, minutes) == dial


@pytest.mark.parametrize('dial, text', [(0, 'Off'), (1, '0:30'), (3, '1:30'), (4, '2:00'), (10, '5:00')])
def test_the_dial_shows_minutes_and_seconds(dial, text):
    from views.lobby import dial_text
    assert dial_text(dial) == text
