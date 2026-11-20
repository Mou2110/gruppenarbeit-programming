"""Shared card faces for the game table and the rules reference."""
from __future__ import annotations

from game.cards import Card, Kind, Suit

SUIT_LABEL = {Suit.SEA: 'Sea', Suit.SARDINE: 'Sardine', Suit.OLIVE: 'Olive', Suit.SUN: 'Sun'}

KIND_LABEL = {
    Kind.WIZARD: 'Wizard', Kind.JESTER: 'Jester', Kind.SHAPESHIFTER: 'Shapeshifter', Kind.DRAGON: 'Dragon',
    Kind.FAIRY: 'Fairy', Kind.BOMB: 'Bomb', Kind.WEREWOLF: 'Werewolf', Kind.JUGGLER: 'Juggler', Kind.CLOUD: 'Cloud',
}

# Symbols as SVG paths (24x24).
SUIT_PATHS = {
    Suit.SEA: '<path d="M2 10c2.5-3 5-3 7.5 0s5 3 7.5 0 3.5-2 5-1"/><path d="M2 16c2.5-3 5-3 7.5 0s5 3 7.5 0 3.5-2 5-1"/>',
    Suit.SARDINE: '<path d="M3 12c3-4.5 9-5.5 14 0-5 5.5-11 4.5-14 0z"/><path d="M17 12l4-3.5v7z"/>',
    Suit.OLIVE: '<path d="M5 19C5 10 11 5 19 5c0 8-5 14-14 14z"/><path d="M5 19L14 10"/>',
    Suit.SUN: ('<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1'
               'M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>'),
}

CARD_RANK = {
    Kind.WIZARD: 'W', Kind.JESTER: 'J', Kind.SHAPESHIFTER: 'S', Kind.DRAGON: 'D',
    Kind.FAIRY: 'F', Kind.BOMB: 'B', Kind.WEREWOLF: 'WW', Kind.JUGGLER: '7½', Kind.CLOUD: '9¾',
}


def svg(paths: str, cls: str = 'ico') -> str:
    """Wraps SVG paths in an <svg> element with a white stroke."""
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths}</svg>')


def suit_icon(suit: Suit) -> str:
    return svg(SUIT_PATHS[suit])


def card_name(card: Card) -> str:
    if card.is_number:
        return f'{SUIT_LABEL[card.suit]} {card.value}'
    return KIND_LABEL[card.kind]


def card_html(card: Card, size: str = 'md', chosen: Suit | None = None) -> str:
    """Render a face-up card and, when applicable, its chosen suit."""
    label = card_name(card)
    if card.is_number:
        face = f'number-face s-{card.suit.value}'
        rank = card.value
        art = f'<span class="suit-emblem">{suit_icon(card.suit)}</span>'
        art += f'<span class="number-suit">{SUIT_LABEL[card.suit]}</span>'
    else:
        face = f'special-face art-{card.kind.value}'
        rank = CARD_RANK[card.kind]
        art = '<span class="special-art"></span>'
        if card.needs_suit_choice and chosen is not None:
            label += f' as {SUIT_LABEL[chosen]}'
            art += f'<span class="chosen-suit s-{chosen.value}">{suit_icon(chosen)}</span>'
    return (f'<div class="card card--{size} {face}" role="img" aria-label="{label}" title="{label}">'
            f'{art}<span class="card-rank">{rank}</span></div>')


def back_html(size: str = 'md', mark: str = '') -> str:
    """HTML for a face-down card (back), optionally with a mark in the center."""
    inner = f'<span class="q">{mark}</span>' if mark else ''
    return f'<div class="card card--{size} back" title="Hidden card">{inner}</div>'
