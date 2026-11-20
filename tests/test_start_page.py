"""The illustrated landing page keeps the existing game actions available."""
import asyncio
from unittest.mock import AsyncMock

from nicegui import app, ui
from nicegui.testing import user_simulation
from nicegui.testing.general import prepare_simulation

from game.lobby import LobbyRegistry
from views import start


def test_start_page_keeps_the_game_actions_beside_decorative_artwork(monkeypatch, tmp_path):
    monkeypatch.setattr(app.storage, 'path', tmp_path / 'storage')
    monkeypatch.setattr(start, 'registry', LobbyRegistry())
    monkeypatch.setattr(start, 'player_id', AsyncMock(return_value='guest'))
    monkeypatch.setattr(start, 'current_account', AsyncMock(return_value=None))
    monkeypatch.setattr(start, 'remembered_name', AsyncMock(return_value='Guest'))

    async def check():
        async with user_simulation() as user:
            prepare_simulation()
            ui.page('/')(start.start_page)
            await user.open('/')

            await user.should_see('Prophecy')
            for marker in ('create', 'join', 'practice'):
                await user.should_see(marker=marker)

            portrait, = user.find(kind=ui.html, content='/static/prophet/lowered.jpg').elements
            assert portrait.props['aria-hidden'] == 'true'
            assert 'alt=""' in portrait.content
            cards, = user.find(kind=ui.html, content='aria-label="Sea 13"').elements
            for label in ('Sea 13', 'Wizard', 'Sardine 7'):
                assert f'aria-label="{label}"' in cards.content

            user.find(marker='join').click()
            await user.should_see(marker='join-confirm')

    asyncio.run(check())
