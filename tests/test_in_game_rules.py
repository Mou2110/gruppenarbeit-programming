"""The lobby's rules help stays available while the game table updates."""
import asyncio

from nicegui import app, ui
from nicegui.testing import user_simulation

from game.lobby import LobbyRegistry
from views import lobby, start


def test_rules_can_be_read_during_play_without_leaving_the_table(monkeypatch, tmp_path):
    registry = LobbyRegistry()
    game_lobby = registry.create('host', 'Marta')
    game_lobby.add_bot('host')
    game_lobby.add_bot('host')

    async def player_id():
        return 'host'

    async def signed_in_account():
        return None

    async def remembered_name():
        return 'Marta'

    async def javascript_result(*args, **kwargs):
        return False

    monkeypatch.setattr(app.storage, 'path', tmp_path / 'storage')
    monkeypatch.setattr(ui, 'run_javascript', javascript_result)
    for view in (lobby, start):
        monkeypatch.setattr(view, 'registry', registry)
        monkeypatch.setattr(view, 'player_id', player_id)
        monkeypatch.setattr(view, 'current_account', signed_in_account)
        monkeypatch.setattr(view, 'remembered_name', remembered_name)

    async def check():
        async with user_simulation() as user:
            ui.page('/')(start.start_page)
            ui.page('/lobby/{code}')(lobby.lobby_page)
            home = await user.open('/')
            home_rules = next(element.content for element in home.elements.values()
                              if isinstance(element, ui.html) and '<h3>Bidding</h3>' in element.content)
            await user.open(f'/lobby/{game_lobby.code}')
            await user.should_not_see(marker='open-game-rules', retries=1)
            user.find(marker='ready').click()

            await user.should_see(marker='open-game-rules')
            trigger = next(iter(user.find(marker='open-game-rules').elements))
            assert trigger.props['aria-label'] == 'Game rules'
            dialog = next(iter(user.find(kind=ui.dialog, marker='game-rules-dialog').elements))
            assert not dialog.value
            user.find(marker='open-game-rules').click()
            assert dialog.value
            with user.scope(marker='game-rules-dialog'):
                content = next(iter(user.find(kind=ui.html, content='<h3>Bidding</h3>').elements)).content
                assert content in home_rules
                assert '<h3>Trump</h3>' in content
                assert '<h3>Special cards (optional)</h3>' in content

            game = game_lobby.game
            assert game is not None
            phase = game.phase
            with user.client:
                game_lobby._changed()
            assert trigger.is_deleted
            assert dialog.value and not dialog.is_deleted

            user.find(marker='close-game-rules').click()
            assert not dialog.value
            assert game_lobby.game is game and game.phase == phase
            await user.should_see(marker='open-game-rules')
            await user.should_see(marker='scoreboard')

    asyncio.run(check())
