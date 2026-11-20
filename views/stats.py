"""Statistics page: only for signed-in players; shows all completed games for the account."""
from __future__ import annotations

import time

from nicegui import run, ui

from game.accounts import AccountError
from game.leaderboard import MIN_GAMES
from game.lobby import registry
from game.presence import presence

from .common import ICON_BACK, ICON_SCORES, button, current_account, esc, icon_button, message_page, page_frame


def summary(results: list[dict]) -> dict:
    """Calculate statistics from the list of the player's games."""
    games = len(results)
    wins = sum(1 for r in results if r['place'] == 1)
    rounds = sum(r['rounds'] for r in results)
    correct = sum(r['correct'] for r in results)
    return {
        'games': games,
        'wins': wins,
        'win_rate': round(100 * wins / games) if games else 0,
        'avg_score': round(sum(r['score'] for r in results) / games) if games else 0,
        'best_score': max((r['score'] for r in results), default=0),
        'bid_rate': round(100 * correct / rounds) if rounds else 0,
    }


def form(results: list[dict], limit: int = 10) -> list[dict]:
    """The last games as a row, oldest on the left. results come newest first.

    kind: 'win' (place 1, also shared), 'last' (last place) or 'mid' (everything in between).
    """
    row = []
    for r in reversed(results[:limit]):
        kind = 'win' if r['place'] == 1 else 'last' if r['place'] == r['players'] else 'mid'
        row.append({'place': r['place'], 'players': r['players'], 'kind': kind})
    return row


def win_streaks(results: list[dict]) -> tuple[int, int]:
    """(current, best) number of wins in a row. results come newest first."""
    current = 0
    for r in results:
        if r['place'] != 1:
            break
        current += 1
    best = run = 0
    for r in results:
        run = run + 1 if r['place'] == 1 else 0
        best = max(best, run)
    return current, best


def streak_text(current: int, best: int) -> str:
    """The sentence under the form."""
    if best == 0:
        return 'No wins yet'
    if current == 0:
        return f'No current streak · Best streak: {best}'
    return f"Current streak: {current} {'win' if current == 1 else 'wins'} in a row · Best streak: {best}"


def _date(timestamp: float) -> str:
    return time.strftime('%d.%m.%Y', time.localtime(timestamp))


def _count(number: int, word: str) -> str:
    return f"{number} {word}{'' if number == 1 else 's'}"


def friend_html(friend: dict, online: bool = False) -> str:
    """Name and totals of one friend. The name links to the profile if the friend has one."""
    name = esc(friend['name'])
    if friend['games'] >= MIN_GAMES:
        name = f'<a class="profile-link" href="/players/{esc(friend["account"])}">{name}</a>'
    if online:
        name += ' <span class="online-dot" style="color: #5BD38B">● online</span>'
    return f"<div>{name}<small>{_count(friend['games'], 'game')} · {_count(friend['wins'], 'win')}</small></div>"


def friends_section(key: str, friends: list[dict]) -> None:
    """Your friends: add someone by username, see their games and wins, remove them again."""
    store = registry.store

    async def add() -> None:
        try:
            name = await run.io_bound(store.add_friend, key, field.value or '')
        except AccountError as error:
            ui.notify(str(error), type='warning')
            return
        except Exception:
            ui.notify('The database could not be reached. Please try again later.', type='negative')
            return
        ui.notify(f'{name} is now your friend.')
        ui.navigate.to('/stats')

    async def remove(friend: str) -> None:
        try:
            await run.io_bound(store.remove_friend, key, friend)
        except Exception:
            ui.notify('The database could not be reached. Please try again later.', type='negative')
            return
        ui.navigate.to('/stats')

    ui.html('<h2 class="h2">Friends</h2>', sanitize=False).classes('mt-s')
    with ui.element('div').classes('row items-center gap-2'):
        field = ui.input(placeholder='Username').classes('namefield') \
            .props('dark outlined dense maxlength=16').mark('friend-name')
        field.on('keydown.enter', add)
        button('Add friend', add, cls='primary small px-4', marker='add-friend')
    if not friends:
        ui.html('<div class="empty-note">No friends yet. Add someone by their username.</div>', sanitize=False)
        return
    with ui.element('div').classes('glist mt-s'):
        for friend in friends:
            with ui.element('div').classes('gitem'):
                ui.html(friend_html(friend, presence.is_online(friend['account'])), sanitize=False)
                ui.element('span')
                button('Remove', lambda friend=friend['account']: remove(friend), cls='primary small ghostbtn px-4',
                       marker=f'remove-{friend["account"]}').style('color: #fff')


async def stats_page() -> None:
    account = await current_account()
    if account is None or registry.store is None:
        message_page('Sign in to see your stats', 'Stats are saved for players with an account. '
                     'You can create one on the start page.')
        return
    try:
        results = await run.io_bound(registry.store.results_for, account[0])
        friends = await run.io_bound(registry.store.friends_of, account[0])
    except Exception:
        message_page('Stats are not available', 'The database could not be reached. Please try again later.')
        return
    s = summary(results)

    with page_frame():
        with ui.element('div').classes('pagehead'):
            icon_button(ICON_BACK, 'Back to start', lambda: ui.navigate.to('/'))
            ui.html(f'<h1>{esc(account[1])}</h1>', sanitize=False)
            ui.element('div').classes('spacer')
            icon_button(ICON_SCORES, 'Leaderboard', lambda: ui.navigate.to('/leaderboard'), marker='leaderboard')

        tiles = [('Games', s['games']), ('Wins', s['wins']), ('Win rate', f"{s['win_rate']}%"),
                 ('Avg points', s['avg_score']), ('Best', s['best_score']), ('Bids hit', f"{s['bid_rate']}%")]
        ui.html('<div class="tiles">' + ''.join(f'<div class="tile"><b>{esc(v)}</b><span>{t}</span></div>'
                                               for t, v in tiles) + '</div>', sanitize=False)

        if results:
            dots = ''.join(f'<span class="fdot {g["kind"]}" title="{g["place"]}. of {g["players"]}">{g["place"]}</span>'
                           for g in form(results))
            ui.html(f'<h2 class="h2">Form</h2><div class="streak">Last 10 games, newest on the right</div>'
                    f'<div class="formrow">{dots}</div>'
                    f'<div class="streak">{esc(streak_text(*win_streaks(results)))}</div>',
                    sanitize=False).classes('mt-s')

        friends_section(account[0], friends)

        ui.html('<h2 class="h2">Recent games</h2>', sanitize=False).classes('mt-s')
        if not results:
            ui.html('<div class="empty-note">No finished games yet. Play one to the end and it shows up here.</div>',
                    sanitize=False)
            return
        rows = []
        for r in results[:30]:
            place = 'Won' if r['place'] == 1 else f"{r['place']}. of {r['players']}"
            rows.append(f'<div class="gitem"><div>{_date(r["finished_at"])}<small>Lobby {esc(r["code"])} · '
                        f'{r["correct"]} of {r["rounds"]} bids hit</small></div>'
                        f'<span class="place{" win" if r["place"] == 1 else ""}">{place}</span>'
                        f'<span class="pts">{r["score"]}</span></div>')
        ui.html('<div class="glist">' + ''.join(rows) + '</div>', sanitize=False)
