"""Tests for the "Play again" button at the end of a game.

At the end of a game everyone presses "Continue" and lands in the waiting room, where each person has to
press "I'm ready" again. "Play again" skips that: the person is ready right away, and as soon as every
human has voted, the next game starts with the same people, bots and settings.
"""
from game.engine import Phase
from game.lobby import LobbyRegistry


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def finished_game():
    """A lobby with two humans (host, p2) and one bot, whose game has just ended."""
    registry = LobbyRegistry(clock=FakeClock())
    lobby = registry.create('host', 'Erik')
    lobby.join('p2', 'Marta')
    for member_id in ('host', 'p2'):
        lobby.connect(member_id)
    lobby.add_bot('host')
    lobby.set_ready('host', True)
    lobby.set_ready('p2', True)
    assert lobby.game is not None
    lobby.game.phase = Phase.GAME_OVER
    return lobby


def test_when_every_human_plays_again_a_new_game_starts_with_the_same_players():
    lobby = finished_game()
    players_before = [p.id for p in lobby.game.players]
    lobby.play_again('host')
    assert lobby.game.phase == Phase.GAME_OVER         # still waiting for Marta
    lobby.play_again('p2')
    assert lobby.game.phase != Phase.GAME_OVER
    assert lobby.game.round_number == 1
    assert [p.id for p in lobby.game.players] == players_before
    assert all(p.score == 0 for p in lobby.game.players)


def test_someone_who_only_presses_continue_is_not_ready_and_the_game_waits_for_them():
    lobby = finished_game()
    lobby.play_again('host')
    lobby.vote_continue('p2')
    assert lobby.game is None                           # back in the waiting room
    assert lobby.member('host').ready is True
    assert lobby.member('p2').ready is False
    assert lobby.missing_for_start() == 'Waiting for 1 player to get ready'
    lobby.set_ready('p2', True)
    assert lobby.game is not None                       # starts as soon as Marta is ready


def test_the_order_does_not_matter():
    lobby = finished_game()
    lobby.vote_continue('p2')
    lobby.play_again('host')
    assert lobby.game is None
    assert lobby.member('host').ready is True and lobby.member('p2').ready is False


def test_nobody_plays_again_by_default_everyone_has_to_get_ready_again():
    lobby = finished_game()
    lobby.vote_continue('host')
    lobby.vote_continue('p2')
    assert lobby.game is None
    assert not lobby.member('host').ready and not lobby.member('p2').ready


def test_bots_never_block_the_rematch():
    lobby = finished_game()
    lobby.play_again('host')
    lobby.play_again('p2')
    assert any(m.is_bot for m in lobby.members)
    assert lobby.game is not None and lobby.game.phase != Phase.GAME_OVER


def test_a_player_who_left_during_the_game_does_not_block_the_rematch():
    lobby = finished_game()
    lobby.leave('p2')                                   # a bot takes over the seat
    lobby.play_again('host')
    assert lobby.game is not None and lobby.game.phase != Phase.GAME_OVER


def test_pressing_play_again_twice_changes_nothing():
    lobby = finished_game()
    lobby.play_again('host')
    lobby.play_again('host')
    lobby.play_again('p2')
    assert lobby.game.round_number == 1 and lobby.game.phase != Phase.GAME_OVER


def test_play_again_does_nothing_in_the_middle_of_a_game():
    lobby = finished_game()
    lobby.game.phase = Phase.PLAYING
    game = lobby.game
    lobby.play_again('host')
    lobby.play_again('p2')
    assert lobby.game is game
    assert lobby.member('host').ready is True           # ready from the start, nothing else changed
    assert lobby.votes == set()


def test_play_again_after_a_round_does_not_end_the_game():
    lobby = finished_game()
    lobby.game.phase = Phase.ROUND_OVER
    game = lobby.game
    lobby.play_again('host')
    lobby.play_again('p2')
    assert lobby.game is game


def test_a_stranger_cannot_play_again():
    lobby = finished_game()
    lobby.play_again('stranger')
    lobby.play_again('p2')
    assert lobby.game.phase == Phase.GAME_OVER          # still waiting for Erik


def test_no_new_game_with_fewer_than_three_players():
    lobby = finished_game()
    lobby.play_again('host')
    lobby.vote_continue('p2')                           # Marta goes back to the waiting room ...
    lobby.leave('p2')                                   # ... and leaves
    assert lobby.game is None
    assert lobby.missing_for_start() == 'At least 3 players are needed'
