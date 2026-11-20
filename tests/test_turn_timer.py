"""Tests for the time limit per move.

Every human has TURN_LIMIT seconds (2 minutes) for a move. The timer is only shown in the last
TIMER_SHOWN seconds (30). When the time is up, a bot makes this one move for them; they keep their seat
and play the next move themselves. Pressing "continue" after a round has the same limit.
"""
from game.engine import Phase
from game.lobby import TIMER_SHOWN, TURN_LIMIT, LobbyRegistry


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


def test_when_the_time_is_up_a_bot_makes_this_one_move():
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
