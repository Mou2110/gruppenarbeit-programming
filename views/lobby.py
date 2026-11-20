"""The /lobby/CODE page: first the waiting room, then the game table after the game starts.

Each browser tab subscribes to the lobby. When something changes - someone joins,
clicks "Ready", or plays a card - all tabs are redrawn.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from functools import partial

from nicegui import ui

from game.cards import Kind
from game.lobby import MAX_PLAYERS, MIN_PLAYERS, LobbyError, clean_name, registry

from .common import (
    ICON_BACK, ICON_CHECK, ICON_CLOSE, ICON_COPY, ICON_PLUS, ICON_SHARE, button, esc, icon_button, message_page,
    current_account, page_frame, player_id, remembered_name, save_name,
)
from .cards import svg
from .rules import game_rules_dialog
from .table import render_table

SPECIAL_OPTIONS = [
    ('Shapeshifter', (Kind.SHAPESHIFTER,)),
    ('Dragon & Fairy', (Kind.DRAGON, Kind.FAIRY)),   # always paired according to the rules
    ('Bomb', (Kind.BOMB,)),
    ('Werewolf', (Kind.WEREWOLF,)),
    ('Juggler', (Kind.JUGGLER,)),
    ('Cloud', (Kind.CLOUD,)),
]


ICON_SEND = '<path d="M4 12l16-8-6 16-3-7z"/><path d="M11 13l9-9"/>'

# Creates a translucent message at the bottom right that stays visible for a few seconds.
# (Sent in full with every message so it does not depend on a previously loaded script.)
BUBBLE_JS = """(() => {
  const box = document.getElementById('chatfloat');
  if (!box) return;
  const bubble = document.createElement('div');
  bubble.className = 'bubble' + (%(mine)s ? ' mine' : '');
  const who = document.createElement('b');
  who.textContent = %(mine)s ? 'You' : %(name)s;
  const what = document.createElement('span');
  what.textContent = %(text)s;
  bubble.append(who, what);
  box.appendChild(bubble);
  while (box.children.length > 3) box.firstChild.remove();
  setTimeout(() => bubble.remove(), 8000);
})();"""


async def lobby_page(code: str) -> None:
    pid = await player_id()
    account = await current_account()
    name = account[1] if account else await remembered_name()
    client = ui.context.client
    lobby = registry.get(code)
    if lobby is None:
        message_page('Lobby not found', f'There is no lobby with the code {code.upper()}. '
                                        'Check the code or create a new lobby.')
        return
    member = lobby.member(pid)
    if member is not None and member.is_bot and lobby.game is not None:
        message_page('You left this game', 'A bot is playing your seat until the game ends.')
        return
    if member is None:
        try:
            lobby.join(pid, name)
        except LobbyError as error:
            message_page("Can't join this lobby", str(error))
            return
    lobby.connect(pid)
    state: dict = {'mode': None}
    # Touch device (phone/tablet)? A card is selected first and played with the second tap.
    try:
        state['touch'] = bool(await ui.run_javascript("matchMedia('(pointer: coarse)').matches", timeout=2))
    except Exception:
        state['touch'] = False

    def mode() -> str:
        return 'game' if lobby.game is not None else 'lobby'

    # ------------------------------------------------------------ Aktionen
    def run(action, *args, **kwargs) -> None:
        try:
            action(*args, **kwargs)
        except LobbyError as error:
            ui.notify(str(error), type='warning')

    def leave_lobby() -> None:
        lobby.leave(pid)
        lobby.unsubscribe(client.id)
        ui.navigate.to('/')

    def rename(value: str) -> None:
        name = clean_name(value or '')
        if name:
            save_name(name)
            lobby.rename(pid, name)

    def toggle_special(kinds: tuple[Kind, ...]) -> None:
        current = set(lobby.settings.special_cards)
        if all(k in current for k in kinds):
            current -= set(kinds)
        else:
            current |= set(kinds)
        run(lobby.update_settings, pid, special_cards=list(current))

    def copy_code() -> None:
        ui.clipboard.write(lobby.code)
        ui.notify(f'Code {lobby.code} copied', type='positive')

    def share_link() -> None:
        ui.run_javascript(
            "const url = window.location.href;"
            "if (navigator.share) { navigator.share({title: 'Prophecy', text: 'Join my game!', url: url}); }"
            "else { navigator.clipboard.writeText(url); }")
        ui.notify('Link ready to share', type='positive')

    # ------------------------------------------------------------ Warteraum
    @ui.refreshable
    def players_part() -> None:
        is_host = lobby.is_host(pid)
        with ui.element('div').classes('section'):
            ui.html(f'<div class="sechead"><span>Players</span><span class="muted">{len(lobby.members)} of '
                    f'{MAX_PLAYERS}</span></div>', sanitize=False)
            for member in lobby.members:
                tags = []
                if member.id == pid:
                    tags.append('you')
                if lobby.is_host(member.id):
                    tags.append('host')
                if not member.is_bot and not lobby.is_online(member.id):
                    tags.append('offline')
                tag_html = f' <span class="muted">({", ".join(tags)})</span>' if tags else ''
                if member.is_bot:
                    pill = '<span class="pill bot">Bot</span>'
                elif member.ready:
                    pill = '<span class="pill ready">Ready</span>'
                else:
                    pill = '<span class="pill">Not ready</span>'
                with ui.element('div').classes('prow' + (' mine' if member.id == pid else '')):
                    ui.html(f'<div class="avatar av-sm">{esc(member.name[:1].upper())}</div>'
                            f'<span class="pn">{esc(member.name)}{tag_html}</span>{pill}', sanitize=False
                            ).classes('prow-main')
                    if is_host and member.is_bot:
                        icon_button(ICON_CLOSE, f'Remove {member.name}', partial(run, lobby.remove_bot, pid, member.id),
                                    marker='remove-bot').classes('mini')
            if is_host and len(lobby.members) < MAX_PLAYERS:
                button('Add a bot', partial(run, lobby.add_bot, pid), cls='primary ghostbtn small', icon=ICON_PLUS,
                       marker='add-bot')

    @ui.refreshable
    def settings_part() -> None:
        settings = lobby.settings
        is_host = lobby.is_host(pid)
        specials = set(settings.special_cards)
        with ui.element('div').classes('section'):
            hint = '' if is_host else '<span class="muted">set by the host</span>'
            ui.html(f'<div class="sechead"><span>Game settings</span>{hint}</div>'
                    '<p class="muted small">Special cards</p>', sanitize=False)
            with ui.element('div').classes('chips'):
                for label, kinds in SPECIAL_OPTIONS:
                    on = all(k in specials for k in kinds)
                    button(label, partial(toggle_special, kinds), cls='chipbtn' + (' on' if on else ''),
                           icon=ICON_CHECK if on else None, disabled=not is_host, marker='setting')
            ui.html('<p class="muted small">Rules</p>', sanitize=False)
            with ui.element('div').classes('chips'):
                on = settings.no_matching_bids
                button("Bids can't add up", partial(run, lobby.update_settings, pid, no_matching_bids=not on),
                       cls='chipbtn' + (' on' if on else ''), icon=ICON_CHECK if on else None,
                       disabled=not is_host, marker='setting')
                on = settings.clairvoyance
                button('Clairvoyance in round 1', partial(run, lobby.update_settings, pid, clairvoyance=not on),
                       cls='chipbtn' + (' on' if on else ''), icon=ICON_CHECK if on else None,
                       disabled=not is_host, marker='setting')

    @ui.refreshable
    def ready_part() -> None:
        me = lobby.member(pid)
        humans = lobby.humans()
        ready = sum(1 for m in humans if m.ready)
        missing = lobby.missing_for_start() or 'Starting…'
        ui.html(f'<div class="readyinfo"><b>{ready} of {len(humans)} player{"s" if len(humans) != 1 else ""} '
                f'ready</b><span>{esc(missing)}</span><span>The game starts automatically once everyone is ready '
                f'and at least {MIN_PLAYERS} players are in.</span></div>', sanitize=False)
        if me is not None:
            button("I'm ready" if not me.ready else 'Not ready after all', partial(run, lobby.set_ready, pid, not me.ready),
                   cls='primary big' if not me.ready else 'primary ghostbtn big', marker='ready')

    def waiting_room() -> None:
        me = lobby.member(pid)
        with ui.element('div').classes('topbar'):
            icon_button(ICON_BACK, 'Leave lobby', leave_lobby, marker='leave-lobby')
            ui.html('<div class="rinfo"><b>Lobby</b></div>', sanitize=False)
            ui.element('div').classes('iconspace')
        with ui.element('div').classes('panel codecard'):
            ui.html(f'<span class="eyebrow">Lobby code</span><span class="code">{lobby.code}</span>', sanitize=False)
            with ui.element('div').classes('twobtn'):
                button('Copy code', copy_code, cls='primary small', icon=ICON_COPY)
                button('Share link', share_link, cls='primary ghostbtn small', icon=ICON_SHARE)
        with ui.element('div').classes('section'):
            ui.html('<label class="flabel" for="name-input">Your name</label>', sanitize=False)
            field = ui.input(value=me.name if me else '', on_change=lambda e: rename(e.value)) \
                .props('id=name-input dark outlined dense maxlength=16').classes('namefield').mark('name')
            if account:  # signed in: the account username is shown
                field.props('readonly hint="Signed in"')
        players_part()
        settings_part()
        ready_part()

    # ------------------------------------------------------------ Umschalten Warteraum / Spiel
    @ui.refreshable
    def table_part(open_rules: Callable[[], None]) -> None:
        render_table(lobby, pid, state, table_part.refresh, open_rules)

    @ui.refreshable
    def content() -> None:
        state['mode'] = mode()
        with page_frame():
            if state['mode'] == 'game':
                # Keep the open dialog outside the table refreshed by moves and bot turns.
                rules = game_rules_dialog()
                table_part(rules.open)
            else:
                waiting_room()

    def on_change() -> None:
        if mode() != state['mode']:
            content.refresh()
        elif state['mode'] == 'game':
            table_part.refresh()
        else:
            players_part.refresh()
            settings_part.refresh()
            ready_part.refresh()

    content()

    # ------------------------------------------------------------ Chat
    # A fixed input field at the bottom (like WhatsApp). New messages briefly float up at the bottom right.
    # When the input field is active, the history appears above it. The chat is outside the table,
    # so redrawing the table never clears the text being typed.
    ui.query('body').classes('haschat')

    @ui.refreshable
    def chat_log() -> None:
        if not lobby.chat:
            ui.html('<div class="cempty">No messages yet. Say hi!</div>', sanitize=False)
            return
        rows = []
        for message in lobby.chat:
            mine = ' mine' if message.member_id == pid else ''
            rows.append(f'<div class="cmsg{mine}"><b>{esc(message.name)}</b><span>{esc(message.text)}</span></div>')
        ui.html(''.join(rows), sanitize=False).classes('cmsgs')

    def scroll_log() -> None:
        client.run_javascript("const l = document.querySelector('.chatlog'); if (l) l.scrollTop = l.scrollHeight;")

    def send_message() -> None:
        text = chat_input.value or ''
        try:
            lobby.say(pid, text)
        except LobbyError as error:
            ui.notify(str(error), type='warning')
            return
        chat_input.value = ''
        # Close the keyboard (blur the field), leaving only the input row visible at the bottom
        ui.run_javascript('document.activeElement && document.activeElement.blur()')

    def on_chat(message) -> None:
        chat_log.refresh()
        scroll_log()
        mine = 'true' if message.member_id == pid else 'false'
        client.run_javascript(BUBBLE_JS % {'mine': mine, 'name': json.dumps(message.name),
                                           'text': json.dumps(message.text)})

    with ui.element('div').classes('chatbar'):
        with ui.element('div').classes('chatlog').props('tabindex=-1'):
            chat_log()
        with ui.element('div').classes('chatrow'):
            chat_input = ui.input(placeholder='Message…') \
                .props('dense borderless dark maxlength=200 enterkeyhint=send autocomplete=off') \
                .classes('chatinput').mark('chat-input')
            chat_input.on('keydown.enter', send_message)
            chat_input.on('focus', js_handler="() => setTimeout(() => { const l = document.querySelector('.chatlog');"
                                               " if (l) l.scrollTop = l.scrollHeight; }, 30)")
            send = ui.element('button').classes('chatsend').props('type=button aria-label="Send message"')
            with send:
                ui.html(svg(ICON_SEND, 'i'), sanitize=False).classes('btnc')
            send.on('click', send_message)
            send.mark('chat-send')
    ui.element('div').classes('chatfloat').props('id=chatfloat')
    lobby.chat_listeners[client.id] = on_chat

    def connection_lost() -> None:
        lobby.disconnect(pid)
        lobby.unsubscribe(client.id)
        lobby.chat_listeners.pop(client.id, None)

    def connection_back() -> None:
        lobby.connect(pid)
        lobby.subscribe(client.id, on_change)
        lobby.chat_listeners[client.id] = on_chat
        on_change()
        chat_log.refresh()

    lobby.subscribe(client.id, on_change)
    client.on_disconnect(connection_lost)
    client.on_connect(connection_back)
