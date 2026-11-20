"""Shared components for all pages: player recognition, page frame, buttons, and icons."""
from __future__ import annotations

import html
import json
import secrets
from collections.abc import Callable
from contextlib import contextmanager

from nicegui import app, run, ui

from game import accounts
from game.lobby import registry

from .cards import svg

ICON_BACK = '<path d="M15 5l-7 7 7 7"/>'
ICON_SCORES = '<path d="M5 20V10M12 20V4M19 20v-7"/>'
ICON_INFO = '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>'
ICON_COPY = ('<rect x="8" y="8" width="12" height="12" rx="2"/>'
             '<path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>')
ICON_SHARE = '<path d="M12 15V3M7 8l5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>'
ICON_CHECK = '<path d="M5 12l5 5 9-10"/>'
ICON_PLUS = '<path d="M12 5v14M5 12h14"/>'
ICON_CLOSE = '<path d="M6 6l12 12M18 6L6 18"/>'
ICON_EXIT = ('<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3"/>'
             '<path d="M10 17l-5-5 5-5"/><path d="M5 12h11"/>')


def esc(text: object) -> str:
    """Safely insert text into HTML (e.g. player names entered by users)."""
    return html.escape(str(text))


async def player_id() -> str:
    """Who is using this tab? Signed in: the account ID (the same on every device).
    As a guest: a fixed ID for this browser tab, which persists after reloads.
    """
    account = await current_account()
    if account:
        return accounts.member_id(account[0])
    return await guest_id()


async def guest_id() -> str:
    """The guest ID for this browser tab."""
    await ui.context.client.connected()
    storage = app.storage.tab
    if 'player_id' not in storage:
        # The ID is also stored in the browser tab (sessionStorage). This lets the game recognize you
        # after a server restart and restore your seat.
        try:
            pid = await ui.run_javascript("sessionStorage.getItem('prophecy_pid') || ''", timeout=2)
        except Exception:
            pid = ''
        pid = str(pid or '')
        if not (len(pid) == 16 and all(c in '0123456789abcdef' for c in pid)):
            pid = secrets.token_hex(8)
        storage['player_id'] = pid
    ui.run_javascript(f"sessionStorage.setItem('prophecy_pid', '{storage['player_id']}')")
    return storage['player_id']


# ---------------------------------------------------------------- Accounts

def _store():
    return registry.store


async def current_account() -> tuple[str, str] | None:
    """(key, username) if someone is signed in on this browser, otherwise None."""
    await ui.context.client.connected()
    storage = app.storage.tab
    if 'account' not in storage:
        account = None
        store = _store()
        if store is not None:
            try:
                token = await ui.run_javascript("localStorage.getItem('prophecy_token') || ''", timeout=2)
                if token:
                    account = await run.io_bound(store.session_account, str(token))
            except Exception:
                account = None
        storage['account'] = list(account) if account else None
    account = storage['account']
    return (account[0], account[1]) if account else None


async def sign_in(username: str, password: str, *, register: bool) -> tuple[str, str]:
    """Register or sign in. Any seat already held as a guest is transferred to the account."""
    store = _store()
    if store is None:
        raise accounts.AccountError('Accounts are not available right now.')
    action = store.register if register else store.login
    key, name = await run.io_bound(action, username, password)
    token = await run.io_bound(store.new_session, key)
    ui.run_javascript(f"localStorage.setItem('prophecy_token', {json.dumps(token)})")
    guest = await guest_id()
    for lobby in registry.lobbies_of(guest):
        lobby.rebind(guest, accounts.member_id(key), name)
    app.storage.tab['account'] = [key, name]
    save_name(name)
    return key, name


async def sign_out() -> None:
    store = _store()
    try:
        token = await ui.run_javascript("localStorage.getItem('prophecy_token') || ''", timeout=2)
        if token and store is not None:
            await run.io_bound(store.end_session, str(token))
    except Exception:
        pass
    ui.run_javascript("localStorage.removeItem('prophecy_token')")
    app.storage.tab['account'] = None


def saved_name() -> str:
    return app.storage.tab.get('name', '')


async def remembered_name() -> str:
    """The most recently used name: first from this tab, otherwise from the browser (localStorage)."""
    if saved_name():
        return saved_name()
    try:
        name = await ui.run_javascript("localStorage.getItem('prophecy_name') || ''", timeout=2)
    except Exception:  # e.g. no JavaScript result in tests
        name = ''
    name = str(name or '')[:16]
    if name:
        app.storage.tab['name'] = name
    return name


def save_name(name: str) -> None:
    """Save the name in the tab and persist it in the browser, so it only needs to be entered once."""
    app.storage.tab['name'] = name
    ui.run_javascript(f"localStorage.setItem('prophecy_name', {json.dumps(name)})")


@contextmanager
def page_frame():
    """The dark blue background with a mobile-width column in the center."""
    with ui.element('div').classes('pg'), ui.element('div').classes('tbl') as column:
        yield column


def button(text: str, on_click: Callable | None = None, *, cls: str = 'primary', icon: str | None = None,
           disabled: bool = False, marker: str | None = None, label: str | None = None) -> ui.element:
    """A button in the game design (a real <button> element)."""
    props = 'type=button'
    if disabled:
        props += ' disabled'
    if label:
        props += f' aria-label="{esc(label)}"'
    element = ui.element('button').classes(cls).props(props)
    with element:
        inner = (svg(icon, 'i') if icon else '') + (f'<span>{esc(text)}</span>' if text else '')
        ui.html(inner, sanitize=False).classes('btnc')
    if on_click is not None and not disabled:
        element.on('click', on_click)
    if marker:
        element.mark(marker)
    return element


def icon_button(icon: str, label: str, on_click: Callable, marker: str | None = None) -> ui.element:
    return button('', on_click, cls='iconbtn', icon=icon, label=label, marker=marker)


def message_page(title: str, text: str) -> None:
    """A simple information page, e.g. when a lobby does not exist."""
    with page_frame():
        with ui.element('div').classes('panel mt'):
            ui.html(f'<h2>{esc(title)}</h2><p>{esc(text)}</p>', sanitize=False)
            button('Back to start', lambda: ui.navigate.to('/'), marker='home')
