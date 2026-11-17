"""The leaderboard: ranks players with an account by their finished games.

The database adds up each account's games (persistence.leaderboard_rows). This file turns
those totals into the numbers shown on the leaderboard and puts the players in order.
"""
from __future__ import annotations

from fractions import Fraction

MIN_GAMES = 5  # players appear on the leaderboard after this many finished games

# The statistics the leaderboard can be sorted by. For all of them, higher is better.
SORT_KEYS = ('win_rate', 'wins', 'games', 'avg_score', 'avg_per_round', 'bid_rate', 'best_score')


def _ratio(part: int, whole: int) -> Fraction:
    """part / whole as an exact fraction (0 if whole is 0), so equal rates compare as equal."""
    return Fraction(part, whole) if whole else Fraction(0)


def _exact(row: dict) -> dict:
    """The exact value of every statistic, used for sorting."""
    return {
        'win_rate': _ratio(row['wins'], row['games']),
        'wins': row['wins'],
        'games': row['games'],
        'avg_score': _ratio(row['points'], row['games']),
        'avg_per_round': _ratio(row['points'], row['rounds']),
        'bid_rate': _ratio(row['correct'], row['rounds']),
        'best_score': row['best'],
    }


def _shown(row: dict, exact: dict) -> dict:
    """The rounded numbers shown on the page (rounded like on the stats page)."""
    return {
        'account': row['account'],
        'name': row['name'],
        'games': row['games'],
        'wins': row['wins'],
        'win_rate': round(100 * exact['win_rate']),
        'avg_score': round(exact['avg_score']),
        'avg_per_round': round(float(exact['avg_per_round']), 1),
        'best_score': row['best'],
        'bid_rate': round(100 * exact['bid_rate']),
    }


def rank(rows: list[dict], sort_by: str = 'win_rate') -> list[dict]:
    """Put the players in order by one statistic and give each a place.

    Higher values come first. On equal values the player with more games comes first
    (more games = more evidence). If that is equal too, both share the place.
    """
    if sort_by not in SORT_KEYS:
        raise ValueError(f'Unknown statistic: {sort_by}')
    players = [(_exact(row), row) for row in rows]
    players.sort(key=lambda p: (-p[0][sort_by], -p[0]['games'], p[1]['name'].lower()))

    board = []
    for exact, row in players:
        entry = _shown(row, exact)
        # place = 1 + number of players who are better (same rule as the places in a game)
        entry['place'] = 1 + sum(1 for other, _ in players
                                 if (other[sort_by], other['games']) > (exact[sort_by], exact['games']))
        board.append(entry)
    return board
