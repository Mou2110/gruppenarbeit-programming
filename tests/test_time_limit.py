"""Tests for the time limit per move.

The host chooses it for each lobby with a dial: off, or 0:30 to 5:00 in half minutes (default 2:00 = TURN_LIMIT).
The countdown is only shown in the last TIMER_SHOWN seconds (30). When the time is up, the game makes a simple
move on purpose (no clever bot move, so being slow does not pay off): the first allowed card from the left,
the lowest allowed bid. They keep their seat. Pressing "continue" after a round has the same limit.
Against bots only there is no time limit at all (feedback from the rehearsal on 21.11.).
"""
import pickle

import pytest

from game.cards import SPECIAL_KINDS, BONUS_KINDS, hand_order
from game.engine import Phase
from game.rules import legal_cards
from game.lobby import TIMER_SHOWN, TURN_CHOICES, TURN_LIMIT, LobbyError, LobbyRegistry
from views.start import start_practice

class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def started_game():
    """Erik (host) and Marta (both humans, online) play with one bot."""
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = registry.create('host', 'Erik')
    lobby.join('p2', 'Marta')
    for member_id in ('host', 'p2'):
        lobby.connect(member_id)
    lobby.add_bot('host')
    lobby.set_ready('host', True)
    lobby.set_ready('p2', True)
    return lobby, clock


def wait(lobby, clock, seconds, step=1.0):
    """Let time pass; the server ticks every step seconds."""
    end = clock.now + seconds
    while clock.now < end:
        clock.now = min(end, clock.now + step)
        lobby.tick()


def until_a_human_must_move(lobby, clock):
    """Let the bot move until a human is next (bots need about one second per move)."""
    for _ in range(100):
        if lobby.waiting_on():
            return lobby.waiting_on()[0]
        wait(lobby, clock, 1.0)
    raise AssertionError('no human turn')


def progress(lobby):
    game = lobby.game
    return (game.phase, game.round_number, game.current, len(game.tricks_played),
            tuple(p.bid for p in game.players), len(game.trick))


def test_the_limit_is_two_minutes_and_the_timer_shows_the_last_30_seconds():
    assert TURN_LIMIT == 120
    assert TIMER_SHOWN == 30


def test_the_game_waits_while_there_is_still_time():
    lobby, clock = started_game()
    until_a_human_must_move(lobby, clock)
    before = progress(lobby)
    wait(lobby, clock, TURN_LIMIT - 5)
    assert progress(lobby) == before


def test_when_the_time_is_up_a_move_is_made_for_them():
    lobby, clock = started_game()
    slow = until_a_human_must_move(lobby, clock)
    before = progress(lobby)
    wait(lobby, clock, TURN_LIMIT + 2)
    assert progress(lobby) != before
    assert not lobby.member(slow).is_bot             # the seat stays theirs


def test_the_timer_is_hidden_at_first_and_shown_in_the_last_30_seconds():
    lobby, clock = started_game()
    slow = until_a_human_must_move(lobby, clock)
    assert lobby.turn_timer() is None
    wait(lobby, clock, TURN_LIMIT - TIMER_SHOWN - 2)
    assert lobby.turn_timer() is None
    wait(lobby, clock, 7)
    who, seconds = lobby.turn_timer()
    assert who == [slow]
    assert 20 <= seconds <= TIMER_SHOWN


def test_every_move_starts_a_fresh_two_minutes():
    lobby, clock = started_game()
    until_a_human_must_move(lobby, clock)
    wait(lobby, clock, TURN_LIMIT + 2)                 # the first human runs out of time
    until_a_human_must_move(lobby, clock)
    before = progress(lobby)
    wait(lobby, clock, TURN_LIMIT - 5)
    assert progress(lobby) == before                   # the next one still has the full time


def test_bots_never_get_a_timer():
    lobby, clock = started_game()
    for _ in range(50):
        if lobby.waiting_on():
            break
        assert lobby.turn_timer() is None
        wait(lobby, clock, 0.3, step=0.3)


