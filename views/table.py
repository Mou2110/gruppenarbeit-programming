"""The game table for an active match, as seen by a specific player.

render_table() renders the complete table from lobby.game.view_for(pid).
The lobby page calls it from a ui.refreshable and redraws whenever
something in the game changes (including other players' moves).
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from functools import partial

from nicegui import ui

from game.cards import Card, Kind, Suit
from game.engine import GameError
from game.lobby import Lobby
from game.rules import Play, lead_suit, trick_winner

from .cards import KIND_LABEL, SUIT_LABEL, back_html, card_html, card_name, suit_icon
from .common import ICON_EXIT, ICON_SCORES, button, esc, icon_button

ACTIVE = {'werewolf', 'choosing_trump', 'bidding', 'playing', 'adjusting'}

SUIT_ORDER = {Suit.SEA: 0, Suit.SARDINE: 1, Suit.OLIVE: 2, Suit.SUN: 3}
SPECIAL_ORDER = {Kind.DRAGON: (0, 0), Kind.WIZARD: (0, 1), Kind.SHAPESHIFTER: (0, 2), Kind.JUGGLER: (6, 0),
                 Kind.CLOUD: (6, 1), Kind.JESTER: (9, 0), Kind.FAIRY: (9, 1), Kind.BOMB: (9, 2), Kind.WEREWOLF: (9, 3)}


def _hand_order(card: Card) -> tuple[int, float]:
    """Sort order for the player hand: strong special cards first, then suits, Jester-like cards last."""
    if card.is_number:
        return (1 + SUIT_ORDER[card.suit], card.value)
    return SPECIAL_ORDER[card.kind]


def _name(v: dict, index: int | None) -> str:
    if index is None:
        return 'Nobody'
    return 'You' if index == v['my_index'] else v['players'][index]['name']


def _verb(v: dict, index: int, you: str, other: str) -> str:
    """Small grammar helper: "You win" / "Marta wins"."""
    return f'You {you}' if index == v['my_index'] else f'{_name(v, index)} {other}'


# ---------------------------------------------------------------- HTML-Bausteine

def _badge(v: dict, p: dict) -> str:
    bid = '–' if p['bid'] is None else str(p['bid'])
    if p['bid_change']:
        bid += f'→{p["bid"] + p["bid_change"]}'
    if v['phase'] in ('werewolf', 'choosing_trump', 'bidding'):
        return f'Bid {bid}'
    return f'Bid {bid} · Won {p["tricks_won"]}'


def _avatar(v: dict, index: int) -> str:
    turn = ' turn' if index == v['current'] and v['phase'] in ACTIVE else ''
    if v['phase'] == 'passing' and not v['players'][index]['has_passed']:
        turn = ' turn'
    dealer = '<span class="dealer" title="Dealer">D</span>' if index == v['dealer'] else ''
    initial = esc(v['players'][index]['name'][:1].upper() or '?')
    return f'<div class="avatar{turn}">{initial}{dealer}</div>'


def _seat_html(v: dict, index: int, lobby: Lobby) -> str:
    p = v['players'][index]
    member = lobby.member(p['id'])
    # Bot / away: shown as a small badge on the avatar instead of on a separate line to keep seats compact.
    mark = ''
    if member is not None and member.is_bot:
        mark = '<span class="seatmark">BOT</span>'
    elif lobby.is_absent(p['id']):
        mark = '<span class="seatmark away">AWAY</span>'
    if v['clairvoyance']:  # Clairvoyance: this player's card is visible (the seat remains reserved)
        cards = ''.join(card_html(c, 'sm') for c in (p['visible_hand'] or []))
        extra = f'<div class="seen">{cards}</div>'
    elif v['phase'] == 'passing':
        extra = f'<span class="cardsleft">{"passed" if p["has_passed"] else "passing…"}</span>'
    else:
        count = p['cards_left']
        extra = f'<span class="cardsleft">{count} card{"s" if count != 1 else ""}</span>'
    avatar = _avatar(v, index)
    return (f'<div class="seat"><div class="avwrap">{avatar}{mark}</div><span class="pname">{esc(p["name"])}</span>'
            f'<span class="badge">{_badge(v, p)}</span>{extra}</div>')


def _trump_html(v: dict) -> str:
    """Top left: the revealed card and, next to it, a single-suit card showing the trump suit."""
    card = v['trump_card']
    face = card_html(card, 'sm') if card else '<div class="card card--sm empty"></div>'
    if v['phase'] in ('werewolf', 'choosing_trump'):
        suit, colour = 'Choosing…', '<div class="card card--md suitcard pending"><span class="num">?</span></div>'
    elif v['trump']:
        suit = SUIT_LABEL[v['trump']]
        colour = (f'<div class="card card--md suitcard s-{v["trump"].value}" title="Trump: {suit}">'
                  f'{suit_icon(v["trump"])}<span class="lbl">{suit}</span></div>')
    else:
        suit, colour = 'No trump', '<div class="card card--md suitcard none"><span class="lbl">No trump</span></div>'
    return (f'<div class="trump"><div class="trumpcards">{face}{colour}</div>'
            f'<span class="tl">Trump</span><span class="ts">{suit}</span></div>')


def _lead_html(v: dict) -> str:
    lead = lead_suit(v['trick']) if v['trick'] else None
    if lead is None:
        return ''
    return f'<span class="chip" title="Suit to follow">{suit_icon(lead)}{SUIT_LABEL[lead]}</span>'


def _slot_position(v: dict, player: int) -> tuple[float, float]:
    """Fixed position (as a percentage of the table center) where a player's card is placed.

    Seats form an ellipse: you are at the bottom, and the others go clockwise
    up the left side and across the top to the right. With 3 players, two are at the top and one at the bottom.
    """
    n = len(v['players'])
    relative = (player - v['my_index']) % n
    angle = math.radians(270 - relative * 360 / n)
    return 50 + 30 * math.cos(angle), 50 - 30 * math.sin(angle)


def _trick_html(v: dict, paused: bool, seen: set | None = None) -> str:
    """Cards in the center of the table. seen: cards already shown by this browser.
    All others have just been played and slide from their player into place."""
    finished = paused and not v['trick'] and bool(v['last_trick'])
    plays: list[Play] = v['last_trick'] if finished else v['trick']
    if not plays:
        if v['phase'] in ('werewolf', 'choosing_trump', 'bidding'):
            return '<span class="hint">Waiting for bids…</span>'
        return ''
    best = trick_winner(plays, v['trump'])
    bombed = any(p.card.kind == Kind.BOMB for p in plays)
    parts = []
    for pos, play in enumerate(plays):
        if play.card.kind == Kind.BOMB:
            tag = '<span class="tag dark">Bomb</span>'
        elif pos == best:
            if bombed:
                text = 'Leads next' if finished else 'Would win'
            else:
                text = 'Wins' if finished else 'Leading'
            tag = f'<span class="tag">{text}</span>'
        else:
            tag = '<span class="tag ghost">-</span>'
        note = ''
        if play.card.needs_role_choice:
            note = f'<span class="as">as {"Wizard" if play.as_wizard else "Jester"}</span>'
        x, y = _slot_position(v, play.player)
        enter, start = '', ''
        if seen is not None and play.card.id not in seen:
            # Starting point: farther out toward the player who played the card
            # (your own card comes up from your hand at the bottom).
            fx, fy = (x - 50) * 4, (y - 50) * 4.5
            if play.player == v['my_index']:
                fy = 170
            enter, start = ' enter', f'--fx:{fx:.0f}px;--fy:{fy:.0f}px;'
            seen.add(play.card.id)
        parts.append(f'<div class="tslot{enter}" style="{start}left:{x:.1f}%;top:{y:.1f}%;z-index:{pos + 1}" '
                     f'title="{esc(_name(v, play.player))}">{tag}{card_html(play.card, "md", chosen=play.suit)}'
                     f'{note}</div>')
    return ''.join(parts)


def _status(v: dict, paused: bool) -> tuple[str, bool]:
    """Status line text and whether it is currently this player's turn."""
    me, current, phase = v['my_index'], v['current'], v['phase']
    if paused and v['last_trick'] and not v['trick']:
        leader = v['last_trick_leader']
        if v['last_trick_bombed']:
            return f'Bomb! Nobody gets the trick · {_verb(v, leader, "lead", "leads")} next', leader == me
        return f'{_verb(v, leader, "win", "wins")} the trick', leader == me
    mine = v['my_turn']
    if phase == 'werewolf':
        return ('You have the Werewolf: choose trump' if mine
                else f'{_name(v, current)} has the Werewolf and picks trump…'), mine
    if phase == 'choosing_trump':
        return ('Choose the trump suit' if mine else f'{_name(v, current)} is choosing trump…'), mine
    if phase == 'bidding':
        return ('Your turn to bid' if mine else f'{_name(v, current)} is bidding…'), mine
    if phase == 'playing' and v['awaiting_choice'] is not None:
        card = card_name(v['trick'][-1].card)
        if v['must_declare']:
            return f'Your card is the {card}: make your choice', True
        return f'{_name(v, current)} is choosing for the {card}…', False
    if phase == 'playing':
        if not mine:
            return f'{_name(v, current)} is playing…', False
        lead = lead_suit(v['trick']) if v['trick'] else None
        hand = v['my_hand'] or []
        if lead and any(c.is_number and c.suit == lead for c in hand):
            return f'Your turn · follow {SUIT_LABEL[lead]}', True
        return 'Your turn', True
    if phase == 'passing':
        if v['must_pass']:
            return f'Juggler! Pass one card to {_name(v, v["pass_target"])}', True
        waiting = [_name(v, i) for i, p in enumerate(v['players']) if not p['has_passed']]
        return f'Waiting for {", ".join(waiting)} to pass a card…', False
    if phase == 'adjusting':
        return ('The Cloud is yours: change your bid by one' if mine
                else f'{_name(v, current)} has the Cloud and changes their bid…'), mine
    return ('Round finished' if phase == 'round_over' else 'Game over'), False


