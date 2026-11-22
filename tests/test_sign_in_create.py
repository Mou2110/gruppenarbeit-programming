"""Signing in with a username that does not work offers to create an account with the same details."""
import asyncio

from nicegui import app, ui
from nicegui.testing import user_simulation
from nicegui.testing.general import prepare_simulation

from game.accounts import AccountError
from views import start


def test_failed_sign_in_offers_to_create_the_account(monkeypatch, tmp_path):
    monkeypatch.setattr(app.storage, 'path', tmp_path / 'storage')
    calls = []

    async def sign_in(username, password, register=False):
        calls.append((username, password, register))
        if not register:
            raise AccountError('Wrong username or password.')

    monkeypatch.setattr(start, 'sign_in', sign_in)

    async def check():
        async with user_simulation() as user:
            prepare_simulation()

            @ui.page('/')
            def page():
                start.auth_dialog(False).open()

            await user.open('/')
            await user.should_not_see(marker='auth-create-instead')     # only after a failed sign-in
            user.find(marker='username').type('Lena')
            user.find(marker='password').type('secret123')
            user.find(marker='auth-submit').click()
            await user.should_see('Wrong username or password.')       # the message itself stays the same
            user.find(marker='auth-create-instead').click()
            await asyncio.sleep(0.1)
    asyncio.run(check())
    assert calls == [('Lena', 'secret123', False), ('Lena', 'secret123', True)]


def test_pressing_sign_in_never_creates_an_account(monkeypatch, tmp_path):
    # The click event must not be mistaken for "create": signing in only signs in.
    monkeypatch.setattr(app.storage, 'path', tmp_path / 'storage')
    calls = []

    async def sign_in(username, password, register=False):
        calls.append(register)

    monkeypatch.setattr(start, 'sign_in', sign_in)

    async def check():
        async with user_simulation() as user:
            prepare_simulation()

            @ui.page('/')
            def page():
                start.auth_dialog(False).open()

            await user.open('/')
            user.find(marker='username').type('Lena')
            user.find(marker='password').type('secret123')
            user.find(marker='auth-submit').click()
            await asyncio.sleep(0.1)
    asyncio.run(check())
    assert calls == [False]
