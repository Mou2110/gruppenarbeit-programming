"""The waiting room says clearly how many players are still missing before the game can start."""
from game.lobby import LobbyRegistry
from views.lobby import missing_players_html


def lobby_with(players: int):
    lobby = LobbyRegistry().create('host', 'Erik')
    for i in range(players - 1):
        lobby.join(f'p{i}', f'Player {i}')
    return lobby


def test_alone_two_more_players_are_needed():
    html = missing_players_html(lobby_with(1))
    assert '2 more players needed' in html and 'Add a bot' in html


def test_two_players_need_one_more():
    assert '1 more player needed' in missing_players_html(lobby_with(2))


def test_bots_count_as_players():
    lobby = lobby_with(2)
    lobby.add_bot('host')
    assert missing_players_html(lobby) == ''


def test_with_enough_players_there_is_no_warning():
    assert missing_players_html(lobby_with(3)) == ''
