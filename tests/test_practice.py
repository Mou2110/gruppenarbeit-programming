"""Tests for "Practice against bots": you choose how many players sit at the table (3 to 6)."""
import pytest

from game.lobby import MAX_PLAYERS, MIN_PLAYERS, LobbyRegistry
from views.start import PRACTICE_SIZES, start_practice


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_every_table_size_from_3_to_6_can_be_chosen():
    assert PRACTICE_SIZES == list(range(MIN_PLAYERS, MAX_PLAYERS + 1)) == [3, 4, 5, 6]


@pytest.mark.parametrize('players', [3, 4, 5, 6])
def test_practice_starts_right_away_with_you_and_the_rest_bots(players):
    registry = LobbyRegistry(clock=FakeClock())
    lobby = start_practice(registry, 'me', 'Moritz', players)
    assert lobby.game is not None                       # the game starts immediately
    assert len(lobby.game.players) == players
    humans = [m for m in lobby.members if not m.is_bot]
    assert [m.id for m in humans] == ['me']
    assert lobby.is_host('me')


@pytest.mark.parametrize('players', [0, 2, 7, 100])
def test_impossible_table_sizes_are_rejected(players):
    registry = LobbyRegistry(clock=FakeClock())
    with pytest.raises(ValueError):
        start_practice(registry, 'me', 'Moritz', players)
    assert registry.lobbies == {}                       # no half-built lobby is left behind
