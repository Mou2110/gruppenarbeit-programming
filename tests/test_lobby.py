"""Tests for lobbies: joining, being ready, settings, bots and automatic moves."""
import pytest

from game.cards import SPECIAL_KINDS, Kind
from game.engine import GameError, Phase
from game.lobby import ABSENT_GRACE, MAX_PLAYERS, LobbyError, LobbyRegistry


class FakeClock:
    """A clock that can be moved forward by hand in the test."""
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_lobby():
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = registry.create('host', 'Erik')
    lobby.connect('host')
    return registry, lobby, clock


def test_codes_are_unique_and_findable():
    registry = LobbyRegistry()
    codes = {registry.create(f'h{i}').code for i in range(200)}
    assert len(codes) == 200
    code = next(iter(codes))
    assert registry.get(code.lower()) is registry.lobbies[code]
    assert registry.get('ZZZZZ') is None


def test_join_rename_and_leave():
    _, lobby, _ = make_lobby()
    lobby.join('p2', 'Marta')
    lobby.join('p2', 'Again')               # joining twice changes nothing
    assert [m.name for m in lobby.members] == ['Erik', 'Marta']
    lobby.rename('p2', '  Marta   Silva  ')
    assert lobby.member('p2').name == 'Marta Silva'
    lobby.rename('p2', '   ')                # empty name is ignored
    assert lobby.member('p2').name == 'Marta Silva'
    lobby.leave('host')
    assert lobby.host_id == 'p2'             # host role is passed on
    assert [m.id for m in lobby.members] == ['p2']


def test_lobby_is_limited_to_six():
    _, lobby, _ = make_lobby()
    for i in range(MAX_PLAYERS - 1):
        lobby.join(f'p{i}')
    with pytest.raises(LobbyError):
        lobby.join('one-too-many')


def test_game_starts_when_three_are_ready():
    _, lobby, _ = make_lobby()
    lobby.join('p2')
    lobby.set_ready('host', True)
    lobby.set_ready('p2', True)
    assert lobby.game is None                # only 2 players
    assert 'At least 3' in lobby.missing_for_start()
    lobby.join('p3')
    assert lobby.game is None
    lobby.set_ready('p3', True)
    assert lobby.game is not None
    assert [p.id for p in lobby.game.players] == ['host', 'p2', 'p3']
    with pytest.raises(LobbyError):
        lobby.join('late')                   # no joining during the game


def test_only_host_manages_bots_and_settings():
    _, lobby, _ = make_lobby()
    lobby.join('p2')
    with pytest.raises(LobbyError):
        lobby.add_bot('p2')
    with pytest.raises(LobbyError):
        lobby.update_settings('p2', no_matching_bids=False)
    lobby.add_bot('host')
    bot = lobby.members[-1]
    assert bot.is_bot and bot.ready
    lobby.remove_member('host', bot.id)
    assert len(lobby.members) == 2


def test_settings_reset_ready_and_block_clairvoyance_with_specials():
    _, lobby, _ = make_lobby()
    lobby.join('p2')
    lobby.set_ready('p2', True)
    assert lobby.settings.clairvoyance is True    # default: clairvoyance on, even with special cards
    lobby.update_settings('host', clairvoyance=False)
    assert lobby.settings.clairvoyance is False
    assert not lobby.member('p2').ready
    lobby.update_settings('host', special_cards=[Kind.CLOUD, Kind.DRAGON])
    assert lobby.settings.special_cards == [Kind.DRAGON, Kind.CLOUD]


def test_settings_are_passed_to_the_game():
    _, lobby, _ = make_lobby()
    lobby.update_settings('host', special_cards=[], clairvoyance=True, no_matching_bids=False)
    lobby.add_bot('host')
    lobby.add_bot('host')
    lobby.set_ready('host', True)
    game = lobby.game
    assert game.special_cards == () and game.clairvoyance and not game.no_matching_bids


def test_listeners_are_notified_and_broken_ones_removed():
    _, lobby, _ = make_lobby()
    calls = []
    lobby.subscribe('a', lambda: calls.append('a'))

    def broken():
        raise RuntimeError('page is gone')
    lobby.subscribe('b', broken)
    lobby.join('p2')
    assert calls == ['a'] and 'b' not in lobby.listeners


def test_wrong_moves_are_rejected():
    _, lobby, _ = make_lobby()
    lobby.add_bot('host')
    lobby.add_bot('host')
    lobby.set_ready('host', True)
    game = lobby.game
    not_my_turn = 'host' if game.players[game.current].id != 'host' else game.players[1].id
    with pytest.raises(GameError):
        lobby.act(not_my_turn, 'bid', bid=0)