def test_after_a_round_continue_is_pressed_automatically_when_the_time_is_up():
    lobby, clock = started_game()
    for _ in range(20):                                # round 1: nobody moves, the timer plays for everyone
        if lobby.game.phase == Phase.ROUND_OVER:
            break
        wait(lobby, clock, TURN_LIMIT + 2)
    assert lobby.game.phase == Phase.ROUND_OVER
    lobby.vote_continue('host')
    wait(lobby, clock, TURN_LIMIT + 2)                 # Marta never presses continue
    assert lobby.game.round_number == 2


def test_after_the_game_the_time_limit_sends_everyone_back_to_the_waiting_room():
    lobby, clock = started_game()
    lobby.game.phase = Phase.GAME_OVER
    lobby.vote_continue('host')
    wait(lobby, clock, TURN_LIMIT + 2)                 # Marta has walked away
    assert lobby.game is None
    assert lobby.member('p2').ready is False           # she has to press "I'm ready" when she is back


def test_nothing_happens_while_nobody_is_online():
    lobby, clock = started_game()
    until_a_human_must_move(lobby, clock)
    before = progress(lobby)
    lobby.disconnect('host')
    lobby.disconnect('p2')
    wait(lobby, clock, 3 * TURN_LIMIT, step=5.0)
    assert progress(lobby) == before                   # the game waits until someone comes back


def test_a_restored_lobby_gives_the_full_time_again():
    lobby, clock = started_game()
    until_a_human_must_move(lobby, clock)
    wait(lobby, clock, TURN_LIMIT - 10)
    clock.now += 5000                                  # server restart: a new clock
    lobby.restored(clock)
    for member_id in ('host', 'p2'):
        lobby.connect(member_id)
    before = progress(lobby)
    wait(lobby, clock, TURN_LIMIT - 5)
    assert progress(lobby) == before


def test_the_time_limit_is_on_by_default():
    lobby, clock = started_game()
    assert lobby.settings.turn_timer is True


def test_the_host_can_switch_the_time_limit_off_and_then_the_game_waits():
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = registry.create('host', 'Erik')
    lobby.join('p2', 'Marta')
    for member_id in ('host', 'p2'):
        lobby.connect(member_id)
    lobby.add_bot('host')
    lobby.update_settings('host', turn_timer=False)
    lobby.set_ready('host', True)
    lobby.set_ready('p2', True)
    until_a_human_must_move(lobby, clock)
    before = progress(lobby)
    wait(lobby, clock, 3 * TURN_LIMIT, step=5.0)
    assert progress(lobby) == before                   # no time limit: the game waits
    assert lobby.turn_timer() is None                  # and no countdown is shown


def test_only_the_host_can_change_the_time_limit():
    import pytest
    from game.lobby import LobbyError
    lobby = LobbyRegistry(clock=FakeClock()).create('host', 'Erik')
    lobby.join('p2', 'Marta')
    with pytest.raises(LobbyError):
        lobby.update_settings('p2', turn_timer=False)
    assert lobby.settings.turn_timer is True


def test_lobbies_saved_before_the_setting_existed_have_the_time_limit_on():
    import pickle
    lobby, clock = started_game()
    del lobby.settings.__dict__['turn_timer']          # like an old saved lobby
    restored = pickle.loads(pickle.dumps(lobby))
    assert restored.settings.turn_timer is True


def test_when_time_is_up_while_bidding_the_lowest_allowed_bid_is_placed():
    lobby, clock = started_game()
    for _ in range(50):
        slow = until_a_human_must_move(lobby, clock)
        if lobby.game.phase == Phase.BIDDING:
            break
        wait(lobby, clock, TURN_LIMIT + 2)
    game = lobby.game
    lowest = min(game.allowed_bids())
    wait(lobby, clock, TURN_LIMIT + 2)
    assert next(p for p in game.players if p.id == slow).bid == lowest


