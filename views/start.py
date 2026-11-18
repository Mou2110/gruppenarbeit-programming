"""The start page: a brief introduction, options to create or join a lobby, and the rules below."""
from __future__ import annotations

from functools import partial

from nicegui import ui

from game.accounts import AccountError
from game.cards import Card, Kind, Suit
from game.lobby import MAX_PLAYERS, registry

from .cards import card_html
from .common import (
    ICON_CLOSE, button, current_account, esc, icon_button, page_frame, player_id, remembered_name, sign_in, sign_out,
)

HERO = (card_html(Card('sea-13', Kind.NUMBER, Suit.SEA, 13), 'md'),
        card_html(Card('wizard-1', Kind.WIZARD), 'md'),
        card_html(Card('sardine-7', Kind.NUMBER, Suit.SARDINE, 7), 'md'))

HOW_IT_WORKS = [
    ('Bid', 'Look at your cards and say how many tricks you will win.'),
    ('Play', 'Everyone plays one card per trick. The highest card wins it.'),
    ('Score', 'Hit your bid exactly to earn points. Miss it and you lose some.'),
]

SUIT_CHIPS = ''.join(f'<span class="mini s-{s}">{name}</span>' for s, name in
                     [('sea', 'Sea'), ('sardine', 'Sardine'), ('olive', 'Olive'), ('sun', 'Sun')])

RULES = [
    ('The cards', 'Four suits numbered 1 to 13, plus 4 Wizards and 4 Jesters. Wizards beat everything, '
                  'Jesters lose everything. Neither has a suit.<div class="minis">' + SUIT_CHIPS +
                  '<span class="mini k-wizard">Wizard</span><span class="mini k-jester">Jester</span></div>'),
    ('Rounds', 'Round 1 deals one card each, round 2 two cards, and so on: 20 rounds with 3 players, '
               '15 with 4, 12 with 5 and 10 with 6.'),
    ('Trump', 'After dealing, the next card is turned up and its suit is trump. A Jester means no trump, '
              'a Wizard lets the dealer choose. Without special cards the last round has no trump.'),
    ('Bidding', 'Starting left of the dealer, everyone says how many tricks they will win. '
                "The bids must not add up to the number of tricks, so the last player has one option less."),
    ('Playing a trick', 'Follow the suit of the first card if you can. Wizards, Jesters and special cards may '
                        'always be played. The trick goes to the first Wizard, otherwise the highest trump, '
                        'otherwise the highest card of the lead suit. The winner leads the next trick.'),
    ('Scoring', 'Bid hit exactly: 20 points plus 10 per trick. Bid missed: minus 10 for every trick you are off. '
                'Most points after the last round wins.'),
    ('Round 1 · Clairvoyance', "In round 1 you can't see your own card, only everyone else's. "
                               'The Werewolf sits out round 1. If your hidden card turns out to be a Shapeshifter, '
                               'Juggler or Cloud, you make your choice once it is revealed.'),
]

SPECIALS = [
    ('k-shift', 'Shapeshifter', 'Play it as a Wizard or as a Jester, your choice.'),
    ('k-dragon', 'Dragon', 'Beats every card, even Wizards. Only the Fairy beats it.'),
    ('k-fairy', 'Fairy', 'The lowest card, but it wins any trick that holds the Dragon.'),
    ('k-bomb', 'Bomb', 'Nobody gets the trick it lands in. Whoever would have won leads next.'),
    ('k-multi', 'Juggler 7½', 'Counts in a suit you pick. After its trick, everyone passes one card to the left.'),
    ('k-multi', 'Cloud 9¾', 'Counts in a suit you pick. Whoever wins its trick must change their bid by one right away.'),
    ('k-wolf', 'Werewolf', 'Swap it for the trump card before bidding and choose the trump yourself.'),
]


def _lobby_status(lobby) -> tuple[str, str]:
    names = ', '.join(m.name for m in lobby.members)
    if lobby.game is None:
        return 'Waiting room', names
    game = lobby.game
    if game.phase.value == 'game_over':
        return 'Game finished', names
    return f'Round {game.round_number} of {game.num_rounds}', names


def auth_dialog(register: bool) -> ui.dialog:
    """Dialog for signing in or creating an account."""
    async def submit() -> None:
        error.set_content('')
        try:
            await sign_in(user_input.value or '', password_input.value or '', register=register)
        except AccountError as problem:
            error.set_content(esc(problem))
            return
        except Exception:
            error.set_content('Something went wrong. Please try again.')
            return
        ui.navigate.to('/')

    with ui.dialog() as dialog, ui.element('div').classes('panel dialogpanel authpanel'):
        if register:
            ui.html('<h2>Create an account</h2><p>Pick a username and a password. Your stats and games '
                    'are then saved to your account, on every device.</p>', sanitize=False)
        else:
            ui.html('<h2>Sign in</h2><p>Welcome back. Sign in to see your stats and your games.</p>',
                    sanitize=False)
        user_input = ui.input(placeholder='Username').classes('namefield') \
            .props('outlined dense maxlength=16 autocomplete=username').mark('username')
        password_input = ui.input(placeholder='Password', password=True).classes('namefield') \
            .props(f'outlined dense autocomplete={"new-password" if register else "current-password"}') \
            .mark('password')
        password_input.on('keydown.enter', submit)
        error = ui.html('', sanitize=False).classes('autherr')
        button('Create account' if register else 'Sign in', submit, marker='auth-submit')
        button('Cancel', dialog.close, cls='primary ghostbtn')
    return dialog


