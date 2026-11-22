"""Inviting friends into a lobby: the popup for the invited friend and the "Invite friends" list in the lobby."""
from __future__ import annotations

from nicegui import ui

from game.accounts import member_id
from game.lobby import MAX_PLAYERS, Lobby, LobbyRegistry, registry
from game.presence import Invite, Presence, presence

from .common import button, current_account, esc


def invitable(friends: list[dict], lobby: Lobby, online: Presence = presence,
              lobbies: LobbyRegistry = registry) -> list[dict]:
    """Friends shown in the "Invite friends" list: online, not yet in the lobby, and our own game has not
    started. Friends in the middle of another game get 'in_game': True and no invite button,
    because with "Join" they would leave that game."""
    if lobby.game is not None or len(lobby.members) >= MAX_PLAYERS:
        return []

    def in_game(account: str) -> bool:
        return any(other.game is not None for other in lobbies.lobbies_of(member_id(account)))

    return [{**f, 'in_game': in_game(f['account'])} for f in friends
            if online.is_online(f['account']) and lobby.member(member_id(f['account'])) is None]


def invite_html(sender_name: str, code: str) -> str:
    return (f'<h2>Game invite</h2><p><b>{esc(sender_name)}</b> invites you to play in lobby '
            f'<b>{esc(code)}</b>.</p>')


async def watch_invites() -> None:
    """Called on every page: signed-in players count as online and see invitations as a popup."""
    account = await current_account()
    if account is None:
        return
    client = ui.context.client

    def show(invite: Invite) -> None:
        with client:
            with ui.dialog() as dialog, ui.element('div').classes('panel dialogpanel'):
                ui.html(invite_html(invite.sender_name, invite.code), sanitize=False)

                def join() -> None:
                    dialog.close()
                    ui.navigate.to(f'/lobby/{invite.code}')

                button('Join', join, cls='primary big', marker='invite-join')
                button('Not now', dialog.close, cls='primary ghostbtn', marker='invite-decline')
            dialog.open()

    presence.connect(client.id, account[0], show)
    client.on_disconnect(lambda: presence.disconnect(client.id))
    client.on_connect(lambda: presence.connect(client.id, account[0], show))