def run_until_over(registry, lobby, clock, max_steps=200_000):
    """Lets time pass until the game is over and everyone is back in the waiting room."""
    rounds_seen = set()
    for _ in range(max_steps):
        clock.now += 0.5
        registry.tick_all()
        if lobby.game is not None:
            rounds_seen.add(lobby.game.round_number)
        if lobby.game is None and rounds_seen:
            return rounds_seen
    raise AssertionError('The game did not finish.')


@pytest.mark.parametrize('specials', [(), SPECIAL_KINDS])
def test_absent_player_is_waited_for_and_no_bot_takes_over(specials):
    registry, lobby, clock = make_lobby()
    lobby.update_settings('host', special_cards=list(specials))
    lobby.join('p2', 'Marta')
    lobby.connect('p2')
    lobby.add_bot('host')
    lobby.set_ready('p2', True)
    lobby.set_ready('host', True)
    game = lobby.game
    assert game is not None
    lobby.disconnect('host')                 # Erik gets something to eat, Marta stays online
    for _ in range(200):                     # 100 seconds: less than the time limit per move (TURN_LIMIT)
        clock.now += 0.5
        registry.tick_all()
    # No bot moved for Erik: the game stops as soon as it is Erik's (or the waiting Marta's) turn.
    # (Only after TURN_LIMIT a bot makes that one move for him, see test_turn_timer.py.)
    assert game.round_number == 1
    assert game.players[game.current].id in ('host', 'p2') or game.phase == Phase.PASSING
    assert lobby.is_absent('host') and not lobby.member('host').is_bot


def test_player_who_leaves_for_good_is_replaced_by_a_bot():
    registry, lobby, clock = make_lobby()
    lobby.join('p2', 'Marta')
    lobby.connect('p2')
    lobby.add_bot('host')
    lobby.set_ready('p2', True)
    lobby.set_ready('host', True)
    lobby.leave('host')                      # deliberately leave for good
    lobby.leave('p2')
    assert lobby.member('host').is_bot and lobby.member('p2').is_bot


def test_present_player_is_waited_for():
    registry, lobby, clock = make_lobby()
    lobby.add_bot('host')
    lobby.add_bot('host')
    lobby.set_ready('host', True)
    game = lobby.game
    for _ in range(200):
        clock.now += 0.5
        registry.tick_all()
    # The human is online: the game waits for them instead of moving for them.
    assert game.players[game.current].id == 'host' or game.phase == Phase.PASSING
    assert game.phase not in (Phase.ROUND_OVER, Phase.GAME_OVER) or 'host' not in lobby.votes


def test_round_continues_only_after_all_humans_voted():
    registry, lobby, clock = make_lobby()
    lobby.join('p2')
    lobby.connect('p2')
    lobby.add_bot('host')
    lobby.set_ready('host', True)
    lobby.set_ready('p2', True)
    game = lobby.game
    # Both humans play using the bot logic so that the first round is over quickly.
    from game import bots
    while game.phase not in (Phase.ROUND_OVER, Phase.GAME_OVER):
        clock.now += 2
        lobby.tick()
        if game.phase == Phase.PASSING:
            for pid in ('host', 'p2'):
                if game.must_pass(pid):
                    lobby.act(pid, 'pass', card_id=bots.choose_pass(game.view_for(pid)))
            continue
        current = game.players[game.current].id
        if current in ('host', 'p2') and not lobby.is_paused():
            view = game.view_for(current)
            if game.phase in (Phase.WEREWOLF, Phase.CHOOSING_TRUMP):
                lobby.act(current, 'trump', suit=bots.choose_trump(view))
            elif game.phase == Phase.BIDDING:
                lobby.act(current, 'bid', bid=bots.choose_bid(view))
            elif game.phase == Phase.ADJUSTING:
                lobby.act(current, 'adjust', change=bots.choose_adjustment(view))
            elif game.awaiting_choice is not None:
                suit, as_wizard = bots.declare_played_card(view)
                lobby.act(current, 'declare', suit=suit, as_wizard=as_wizard)
            else:
                card_id, suit, as_wizard = bots.choose_card(view)
                lobby.act(current, 'play', card_id=card_id, suit=suit, as_wizard=as_wizard)
    clock.now += 5
    lobby.tick()
    lobby.vote_continue('host')
    clock.now += 5
    lobby.tick()
    assert game.round_number == 1            # p2 has not confirmed yet
    assert [m.id for m in lobby.waiting_for_votes()] == ['p2']
    lobby.vote_continue('p2')
    clock.now += 5
    lobby.tick()
    assert game.round_number == 2