async def start_page() -> None:
    pid = await player_id()
    account = await current_account()
    name = account[1] if account else await remembered_name()

    async def do_sign_out() -> None:
        await sign_out()
        ui.navigate.to('/')

    def create_lobby() -> None:
        lobby = registry.create(pid, name)
        ui.navigate.to(f'/lobby/{lobby.code}')

    def practice() -> None:
        lobby = registry.create(pid, name)
        for _ in range(3):
            lobby.add_bot(pid)
        lobby.set_ready(pid, True)  # starts the game immediately
        ui.navigate.to(f'/lobby/{lobby.code}')

    def join() -> None:
        code = (code_input.value or '').strip().upper()
        lobby = registry.get(code)
        if lobby is None:
            ui.notify(f'There is no lobby with the code {code or "…"}', type='warning')
            return
        if lobby.member(pid) is None and lobby.game is not None:
            ui.notify('That game has already started', type='warning')
            return
        if lobby.member(pid) is None and len(lobby.members) >= MAX_PLAYERS:
            ui.notify('That lobby is full', type='warning')
            return
        ui.navigate.to(f'/lobby/{lobby.code}')

    with ui.dialog() as dialog, ui.element('div').classes('panel dialogpanel'):
        ui.html('<h2>Join a lobby</h2><p>Enter the 4-character code from the host.</p>', sanitize=False)
        code_input = ui.input(placeholder='K7QX').props('outlined autofocus maxlength=4').classes('codefield') \
            .mark('code')
        code_input.on('keydown.enter', join)
        button('Join', join, marker='join-confirm')
        button('Cancel', dialog.close, cls='primary ghostbtn')

    with page_frame():
        with ui.element('div').classes('hero'):
            ui.html(f'<div class="herocards">{"".join(HERO)}</div><h1>Prophecy</h1>'
                    '<p class="tagline">Predict exactly how many tricks you will win. '
                    'Every round you get one card more.</p>'
                    '<span class="meta">3–6 players · about 45 minutes</span>', sanitize=False)
        with ui.element('div').classes('stack'):
            button('Create lobby', create_lobby, cls='primary big', marker='create')
            button('Join lobby', dialog.open, cls='primary ghostbtn big', marker='join')
            button('Practice against bots', practice, cls='linkbtn', marker='practice')

        # Your games: return to any lobby you are in without a link or code.
        mine = registry.games_of(pid)
        leaving: dict = {}

        def ask_leave(lobby) -> None:
            leaving['lobby'] = lobby
            leave_text.set_content(f'<h2>Remove game {esc(lobby.code)}?</h2><p>You leave this game for good. '
                                   'If others are still playing, a bot takes over your seat.</p>')
            leave_dialog.open()

        def confirm_leave() -> None:
            lobby = leaving.pop('lobby', None)
            if lobby is not None:
                lobby.leave(pid)
            leave_dialog.close()
            ui.navigate.to('/')

        with ui.dialog() as leave_dialog, ui.element('div').classes('panel dialogpanel'):
            leave_text = ui.html('', sanitize=False)
            button('Remove game', confirm_leave, marker='remove-confirm')
            button('Cancel', leave_dialog.close, cls='primary ghostbtn')

        if mine:
            with ui.element('div').classes('section plain'):
                ui.html('<h2 class="h2">Your games</h2>', sanitize=False)
                with ui.element('div').classes('games'):
                    for lobby in mine:
                        status, names = _lobby_status(lobby)
                        with ui.element('div').classes('grow'):
                            ui.html(f'<span class="gcode">{esc(lobby.code)}</span>'
                                    f'<div class="ginfo">{esc(status)}<span>{esc(names)}</span></div>',
                                    sanitize=False).classes('ginfo-wrap').style('display:contents')
                            button('Rejoin', partial(ui.navigate.to, f'/lobby/{lobby.code}'), cls='primary small',
                                   marker='rejoin')
                            icon_button(ICON_CLOSE, f'Remove game {lobby.code}', partial(ask_leave, lobby),
                                        marker='remove')

        # Account: optional. Play as a guest without an account.
        if registry.store is not None:
            with ui.element('div').classes('acct'):
                if account:
                    ui.html(f'<p>Signed in as <b>{esc(account[1])}</b>. Your games count towards your stats, '
                            'and you can get back into them from any device.</p>', sanitize=False)
                    with ui.element('div').classes('acctrow'):
                        button('My stats', lambda: ui.navigate.to('/stats'), cls='primary small', marker='stats')
                        button('Sign out', do_sign_out, cls='primary small ghostbtn', marker='signout')
                else:
                    ui.html('<p>Playing as a guest. With an account your stats are saved and you can get back '
                            'into your games from any device.</p>', sanitize=False)
                    signin, register = auth_dialog(False), auth_dialog(True)
                    with ui.element('div').classes('acctrow'):
                        button('Sign in', signin.open, cls='primary small', marker='signin')
                        button('Create account', register.open, cls='primary small ghostbtn', marker='register')

        steps = ''.join(f'<div class="step"><span class="stepnum">{i}</span><b>{title}</b><span>{text}</span></div>'
                        for i, (title, text) in enumerate(HOW_IT_WORKS, start=1))
        ui.html(f'<h2 class="h2">How it works</h2><div class="steps">{steps}</div>', sanitize=False) \
            .classes('section plain')

        rules = ''.join(f'<div class="rule"><h3>{title}</h3><p>{text}</p></div>' for title, text in RULES)
        specials = ''.join(f'<div class="spec"><span class="swatch {css}"></span><p><b>{name}</b> · {text}</p></div>'
                           for css, name, text in SPECIALS)
        ui.html(f'<h2>Rules</h2>{rules}<div class="rule"><h3>Special cards (optional)</h3>{specials}</div>',
                sanitize=False).classes('panel rules')
