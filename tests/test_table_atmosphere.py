"""The decorative table stays mounted while the game view updates."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from nicegui import app, ui
from nicegui.testing import user_simulation
from nicegui.testing.general import prepare_simulation

from game.cards import build_deck
from game.lobby import LobbyRegistry
from views import lobby


@pytest.mark.parametrize('players', [3, 4, 5, 6])
def test_table_atmosphere_only_appears_in_game_and_survives_redraws(monkeypatch, tmp_path, players):
    registry = LobbyRegistry()
    game_lobby = registry.create('host', 'Marta')
    for _ in range(players - 1):
        game_lobby.add_bot('host')
    game_lobby.update_settings('host', clairvoyance=False)
    monkeypatch.setattr(app.storage, 'path', tmp_path / 'storage')
    monkeypatch.setattr(lobby, 'registry', registry)
    monkeypatch.setattr(lobby, 'player_id', AsyncMock(return_value='host'))
    monkeypatch.setattr(lobby, 'current_account', AsyncMock(return_value=None))
    monkeypatch.setattr(lobby, 'remembered_name', AsyncMock(return_value='Marta'))
    monkeypatch.setattr(ui, 'run_javascript', AsyncMock(return_value=False))

    async def check():
        async with user_simulation() as user:
            prepare_simulation()
            ui.page('/lobby/{code}')(lobby.lobby_page)
            client = await user.open(f'/lobby/{game_lobby.code}')

            await user.should_not_see(marker='table-atmosphere', retries=1)
            user.find(marker='ready').click()
            await user.should_see(marker='table-atmosphere')
            current, = user.find(marker='table-atmosphere').elements
            assert current.props['aria-hidden'] == 'true'
            seats = [element for element in client.elements.values() if 'table-seat' in element.classes]
            assert len(seats) == players - 1
            assert len({(seat.style['--seat-x'], seat.style['--seat-y']) for seat in seats}) == players - 1

            game_lobby.game.players[0].hand = build_deck()[:20]
            with client:
                game_lobby._changed()
            await asyncio.sleep(0)
            refreshed, = user.find(marker='table-atmosphere').elements
            assert refreshed is current
            cards = [element for element in client.elements.values() if 'hcard' in element.classes]
            assert len(cards) == 20
            assert cards[0].style['--fan-angle'].startswith('-')
            assert not cards[-1].style['--fan-angle'].startswith('-')
            await user.should_see(marker='open-game-rules')

    asyncio.run(check())
