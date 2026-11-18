"""Tests for saving: lobbies and running games survive a server restart."""
from game.engine import Phase
from game.lobby import LobbyRegistry
from game.persistence import SqliteStore


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def run_until(registry, clock, condition, steps=20000):
    for _ in range(steps):
        if condition():
            return True
        clock.now += 2.0
        registry.tick_all()
    return condition()


def started_registry(tmp_path):
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    store = SqliteStore(tmp_path / 'db.sqlite')
    registry.attach_store(store)
    lobby = registry.create('host', 'Erik')
    lobby.connect('host')
    for _ in range(3):
        lobby.add_bot('host')
    lobby.set_ready('host', True)
    return registry, lobby, clock, store


def test_lobby_in_game_survives_restart(tmp_path):
    registry, lobby, clock, store = started_registry(tmp_path)
    assert lobby.game is not None
    # let the bots make a few moves, then it is the human's turn
    run_until(registry, clock, lambda: lobby.game.players[lobby.game.current].id == 'host'
              and lobby.game.phase in (Phase.BIDDING, Phase.PLAYING))
    before = lobby.game.view_for('host')
    lobby.say('host', 'brb, getting food')
    registry.tick_all()
    store.flush()

    # "Restart": new registry, new clock, same database
    clock2 = FakeClock()
    clock2.now = 5.0
    registry2 = LobbyRegistry(clock=clock2)
    registry2.attach_store(SqliteStore(tmp_path / 'db.sqlite'))
    restored = registry2.get(lobby.code)
    assert restored is not None and restored is not lobby
    after = restored.game.view_for('host')
    assert after['phase'] == before['phase'] and after['round'] == before['round']
    assert [play.card.id for play in after['trick']] == [play.card.id for play in before['trick']]
    assert sorted(c.id for c in after['my_hand'] or []) == sorted(c.id for c in before['my_hand'] or [])
    assert [p['score'] for p in after['players']] == [p['score'] for p in before['players']]
    assert [m.name for m in restored.members] == [m.name for m in lobby.members]
    assert restored.listeners == {} and restored.connections == {} and restored.chat_listeners == {}
    assert [m.text for m in restored.chat] == ['brb, getting food']
    # nobody counts as absent right away, the players have time to reconnect
    assert not restored.is_absent('host')
    # As long as nobody is connected, the game waits – even long after the grace period.
    run_until(registry2, clock2, lambda: False, steps=200)
    assert restored.game.view_for('host')['phase'] == before['phase']
    # Whoever comes back can continue playing right away.
    restored.connect('host')
    view = restored.game.view_for('host')
    assert view['current'] == view['my_index']


def test_finished_game_is_recorded_once(tmp_path):
    registry, lobby, clock, store = started_registry(tmp_path)
    lobby.members[0].id = lobby.game.players[0].id = 'acct:erik'   # as a logged-in player
    lobby.host_id = 'acct:erik'
    lobby.anyone_online = lambda: True                 # for the test: bots move for everyone
    lobby._plays_automatically = lambda member_id: True
    assert run_until(registry, clock, lambda: lobby.game is not None and lobby.game.phase == Phase.GAME_OVER
                     or lobby.game is None)
    for _ in range(5):
        registry.tick_all()
    store.flush()
    games = store.finished_games()
    assert len(games) == 1
    assert games[0]['code'] == lobby.code
    assert {p['name'] for p in games[0]['players']} >= {'Erik'}
    assert games[0]['rounds'] == 15
    results = store.results_for('erik')
    assert len(results) == 1 and results[0]['rounds'] == 15 and 1 <= results[0]['place'] <= 4
    assert store.results_for('nobody') == []


def test_deleted_lobby_is_removed_from_store(tmp_path):
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    store = SqliteStore(tmp_path / 'db.sqlite')
    registry.attach_store(store)
    lobby = registry.create('host', 'Erik')
    lobby.disconnect('host')
    registry.tick_all()
    store.flush()
    assert lobby.code in store.load_lobbies()
    clock.now += 31 * 60   # nobody online, nothing happened for a long time
    registry.tick_all()
    store.flush()
    assert lobby.code not in registry.lobbies
    assert lobby.code not in store.load_lobbies()