def test_when_time_is_up_while_playing_the_first_allowed_card_from_the_left_is_played():
    lobby, clock = started_game()
    checked = 0
    for _ in range(400):
        if lobby.game is None or lobby.game.round_number > 4:
            break
        if lobby.waiting_on() and lobby.game.phase == Phase.PLAYING and lobby.game.awaiting_choice is None:
            game = lobby.game
            player = game.players[game.current]
            if len(player.hand) > 1:
                expected = min(legal_cards(player.hand, game.trick), key=hand_order)
                before = list(player.hand)
                wait(lobby, clock, TURN_LIMIT + 2)
                assert expected not in player.hand and expected in before
                checked += 1
                continue
        if lobby.game.phase == Phase.ROUND_OVER:
            lobby.vote_continue('host')
            lobby.vote_continue('p2')
        wait(lobby, clock, TURN_LIMIT + 2, step=TURN_LIMIT + 2)
    assert checked >= 3


def test_a_whole_game_can_be_finished_by_the_time_limit_alone_even_with_all_special_cards():
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = registry.create('host', 'Erik')
    lobby.join('p2', 'Marta')
    for member_id in ('host', 'p2'):
        lobby.connect(member_id)
    lobby.add_bot('host')
    lobby.update_settings('host', special_cards=list(SPECIAL_KINDS + BONUS_KINDS))
    lobby.set_ready('host', True)
    lobby.set_ready('p2', True)
    game = lobby.game
    for _ in range(20000):                             # nobody ever moves: every move comes from the timer
        if game.phase == Phase.GAME_OVER:
            break
        clock.now += TURN_LIMIT / 2
        lobby.tick()
    assert game.phase == Phase.GAME_OVER
    assert not any(m.is_bot for m in lobby.members if m.id in ('host', 'p2'))


# ---------------------------------------------------------------- Choosing the time limit (dial)

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


@pytest.mark.parametrize('minutes', [6, 2.25, True])   # too long, not a half minute, not a number
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


# ---------------------------------------------------------------- No time limit against bots

def run(registry, clock, seconds):
    for _ in range(int(seconds / 0.5)):
        clock.now += 0.5
        registry.tick_all()


def practice(players=4):
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = start_practice(registry, 'me', 'Me', players)
    lobby.connect('me')
    run(registry, clock, 30)                     # the bots make their first moves
    return registry, clock, lobby


def test_no_countdown_when_playing_only_against_bots():
    registry, clock, lobby = practice()
    assert lobby.waiting_on() == ['me']
    assert lobby.seconds_left() is None
    assert lobby.turn_timer() is None


def test_against_bots_you_can_think_as_long_as_you_like():
    registry, clock, lobby = practice()
    phase, hand = lobby.game.phase, len(lobby.game.players[0].hand)
    run(registry, clock, TURN_LIMIT * 5)         # 10 minutes, still at the table
    assert lobby.waiting_on() == ['me']
    assert (lobby.game.phase, len(lobby.game.players[0].hand)) == (phase, hand)   # nothing was played for me


def test_against_bots_a_long_break_keeps_the_game_and_your_move():
    registry, clock, lobby = practice()
    phase = lobby.game.phase
    lobby.disconnect('me')                       # e.g. "Back to start" or the phone goes to sleep
    run(registry, clock, 10 * 60)
    assert registry.get(lobby.code) is lobby     # the game still exists
    lobby.connect('me')
    run(registry, clock, 5)
    assert lobby.game.phase == phase and lobby.waiting_on() == ['me']   # and it is still my move


def test_with_two_humans_the_time_limit_still_applies():
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = registry.create('a', 'Ana')
    lobby.join('b', 'Ben')
    lobby.add_bot('a')
    for member in ('a', 'b'):
        lobby.connect(member)
        lobby.set_ready(member, True)
    run(registry, clock, 5)
    assert lobby.seconds_left() is not None


def test_when_the_other_human_leaves_for_good_the_time_limit_stops():
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = registry.create('a', 'Ana')
    lobby.join('b', 'Ben')
    lobby.add_bot('a')
    for member in ('a', 'b'):
        lobby.connect(member)
        lobby.set_ready(member, True)
    lobby.leave('b')                             # Ben's seat goes to a bot: Ana now plays only against bots
    run(registry, clock, 5)
    assert lobby.seconds_left() is None
