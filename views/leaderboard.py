"""Leaderboard page: all players with an account and at least 5 finished games."""
from __future__ import annotations

SORT_LABELS: dict[str, str] = {}


def sort_key(asked: str | None) -> str:
    raise NotImplementedError


def games_needed(played: int) -> int:
    raise NotImplementedError


def display_value(entry: dict, sort_by: str) -> str:
    raise NotImplementedError


def view_rows(board: list[dict], sort_by: str, me: str | None) -> list[dict]:
    raise NotImplementedError