def _phase_text(v: dict) -> str:
    phase = v['phase']
    if phase in ('werewolf', 'choosing_trump'):
        return 'Choosing trump'
    if phase == 'bidding':
        return 'Clairvoyance · Bidding' if v['clairvoyance'] else 'Bidding'
    if phase in ('playing', 'passing'):
        played_by_me = any(p.player == v['my_index'] for p in v['trick'])
        done = v['round'] - v['my_hand_size'] - (1 if played_by_me else 0)
        return f'Trick {min(done + 1, v["round"])} of {v["round"]}'
    if phase == 'adjusting':
        return 'Cloud'
    return 'Round finished' if phase == 'round_over' else 'Game over'


def _me_html(v: dict) -> str:
    me = v['my_index']
    p = v['players'][me]
    return (f'<div class="me">{_avatar(v, me)}<span class="pname">{esc(p["name"])} (you)</span>'
            f'<span class="badge">{_badge(v, p)}</span></div>')


# ------------------------------------------------------------------- The table

def render_table(lobby: Lobby, pid: str, state: dict, refresh_self: Callable[[], None]) -> None:
    """Renders the table for player pid. state holds data specific to this browser tab."""
    v = lobby.game.view_for(pid)
    paused = lobby.is_paused()
    n, me = len(v['players']), v['my_index']
    others = [(me + k) % n for k in range(1, n)]
    left, right, top = others[0], others[-1], others[1:-1]

    # Did the player receive a Juggler card? Show a brief notification.
    if v['pass_count'] != state.get('seen_pass', v['pass_count']) and v['received'] is not None:
        ui.notify(f'You received {card_name(v["received"])}', type='info', position='top')
    state['seen_pass'] = v['pass_count']

    def act(action: str, **kwargs) -> None:
        state['pending'] = None
        try:
            lobby.act(pid, action, **kwargs)
        except GameError as error:
            ui.notify(str(error), type='warning')
            refresh_self()

    def first_tap(card_id: str) -> bool:
        """On a phone: the first tap only selects the card (it lifts above the others).
        The second tap plays it. This prevents accidental plays when many cards overlap."""
        if state.get('touch') and state.get('selected') != card_id:
            state['selected'] = card_id
            # # Update only the browser instead of redrawing the hand: the card slides smoothly upward
            # (and the previously selected card slides smoothly back down).
            chosen = next(c for c in v['my_hand'] if c.id == card_id)
            text = f'Tap again to {"pass" if v["must_pass"] else "play"} {card_name(chosen)}'
            ui.run_javascript(
                "document.querySelectorAll('.hcard.selected').forEach(e => e.classList.remove('selected'));"
                f"const el = document.querySelector('.hcard[data-card=\"{card_id}\"]');"
                "if (el) el.classList.add('selected');"
                "const s = document.querySelector('.statusrow .status');"
                f"if (s) {{ s.textContent = {json.dumps(text)}; s.classList.remove('wait'); }}")
            return True
        state['selected'] = None
        return False

    def pass_card(card_id: str) -> None:
        if not first_tap(card_id):
            act('pass', card_id=card_id)

    def choose(card_id: str) -> None:
        """Card clicked: play it directly or ask for a suit or role first."""
        if first_tap(card_id):
            return
        card = next(c for c in v['my_hand'] if c.id == card_id)
        if card.needs_suit_choice or card.needs_role_choice:
            state['pending'] = card_id
            refresh_self()
        else:
            act('play', card_id=card_id)

    def set_state(key: str, value) -> None:
        state[key] = value
        refresh_self()

    # --- Panels in the center of the table ---
    def werewolf_panel() -> None:
        with ui.element('div').classes('panel'):
            ui.html(f'<h2>You drew the Werewolf</h2><p>It swaps places with the trump card '
                    f'({card_name(v["trump_card"])}). Pick the trump suit for this round, or play without trump.</p>',
                    sanitize=False)
            with ui.element('div').classes('suitgrid'):
                for suit in Suit:
                    button(SUIT_LABEL[suit], partial(act, 'trump', suit=suit), cls=f'suitbtn s-{suit.value}',
                           icon=None, marker='trump')
            button('No trump', partial(act, 'trump', suit=None), marker='trump')

    def trump_panel() -> None:
        with ui.element('div').classes('panel'):
            ui.html(f'<h2>Choose the trump suit</h2><p>A {card_name(v["trump_card"])} was turned up, '
                    f'so the dealer picks.</p>', sanitize=False)
            with ui.element('div').classes('suitgrid'):
                for suit in Suit:
                    button(SUIT_LABEL[suit], partial(act, 'trump', suit=suit), cls=f'suitbtn s-{suit.value}',
                           marker='trump')

    def bid_panel() -> None:
        bids = sum(p['bid'] or 0 for p in v['players'])
        hint = ("You can't see your own card, only everyone else's."
                if v['clairvoyance'] else f'{v["my_hand_size"]} card{"s" if v["my_hand_size"] != 1 else ""} in hand')
        forbidden = v['forbidden_bid']
        with ui.element('div').classes('panel'):
            ui.html(f'<h2>How many tricks will you take?</h2><p>{hint}</p>', sanitize=False)
            with ui.element('div').classes('numgrid'):
                for bid in range(v['round'] + 1):
                    if bid == forbidden:
                        button(str(bid), cls='numbtn off', disabled=True, label=f'{bid} is not allowed')
                    else:
                        button(str(bid), partial(act, 'bid', bid=bid), cls='numbtn', marker='bid')
            note = f'Bids so far: {bids} of {v["round"]} trick{"s" if v["round"] != 1 else ""}.'
            if forbidden is not None:
                note += f" You bid last, so you can't say {forbidden}: the bids must not add up to {v['round']}."
            ui.html(f'<p>{note}</p>', sanitize=False)

    def adjust_panel() -> None:
        mine = v['players'][me]
        won = mine['tricks_won']
        with ui.element('div').classes('panel'):
            ui.html(f'<h2>You won the Cloud</h2><p>Your bid of {mine["bid"]} must go up or down by one right now. '
                    f'You have won {won} trick{"s" if won != 1 else ""} so far.</p>', sanitize=False)
            with ui.element('div').classes('suitgrid'):
                for change in v['adjust_options']:
                    button(f'Bid {mine["bid"] + change} ({change:+d})', partial(act, 'adjust', change=change),
                           cls='numbtn wide', marker='adjust')

    # --- Card with a choice (Juggler, Cloud, Shapeshifter) ---
    def choice_sheet(card: Card, declare: bool = False) -> None:
        def pick(**choice) -> None:
            if declare:
                act('declare', **choice)
            else:
                act('play', card_id=card.id, **choice)

        with ui.element('div').classes('sheet'), ui.element('div').classes('panel'):
            if card.needs_suit_choice:
                value = '7½' if card.kind == Kind.JUGGLER else '9¾'
                ui.html(f'<h2>Play the {KIND_LABEL[card.kind]} ({value}) as…</h2>'
                        f'<p>It counts as {value} in the suit you pick, also the trump suit.</p>', sanitize=False)
                with ui.element('div').classes('suitgrid'):
                    for suit in Suit:
                        button(SUIT_LABEL[suit], partial(pick, suit=suit),
                               cls=f'suitbtn s-{suit.value}', marker='choice')
            else:
                ui.html('<h2>Play the Shapeshifter as…</h2><p>It then counts exactly like that card.</p>',
                        sanitize=False)
                with ui.element('div').classes('suitgrid'):
                    button('Wizard', partial(pick, as_wizard=True), cls='suitbtn k-wizard', marker='choice')
                    button('Jester', partial(pick, as_wizard=False), cls='suitbtn k-jester', marker='choice')
            if not declare:
                button('Cancel', partial(set_state, 'pending', None), cls='primary ghostbtn')

    # --- player hand ---
    def hand() -> None:
        can_play = v['phase'] == 'playing' and v['my_turn']
        with ui.element('div').classes('hand'):
            if v['my_hand'] is None:  # Clairvoyance: own card is hidden
                with ui.element('div').classes('handrow'):
                    for _ in range(v['my_hand_size']):
                        element = ui.html(back_html('lg', '?'), sanitize=False).classes('hcard')
                        if can_play and v['playable']:
                            element.classes('playable')
                            element.on('click', partial(act, 'play', card_id=v['playable'][0])).mark('playable')
                return
            # All cards in one row. If there is not enough room, CSS makes them overlap.
            with ui.element('div').classes('handrow'):
                for card in sorted(v['my_hand'], key=_hand_order):
                        element = ui.html(card_html(card, 'lg'), sanitize=False).classes('hcard') \
                            .props(f'data-card={card.id}')
                        if card.id == state.get('selected'):
                            element.classes('selected')
                        if v['must_pass']:
                            element.classes('playable')
                            element.on('click', partial(pass_card, card.id)).mark('pass')
                        elif can_play:
                            if card.id in v['playable']:
                                element.classes('playable')
                                if card.id == state.get('pending'):
                                    element.classes('picked')
                                element.on('click', partial(choose, card.id)).mark('playable')
                            else:
                                element.classes('dim')

    # --- Results, scoreboard, leave ---
    def results_overlay() -> None:
        over = v['phase'] == 'game_over'
        # Sort by total score: the leader is at the top (ties keep the seating order).
        rows = sorted(v['players'], key=lambda p: -p['score'])
        lines = []
        for rank, p in enumerate(rows):
            points = p['round_scores'][-1] if p['round_scores'] else 0
            css = 'pos' if points > 0 else 'neg'
            top_row = ' class="top"' if rank == 0 else ''
            name = esc(p['name']) + (' (you)' if p['id'] == pid else '')
            bid = str(p['bid']) + (f'→{p["bid"] + p["bid_change"]}' if p['bid_change'] else '')
            lines.append(f'<tr{top_row}><td>{name}</td><td class="r">{bid}</td><td class="r">{p["tricks_won"]}</td>'
                         f'<td class="r {css}">{points:+d}</td><td class="r">{p["score"]}</td></tr>')
        title = 'Final standings' if over else f'Round {v["round"]} results'
        table = ('<table class="restbl"><tr><th>Player</th><th class="r">Bid</th><th class="r">Won</th>'
                 '<th class="r">Round</th><th class="r">Total</th></tr>' + ''.join(lines) + '</table>')
        with ui.element('div').classes('overlay'), ui.element('div').classes('panel'):
            ui.html(f'<h2>{title}</h2>{table}', sanitize=False)
            if over:
                winner = rows[0]
                who = 'You win' if winner['id'] == pid else f'{esc(winner["name"])} wins'
                ui.html(f'<p>{who} with {winner["score"]} points.</p>', sanitize=False)
            if pid in lobby.votes:
                waiting = ', '.join(esc(m.name) for m in lobby.waiting_for_votes()) or 'the others'
                ui.html(f'<p class="waiting">Waiting for {waiting}…</p>', sanitize=False)
            else:
                button('Back to lobby' if over else 'Next round', lambda: lobby.vote_continue(pid),
                       marker='continue')

    def scores_overlay() -> None:
        players = v['players']
        head = ''.join(f'<th class="r">{esc(p["name"])}</th>' for p in players)
        rounds = max((len(p['round_scores']) for p in players), default=0)
        body = ''.join(
            f'<tr><td>{r + 1}</td>' + ''.join(f'<td class="r">{p["round_scores"][r]:+d}</td>' for p in players)
            + '</tr>' for r in range(rounds))
        totals = ''.join(f'<td class="r">{p["score"]}</td>' for p in players)
        table = (f'<table class="restbl"><tr><th>Round</th>{head}</tr>{body}'
                 f'<tr class="top"><td>Total</td>{totals}</tr></table>')
        with ui.element('div').classes('overlay'), ui.element('div').classes('panel'):
            ui.html(f'<h2>Scoreboard</h2>{table}', sanitize=False)
            button('Close', partial(set_state, 'scores_open', False))

    def leave_overlay() -> None:
        def leave() -> None:
            lobby.leave(pid)
            ui.navigate.to('/')
        with ui.element('div').classes('overlay'), ui.element('div').classes('panel'):
            ui.html('<h2>Leave the table?</h2><p><b>Back to start</b> keeps your seat: you can rejoin any time '
                    'from "Your games". The game waits for you until you are back.</p>'
                    '<p><b>Leave for good</b> gives your seat to a bot for the rest of the game.</p>',
                    sanitize=False)
            button('Back to start', lambda: ui.navigate.to('/'), marker='home')
            button('Leave for good', leave, cls='primary ghostbtn', marker='leave')
            button('Stay', partial(set_state, 'confirm_leave', False), cls='linkbtn authswitch')

    # --- complete table ---
    with ui.element('div').classes('topbar'):
        icon_button(ICON_EXIT, 'Leave game', partial(set_state, 'confirm_leave', True))
        ui.html(f'<div class="rinfo"><b>Round {v["round"]} of {v["total_rounds"]}</b>'
                f'<span>{_phase_text(v)}</span></div>', sanitize=False)
        icon_button(ICON_SCORES, 'Scoreboard', partial(set_state, 'scores_open', True))

    with ui.element('div').classes('board'):
        ui.html(_trump_html(v), sanitize=False).classes('a-trump')
        ui.html('<div class="topseats">' + ''.join(_seat_html(v, i, lobby) for i in top) + '</div>',
                sanitize=False).classes('a-top')
        ui.html(_lead_html(v), sanitize=False).classes('a-lead')
        ui.html(_seat_html(v, left, lobby), sanitize=False).classes('a-left')
        with ui.element('div').classes('a-trick'):
            phase = v['phase']
            if phase == 'werewolf' and v['my_turn']:
                werewolf_panel()
            elif phase == 'choosing_trump' and v['my_turn']:
                trump_panel()
            elif phase == 'bidding' and v['my_turn']:
                bid_panel()
            elif phase == 'adjusting' and v['my_turn']:
                adjust_panel()
            else:
                # Which cards has this browser already seen? On the first render (e.g. after a reload)
                # nothing slides; afterwards, only the newly played card does.
                shown = [p.card.id for p in (v['trick'] or v['last_trick'])]
                if 'seen_trick' not in state:
                    state['seen_trick'] = set(shown)
                state['seen_trick'] &= set(shown)
                ui.html(_trick_html(v, paused, state['seen_trick']), sanitize=False).classes('trick')
        ui.html(_seat_html(v, right, lobby), sanitize=False).classes('a-right')

    # A selected card (phone) stays selected only while it can be played or passed.
    selectable = v['playable'] if (v['phase'] == 'playing' and v['my_turn']) else (
        [c.id for c in v['my_hand'] or []] if v['must_pass'] else [])
    if state.get('selected') not in selectable:
        state['selected'] = None
    text, mine = _status(v, paused)
    if state.get('selected'):
        chosen = next(c for c in v['my_hand'] if c.id == state['selected'])
        verb = 'pass' if v['must_pass'] else 'play'
        text, mine = f'Tap again to {verb} {card_name(chosen)}', True
    # If the player whose turn it is has gone away, the game waits for them - show that clearly.
    if not mine and not paused and v['phase'] in ACTIVE:
        waiting_for = v['players'][v['current']]
        member = lobby.member(waiting_for['id'])
        if member is not None and not member.is_bot and not lobby.is_online(member.id):
            text = f'Waiting for {waiting_for["name"]} · away'
    if v['phase'] == 'passing':
        away = [p['name'] for p in v['players'] if not p['has_passed'] and (m := lobby.member(p['id']))
                and not m.is_bot and not lobby.is_online(m.id)]
        if away:
            text = 'Waiting for ' + ', '.join(away) + ' · away'

    # Bottom: player info and status line (side by side on wide screens to save height)
    with ui.element('div').classes('bottombar'):
        ui.html(f'<span class="status{"" if mine else " wait"}">{esc(text)}</span>',
                sanitize=False).classes('statusrow')
        ui.html(_me_html(v), sanitize=False).classes('mewrap')
    hand()

    pending = state.get('pending')
    if v['must_declare']:
        state['pending'] = None
        choice_sheet(v['trick'][-1].card, declare=True)
    elif pending and v['phase'] == 'playing' and v['my_turn'] and pending in v['playable']:
        choice_sheet(next(c for c in v['my_hand'] if c.id == pending))
    else:
        state['pending'] = None

    if state.get('confirm_leave'):
        leave_overlay()
    elif v['phase'] in ('round_over', 'game_over') and not paused:
        results_overlay()
    elif state.get('scores_open'):
        scores_overlay()
