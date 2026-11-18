"""Statistics page: only for signed-in players; shows all completed games for the account."""
from __future__ import annotations

import time

from nicegui import run, ui

from game.lobby import registry

from .common import ICON_BACK, ICON_SCORES, current_account, esc, icon_button, message_page, page_frame


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
    raise NotImplementedError


def win_streaks(results: list[dict]) -> tuple[int, int]:
    raise NotImplementedError


def streak_text(current: int, best: int) -> str:
    raise NotImplementedError


def _date(timestamp: float) -> str:
    return time.strftime('%d.%m.%Y', time.localtime(timestamp))


async def stats_page() -> None:
    account = await current_account()
    if account is None or registry.store is None:
        message_page('Sign in to see your stats', 'Stats are saved for players with an account. '
                     'You can create one on the start page.')
        return
    try:
        results = await run.io_bound(registry.store.results_for, account[0])
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
