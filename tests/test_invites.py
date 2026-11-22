"""Tests for inviting friends: who is online, and invitations into a lobby that pop up for the friend."""
import pytest

from game.lobby import LobbyRegistry
from game.presence import INVITE_GAP, InviteError, Presence
from views import invites, stats


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def presence():
    return Presence(clock=FakeClock())


def test_nobody_is_online_at_first(presence):
    assert not presence.is_online('marta')


def test_online_while_at_least_one_page_is_open(presence):
    presence.connect('tab-1', 'marta', lambda invite: None)
    presence.connect('tab-2', 'marta', lambda invite: None)
    assert presence.is_online('marta')
    presence.disconnect('tab-1')
    assert presence.is_online('marta')                 # the second tab is still open
    presence.disconnect('tab-2')
    assert not presence.is_online('marta')
    presence.disconnect('tab-2')                       # closing twice does nothing


def test_invite_pops_up_on_every_open_page_of_the_friend(presence):
    got = []
    presence.connect('tab-1', 'marta', got.append)
    presence.connect('tab-2', 'marta', got.append)
    presence.connect('tab-3', 'jan', got.append)       # someone else: gets nothing
    assert presence.invite('erik', 'Erik', 'marta', 'K7QX') == 2
    assert [(i.sender_name, i.code) for i in got] == [('Erik', 'K7QX'), ('Erik', 'K7QX')]


def test_cannot_invite_a_friend_who_is_offline(presence):
    with pytest.raises(InviteError):
        presence.invite('erik', 'Erik', 'marta', 'K7QX')


def test_cannot_invite_yourself(presence):
    presence.connect('tab-1', 'erik', lambda invite: None)
    with pytest.raises(InviteError):
        presence.invite('erik', 'Erik', 'erik', 'K7QX')


def test_inviting_the_same_friend_again_needs_a_short_break(presence):
    got = []
    presence.connect('tab-1', 'marta', got.append)
    presence.invite('erik', 'Erik', 'marta', 'K7QX')
    with pytest.raises(InviteError):                   # no spam: 50 invites per second are not possible
        presence.invite('erik', 'Erik', 'marta', 'K7QX')
    presence.connect('tab-2', 'jan', got.append)
    presence.invite('erik', 'Erik', 'jan', 'K7QX')     # another friend can be invited right away
    presence.clock.now += INVITE_GAP
    presence.invite('erik', 'Erik', 'marta', 'K7QX')   # after the break it works again
    assert len(got) == 3


def test_closed_page_that_fails_is_forgotten(presence):
    def broken(invite):
        raise RuntimeError('page no longer exists')
    presence.connect('tab-1', 'marta', broken)
    assert presence.invite('erik', 'Erik', 'marta', 'K7QX') == 0
    assert not presence.is_online('marta')


def friend(account, name):
    return {'account': account, 'name': name, 'games': 0, 'wins': 0}


def test_lobby_offers_only_online_friends_who_are_not_in_it_yet(presence):
    lobby = LobbyRegistry().create('acct:erik', 'Erik')
    lobby.join('acct:jan', 'Jan')
    for account in ('marta', 'jan'):
        presence.connect(f'tab-{account}', account, lambda invite: None)
    friends = [friend('jan', 'Jan'), friend('marta', 'Marta'), friend('rui', 'Rui')]
    # Jan already sits in the lobby, Rui is offline: only Marta can be invited.
    assert [f['name'] for f in invites.invitable(friends, lobby, presence)] == ['Marta']


def test_no_invites_once_the_game_has_started(presence):
    lobby = LobbyRegistry().create('acct:erik', 'Erik')
    for _ in range(2):
        lobby.add_bot('acct:erik')
    lobby.set_ready('acct:erik', True)                 # three players: the game starts
    presence.connect('tab-marta', 'marta', lambda invite: None)
    assert lobby.game is not None
    assert invites.invitable([friend('marta', 'Marta')], lobby, presence) == []


def test_popup_text_escapes_the_name():
    html = invites.invite_html('<Erik>', 'K7QX')
    assert '&lt;Erik&gt;' in html and '<Erik>' not in html
    assert 'K7QX' in html


def test_friends_list_shows_who_is_online():
    assert 'online' in stats.friend_html(friend('marta', 'Marta'), online=True)
    assert 'online' not in stats.friend_html(friend('marta', 'Marta'))


def test_friend_in_a_running_game_cannot_be_invited(presence):
    lobbies = LobbyRegistry()
    running = lobbies.create('acct:marta', 'Marta')
    for _ in range(2):
        running.add_bot('acct:marta')
    running.set_ready('acct:marta', True)              # Marta is playing a game right now
    presence.connect('tab-marta', 'marta', lambda invite: None)
    lobby = lobbies.create('acct:erik', 'Erik')
    assert invites.invitable([friend('marta', 'Marta')], lobby, presence, lobbies) == []