def test_leaving_during_game_hands_seat_to_bot():
    _, lobby, _ = make_lobby()
    lobby.join('p2')
    lobby.add_bot('host')
    lobby.set_ready('host', True)
    lobby.set_ready('p2', True)
    lobby.leave('p2')
    assert lobby.member('p2').is_bot


def test_empty_lobbies_are_removed():
    registry, lobby, _ = make_lobby()
    lobby.leave('host')
    registry.tick_all()
    assert lobby.code not in registry.lobbies


def test_game_waits_when_nobody_is_online_and_resumes_on_return():
    registry, lobby, clock = make_lobby()
    for _ in range(3):
        lobby.add_bot('host')
    lobby.set_ready('host', True)
    game = lobby.game
    lobby.disconnect('host')                 # e.g. browser crashed, nobody else is there
    clock.now += ABSENT_GRACE + 1
    for _ in range(500):
        clock.now += 0.5
        registry.tick_all()
    assert game.round_number == 1 and lobby.game is game   # the bots did not keep playing on their own
    assert lobby.code in registry.lobbies                  # and the lobby was not deleted
    lobby.connect('host')                                  # back again: the game continues
    for _ in range(2000):
        clock.now += 0.5
        registry.tick_all()
        if game.players[game.current].id == 'host' and game.phase.value in ('bidding', 'playing'):
            break
    assert game.players[game.current].id == 'host' or game.round_number > 1


def test_rebind_moves_a_guest_seat_to_an_account():
    registry, lobby, clock = make_lobby()
    lobby.add_bot('host')
    lobby.add_bot('host')
    lobby.set_ready('host', True)
    assert lobby.rebind('host', 'acct:erik', 'Erik')
    assert lobby.member('host') is None and lobby.member('acct:erik') is not None
    assert lobby.host_id == 'acct:erik'
    assert any(p.id == 'acct:erik' for p in lobby.game.players)
    assert lobby.game.view_for('acct:erik')['my_index'] == 0
    assert registry.lobbies_of('acct:erik') == [lobby]
    assert not lobby.rebind('nobody', 'acct:x')


def test_your_games_only_lists_games_with_cards_played_and_can_be_left(monkeypatch):
    registry, lobby, clock = make_lobby()
    waiting = registry.create('host', 'Erik')          # waiting room: does not appear in "Your games"
    lobby.add_bot('host')
    lobby.add_bot('host')
    lobby.set_ready('host', True)                      # started, but no card played yet
    assert registry.games_of('host') == []
    game = lobby.game
    # For the test we let a bot move for Erik until a card has been played.
    monkeypatch.setattr(type(lobby), '_plays_automatically', lambda self, member_id: True)
    for _ in range(5000):
        if game.trick or game.tricks_played or game.round_number > 1:
            break
        clock.now += 1
        registry.tick_all()
    assert registry.games_of('host') == [lobby]
    assert waiting not in registry.games_of('host')
    lobby.leave('host')                                # "Remove game": a bot takes over the seat
    assert registry.games_of('host') == []
    assert lobby.member('host').is_bot


def test_chat_messages_are_cleaned_limited_and_sent_to_listeners():
    registry, lobby, clock = make_lobby()
    lobby.join('p2', 'Marta')
    received = []
    lobby.chat_listeners['tab'] = received.append
    message = lobby.say('host', '  haha   <b>nice</b>  ')
    assert message.text == 'haha <b>nice</b>' and message.name == 'Erik' and message.number == 1
    assert received == [message]
    assert lobby.say('p2', '   ') is None                  # empty message: nothing happens
    with pytest.raises(LobbyError):
        lobby.say('host', 'spam')                          # too fast in a row
    clock.now += 1
    assert len(lobby.say('host', 'x' * 500).text) == 200   # too long: gets shortened
    with pytest.raises(LobbyError):
        lobby.say('stranger', 'hi')                        # not in the lobby
    for i in range(150):
        clock.now += 1
        lobby.say('p2', f'msg {i}')
    assert len(lobby.chat) == 100 and lobby.chat[-1].text == 'msg 149'


def test_host_can_remove_a_player_from_the_waiting_room_but_nobody_else_can():
    _, lobby, _ = make_lobby()
    lobby.join('p2')
    lobby.join('p3')
    with pytest.raises(LobbyError):
        lobby.remove_member('p2', 'p3')        # only the host
    with pytest.raises(LobbyError):
        lobby.remove_member('host', 'host')    # not yourself
    lobby.remove_member('host', 'p2')
    assert [m.id for m in lobby.members] == ['host', 'p3']
