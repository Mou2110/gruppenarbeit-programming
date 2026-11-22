"""Friends are easier to reach: their own page (/friends), a button on the start page and on player profiles."""
import asyncio
from unittest.mock import AsyncMock

from nicegui import app, ui
from nicegui.testing import user_simulation
from nicegui.testing.general import prepare_simulation

from game.lobby import LobbyRegistry
from game.persistence import SqliteStore
from views import leaderboard, start, stats


def signed_in(monkeypatch, tmp_path, module_names=('stats',)):
    store = SqliteStore(tmp_path / 'db.sqlite')
    for name in ('Erik', 'Marta'):
        store.register(name, 'secret123')
    monkeypatch.setattr(app.storage, 'path', tmp_path / 'storage')
    monkeypatch.setattr(stats.registry, 'store', store)
    for module in (stats, start, leaderboard):
        monkeypatch.setattr(module, 'current_account', AsyncMock(return_value=('erik', 'Erik')))
    return store


def test_friends_page_lets_you_add_a_friend(monkeypatch, tmp_path):
    store = signed_in(monkeypatch, tmp_path)

    async def check():
        async with user_simulation() as user:
            prepare_simulation()
            ui.page('/friends')(stats.friends_page)
            await user.open('/friends')
            await user.should_see('No friends yet')
            user.find(marker='friend-name').type('Marta')
            user.find(marker='add-friend').click()
            await user.should_see('Marta is now your friend.')
    asyncio.run(check())
    assert [f['name'] for f in store.friends_of('erik')] == ['Marta']


def test_friends_page_asks_guests_to_sign_in(monkeypatch, tmp_path):
    signed_in(monkeypatch, tmp_path)
    monkeypatch.setattr(stats, 'current_account', AsyncMock(return_value=None))

    async def check():
        async with user_simulation() as user:
            prepare_simulation()
            ui.page('/friends')(stats.friends_page)
            await user.open('/friends')
            await user.should_see('Sign in to add friends')
    asyncio.run(check())


def test_start_page_has_a_friends_button(monkeypatch, tmp_path):
    signed_in(monkeypatch, tmp_path)
    monkeypatch.setattr(start, 'registry', LobbyRegistry())
    start.registry.store = stats.registry.store
    monkeypatch.setattr(start, 'player_id', AsyncMock(return_value='acct:erik'))
    monkeypatch.setattr(start, 'remembered_name', AsyncMock(return_value='Erik'))

    async def check():
        async with user_simulation() as user:
            prepare_simulation()
            ui.page('/')(start.start_page)
            await user.open('/')
            await user.should_see(marker='friends')
    asyncio.run(check())
