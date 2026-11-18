"""Leaderboard page: all players with an account and at least 5 finished games.

The ranking rule lives in game/leaderboard.py. This page only reads the sort order from the
address (/leaderboard?sort=bid_rate), asks the database for the totals and draws the rows.
"""
from __future__ import annotations

from nicegui import run, ui

from game.leaderboard import MIN_GAMES, SORT_KEYS, rank
from game.lobby import registry

from .common import ICON_BACK, button, current_account, esc, icon_button, message_page, page_frame

DEFAULT_SORT = 'win_rate'
SORT_LABELS = {
    'win_rate': 'Win rate',
    'wins': 'Wins',
    'games': 'Games',
    'avg_score': 'Avg / game',
    'avg_per_round': 'Avg / round',
    'bid_rate': 'Bids hit',
    'best_score': 'Best',
}
PERCENT_KEYS = ('win_rate', 'bid_rate')


def sort_key(asked: str | None) -> str:
    """The statistic asked for in the address, or win rate if it is missing or unknown."""
    return asked if asked in SORT_KEYS else DEFAULT_SORT


def games_needed(played: int) -> int:
    """How many more finished games a player needs to appear on the leaderboard."""
    return max(0, MIN_GAMES - played)


def display_value(entry: dict, sort_by: str) -> str:
    """The chosen statistic as it is written on the right of a row."""
    value = entry[sort_by]
    if sort_by in PERCENT_KEYS:
        return f'{value} %'
    if sort_by == 'avg_per_round':
        return f'{value:.1f}'
    return str(value)


def view_rows(board: list[dict], sort_by: str, me: str | None) -> list[dict]:
    """The rows of the page. me is the signed-in account key (None for guests)."""
    return [{
        'place': entry['place'],
        'name': entry['name'],
        'detail': f"{entry['games']} games · {entry['wins']} {'win' if entry['wins'] == 1 else 'wins'}",
        'value': display_value(entry, sort_by),
        'me': me is not None and entry['account'] == me,
        'top': entry['place'] == 1,
    } for entry in board]


def _row_html(row: dict) -> str:
    name = esc(row['name']) + (' <em>(you)</em>' if row['me'] else '')
    return (f'<div class="gitem lbitem{" me" if row["me"] else ""}">'
            f'<span class="lbplace{" top" if row["top"] else ""}">{row["place"]}</span>'
            f'<div>{name}<small>{esc(row["detail"])}</small></div>'
            f'<span class="pts">{esc(row["value"])}</span></div>')


async def leaderboard_page(sort: str | None = None) -> None:
    sort_by = sort_key(sort)
    if registry.store is None:
        message_page('Leaderboard not available', 'Results are saved in the database, which is not available.')
        return
    account = await current_account()
    try:
        board = rank(await run.io_bound(registry.store.leaderboard_rows), sort_by)
        played = len(await run.io_bound(registry.store.results_for, account[0])) if account else 0
    except Exception:
        message_page('Leaderboard not available', 'The database could not be reached. Please try again later.')
        return
    rows = view_rows(board, sort_by, account[0] if account else None)

    with page_frame():
        with ui.element('div').classes('pagehead'):
            icon_button(ICON_BACK, 'Back to start', lambda: ui.navigate.to('/'))
            ui.html('<h1>Leaderboard</h1>', sanitize=False)

        with ui.element('div').classes('sortbar mt-s'):
            for key, label in SORT_LABELS.items():
                button(label, lambda key=key: ui.navigate.to(f'/leaderboard?sort={key}'),
                       cls='sortbtn on' if key == sort_by else 'sortbtn', marker=f'sort-{key}')

        if account is None:
            note = 'Create an account on the start page to appear here.'
        elif not any(row['me'] for row in rows):
            missing = games_needed(played)
            note = f"You need {missing} more finished game{'' if missing == 1 else 's'} to appear here."
        else:
            note = ''
        if note:
            ui.html(f'<div class="lbnote">{esc(note)}</div>', sanitize=False).classes('mt-s')

        if not rows:
            ui.html(f'<div class="empty-note">Nobody has finished {MIN_GAMES} games yet. '
                    'Play with an account and you could be first.</div>', sanitize=False)
            return
        ui.html('<div class="glist">' + ''.join(_row_html(row) for row in rows) + '</div>',
                sanitize=False).classes('mt-s')
