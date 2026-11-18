"""Generates the HTML for individual cards in the Azulejo design.

The visual styling (colors, sizes) is defined in static/styles.css. This file only
assembles the basic structure of a card.
"""
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
COMPASS_PATHS = ('<circle cx="12" cy="12" r="9.5"/><path d="M12 3.5l2 8.5-2 8.5-2-8.5z"/>'
                 '<path d="M3.5 12l8.5-2 8.5 2-8.5 2z"/>')
WING_PATHS = '<path d="M3 19C6 11 12 6 21 4c-2 3-2 5-1 7-3 0-5 1-6 3-2-1-4 0-5 2-2-1-4 0-6 3z"/><path d="M9 13l5-4"/>'
SPARKLE_PATHS = ('<path d="M11 3l1.8 6.2L19 11l-6.2 1.8L11 19l-1.8-6.2L3 11l6.2-1.8z"/>'
                 '<path d="M19 15l.7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7z"/>')
BOMB_PATHS = '<circle cx="10.5" cy="14.5" r="6.5"/><path d="M15 10l3-3"/><path d="M19.5 2.5v2M22 5h-2M21 7.5l-1.2-1.2"/>'
BALLS_PATHS = ('<circle cx="6" cy="15" r="2.5"/><circle cx="12" cy="7" r="2.5"/><circle cx="18" cy="15" r="2.5"/>'
               '<path d="M4 21c4-2 12-2 16 0"/>')
CLOUD_PATHS = '<path d="M7 18h10a4 4 0 0 0 0-8 6 6 0 0 0-11.5 1.5A3.5 3.5 0 0 0 7 18z"/>'

# Werewolf teeth (custom canvas, 100x66).
_UPPER = ['12,15.6 20,15.6 16,23.6', '21,13.3 31,13.3 26,31.3', '32,11.8 40,11.8 36,19.8', '42,11.1 50,11.1 46,19.1',
          '50,11.1 58,11.1 54,19.1', '60,11.8 68,11.8 64,19.8', '69,13.3 79,13.3 74,31.3', '80,15.6 88,15.6 84,23.6']
_LOWER = ['18,54.4 26,54.4 22,47.4', '27,56.5 37,56.5 32,41.5', '38,57.7 46,57.7 42,50.7', '46,58 54,58 50,51',
          '54,57.7 62,57.7 58,50.7', '63,56.5 73,56.5 68,41.5', '74,54.4 82,54.4 78,47.4']
TEETH_SVG = ('<svg class="ico wolf" viewBox="0 0 100 66" fill="none" stroke="currentColor" stroke-width="3" '
             'stroke-linecap="round" aria-hidden="true"><path d="M8 18Q50 4 92 18"/><path d="M14 52Q50 64 86 52"/>'
             '<g fill="currentColor" stroke="none">'
             + ''.join(f'<polygon points="{p}"/>' for p in _UPPER + _LOWER) + '</g></svg>')

FLAMES_SVG = ('<svg class="flames" viewBox="0 0 140 210" preserveAspectRatio="none" aria-hidden="true">'
              '<path d="M0 210V178C12 168 10 156 18 146C22 160 30 164 34 156C38 146 34 136 44 126C46 142 56 150 62 140'
              'C66 132 64 124 70 114C76 128 80 140 88 136C94 132 92 122 100 116C102 132 110 142 118 136'
              'C124 130 122 152 128 148C134 146 136 160 140 162V210Z" fill="#D24E1C"/>'
              '<path d="M44 210C46 196 52 188 56 178C60 188 64 190 68 180C72 170 70 162 76 154C80 168 86 176 90 186'
              'C94 180 96 174 100 172C100 186 98 198 100 210Z" fill="#E36A24"/></svg>')

ZZZ = '<span class="zzz"><i>Z</i><i>Z</i><i>Z</i></span>'


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
    """HTML for a face-up card. size: 'sm', 'md', or 'lg'.

    chosen: the suit selected when playing a Juggler or Cloud (colors the card).
    """
    kind = card.kind
    label = card_name(card)
    if kind == Kind.NUMBER:
        value = card.value
        body = f'<span class="idx">{value}</span><span class="num">{value}</span>{suit_icon(card.suit)}'
        css = f's-{card.suit.value}'
    elif kind == Kind.WIZARD:
        body = f'<span class="idx">W</span>{svg(COMPASS_PATHS, "ico big")}<span class="lbl">Wizard</span>'
        css = 'k-wizard'
    elif kind == Kind.JESTER:
        body = f'<span class="idx">J</span>{ZZZ}<span class="lbl">Jester</span>'
        css = 'k-jester'
    elif kind == Kind.SHAPESHIFTER:
        body = (f'<span class="half up">{svg(COMPASS_PATHS, "ico")}</span>'
                f'<span class="half down">{ZZZ}</span><span class="band">Shapeshifter</span>')
        css = 'k-shift'
    elif kind == Kind.DRAGON:
        body = f'{FLAMES_SVG}<span class="idx">D</span>{svg(WING_PATHS, "ico big")}<span class="lbl">Dragon</span>'
        css = 'k-dragon'
    elif kind == Kind.FAIRY:
        body = f'<span class="idx">F</span>{svg(SPARKLE_PATHS, "ico big")}<span class="lbl">Fairy</span>'
        css = 'k-fairy'
    elif kind == Kind.BOMB:
        body = f'{svg(BOMB_PATHS, "ico big")}<span class="lbl">Bomb</span>'
        css = 'k-bomb'
    elif kind == Kind.WEREWOLF:
        body = f'{TEETH_SVG}<span class="lbl">Werewolf</span>'
        css = 'k-wolf'
    else:  # Juggler or Cloud
        value, paths = ('7½', BALLS_PATHS) if kind == Kind.JUGGLER else ('9¾', CLOUD_PATHS)
        body = (f'<span class="idx">{value}</span><span class="num frac">{value}</span>'
                f'{svg(paths)}<span class="lbl">{label}</span>')
        css = f's-{chosen.value}' if chosen else 'k-multi'
        if chosen:
            label = f'{label} as {SUIT_LABEL[chosen]}'
    return f'<div class="card card--{size} {css}" title="{label}">{body}</div>'


def back_html(size: str = 'md', mark: str = '') -> str:
    """HTML for a face-down card (back), optionally with a mark in the center."""
    inner = f'<span class="q">{mark}</span>' if mark else ''
    return f'<div class="card card--{size} back" title="Hidden card">{inner}</div>'
