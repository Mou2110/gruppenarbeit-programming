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

from game.cards import Card, Kind, Suit, hand_order
from game.engine import GameError
from game.lobby import Lobby
from game.rules import trick_has_bomb, Play, lead_suit, trick_winner

from .cards import KIND_LABEL, SUIT_LABEL, back_html, card_html, card_name, suit_emblem, suit_icon
from .common import ICON_EXIT, ICON_INFO, ICON_SCORES, button, esc, icon_button

ACTIVE = {'werewolf', 'choosing_trump', 'bidding', 'playing', 'adjusting'}




# When CR7 is played, every browser says "Siuuu". Spoken by the browser itself (Web Speech API), so there is
# no audio file and no recording of anyone's voice. Browsers without speech simply stay silent.
SIUUU_JS = ("if (window.speechSynthesis) { const u = new SpeechSynthesisUtterance('Siuuuuu!');"
            " u.rate = 0.6; u.pitch = 1.4; window.speechSynthesis.speak(u); }")


def cheer_for_cr7(v: dict, state: dict, game_number: int) -> bool:
    """True once per round when CR7 lands on the table (also as the last card of a trick).

    Remembers game AND round: after a rematch, round 3 is a new round 3 (found by Jakob).
    """
    on_table = list(v['trick']) + list(v['last_trick'] or [])
    key = (game_number, v['round'])
    if not any(p.card.kind == Kind.CR7 for p in on_table) or state.get('siuuu_at') == key:
        return False
    state['siuuu_at'] = key
    return True


def trick_bombed(plays: list[Play]) -> bool:
    """Does the Bomb take effect in this trick? (Not if CR7 is in it.)"""
    return trick_has_bomb(plays)

_hand_order = hand_order   # order of the hand from left to right (game/cards.py)


def _name(v: dict, index: int | None) -> str:
    if index is None:
        return 'Nobody'
    return 'You' if index == v['my_index'] else v['players'][index]['name']


def _verb(v: dict, index: int, you: str, other: str) -> str:
    """Small grammar helper: "You win" / "Marta wins"."""
    return f'You {you}' if index == v['my_index'] else f'{_name(v, index)} {other}'


# ---------------------------------------------------------------- HTML-Bausteine

def _bid_value(p: dict) -> str:
    bid = '–' if p['bid'] is None else str(p['bid'])
    if p['bid_change']:
        bid += f'→{p["bid"] + p["bid_change"]}'
    return bid


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
    if v['clairvoyance'] and index != v['my_index']:
        cards = ''.join(card_html(c, 'sm') for c in (p['visible_hand'] or []))
        extra = f'<div class="seen">{cards}</div>'
    elif v['phase'] == 'passing':
        extra = f'<span class="cardsleft">{"passed" if p["has_passed"] else "passing…"}</span>'
    else:
        count = p['cards_left']
        extra = f'<span class="cardsleft">{count} card{"s" if count != 1 else ""}</span>'
    avatar = _avatar(v, index)
    name = esc(p['name'])
    label = 'You' if index == v['my_index'] else name
    bid = f'<span class="player-stat"><span>Bid</span><b>{_bid_value(p)}</b></span>'
    won = ''
    if v['phase'] not in ('werewolf', 'choosing_trump', 'bidding'):
        won = f'<span class="player-stat"><span>Won</span><b>{p["tricks_won"]}</b></span>'
    return (f'<div class="seat"><div class="avwrap">{avatar}{mark}</div><div class="player-label">'
            f'<span class="pname" title="{name}">{label}</span>'
            f'<div class="player-stats">{bid}{won}</div>{extra}</div></div>')


def _trump_html(v: dict) -> str:
    """Show the revealed card beside the current trump suit or selection status."""
    card = v['trump_card']
    revealed = card_html(card, 'sm') if card is not None else ''
    symbol = ''
    if v['phase'] in ('werewolf', 'choosing_trump'):
        status = 'Choosing…'
    elif v['trump']:
        trump = v['trump']
        status = SUIT_LABEL[trump]
        symbol = f'<span class="trump-symbol s-{trump.value}">{suit_emblem(trump)}</span>'
    else:
        status = 'No trump'
    return (f'<div class="trump-display">{revealed}<div class="trump">'
            f'<span class="tl">Trump</span>{symbol}<span class="ts">{status}</span></div></div>')


def _lead_html(v: dict) -> str:
    lead = lead_suit(v['trick']) if v['trick'] else None
    if lead is None:
        return ''
    return f'<span class="chip" title="Suit to follow">{suit_icon(lead)}{SUIT_LABEL[lead]}</span>'


def _seat_vector(v: dict, player: int) -> tuple[float, float]:
    """Direction from the center to the player, with the viewer at the bottom."""
    n = len(v['players'])
    relative = (player - v['my_index']) % n
    angle = math.radians(270 - relative * 360 / n)
    return math.cos(angle), -math.sin(angle)


def _slot_position(v: dict, player: int) -> tuple[float, float]:
    """The played card goes in front of its player's seat."""
    x, y = _seat_vector(v, player)
    column = 29 if x < -.1 else 71 if x > .1 else 50
    row = 25.5 if y < -.1 else 74.5 if y > .1 else 50
    return column, row


def _fan_style(index: int, count: int) -> str:
    side = (2 * index - count + 1) / (count - 1) if count > 1 else 0
    angle = side * min(12, 3 * (count - 1), 96 / count)
    drop = side ** 2 * min(8, 2 * (count - 1))
    return f'--fan-angle:{angle:.2f}deg;--fan-drop:{drop:.1f}px'


def _trick_html(v: dict, paused: bool, seen: set | None = None) -> str:
    """Cards in the center of the table. seen: cards already shown by this browser.
    All others have just been played and fade into their slot."""
    finished = paused and not v['trick'] and bool(v['last_trick'])
    plays: list[Play] = v['last_trick'] if finished else v['trick']
    if not plays:
        if v['phase'] in ('werewolf', 'choosing_trump', 'bidding'):
            return '<span class="hint">Waiting for bids…</span>'
        return ''
    best = trick_winner(plays, v['trump'])
    bombed = trick_bombed(plays)
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
            tag = ''
        note = ''
        if play.card.needs_role_choice:
            note = f'<span class="as">as {"Wizard" if play.as_wizard else "Jester"}</span>'
        x, y = _slot_position(v, play.player)
        enter = ''
        if seen is not None and play.card.id not in seen:
            enter = ' enter'
            seen.add(play.card.id)
        caption = f'<span class="trick-caption">{tag}{note}</span>' if tag or note else ''
        below = ' caption-below' if y <= 50 else ''
        parts.append(f'<div class="tslot{enter}{below}" style="left:{x:.1f}%;top:{y:.1f}%;z-index:{pos + 1}" '
                     f'title="{esc(_name(v, play.player))}">{card_html(play.card, "md", chosen=play.suit)}'
                     f'{caption}</div>')
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


# ------------------------------------------------------------------- The table

def render_table(lobby: Lobby, pid: str, state: dict, refresh_self: Callable[[], None],
                 open_rules: Callable[[], None]) -> None:
    """Renders the table for player pid. state holds data specific to this browser tab."""
    v = lobby.game.view_for(pid)
    paused = lobby.is_paused()
    n, me = len(v['players']), v['my_index']
    others = [(me + k) % n for k in range(1, n)]

    # Did the player receive a Juggler card? Show a brief notification.
    if v['pass_count'] != state.get('seen_pass', v['pass_count']) and v['received'] is not None:
        ui.notify(f'You received {card_name(v["received"])}', type='info', position='top')
    state['seen_pass'] = v['pass_count']
    if cheer_for_cr7(v, state, lobby.game_number):
        ui.run_javascript(SIUUU_JS)

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

    # --- Decisions before and during a round ---
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
    def choice_panel(card: Card, declare: bool = False) -> None:
        def pick(**choice) -> None:
            if declare:
                act('declare', **choice)
            else:
                act('play', card_id=card.id, **choice)

        with ui.element('div').classes('panel'):
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
        can_play = v['phase'] == 'playing' and v['my_turn'] and not decision
        with ui.element('div').classes('hand'), ui.element('div').classes('handrow') \
                .props('role=group aria-label="Your hand" tabindex=0'):
            if v['my_hand'] is None:  # Clairvoyance: own card is hidden
                for _ in range(v['my_hand_size']):
                    element = ui.html(back_html('lg', '?'), sanitize=False).classes('hcard')
                    if can_play and v['playable']:
                        element.classes('playable')
                        element.on('click', partial(act, 'play', card_id=v['playable'][0])).mark('playable')
                return
            cards = sorted(v['my_hand'], key=_hand_order)
            for index, card in enumerate(cards):
                element = ui.html(card_html(card, 'lg'), sanitize=False).classes('hcard') \
                    .props(f'data-card={card.id}').style(_fan_style(index, len(cards)))
                if card.id == state.get('selected'):
                    element.classes('selected')
                if card.id == state.get('pending'):
                    element.classes('picked')
                if v['must_pass']:
                    element.classes('playable')
                    element.on('click', partial(pass_card, card.id)).mark('pass')
                elif can_play:
                    if card.id in v['playable']:
                        element.classes('playable')
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
                if over:
                    button('Play again', lambda: lobby.play_again(pid), marker='play-again')
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
    with ui.element('div').classes('topbar game-topbar'):
        icon_button(ICON_EXIT, 'Leave game', partial(set_state, 'confirm_leave', True)).classes('game-exit')
        ui.html(f'<div class="rinfo"><b>Round {v["round"]} of {v["total_rounds"]}</b>'
                f'<span>{_phase_text(v)}</span></div>', sanitize=False).classes('game-round')
        with ui.element('div').classes('game-topbar-actions'):
            icon_button(ICON_SCORES, 'Scoreboard', partial(set_state, 'scores_open', True), marker='scoreboard')
            icon_button(ICON_INFO, 'Game rules', open_rules, marker='open-game-rules').props('title="Game rules"')

        ui.html(_trump_html(v), sanitize=False).classes('a-trump')
        ui.html(_lead_html(v), sanitize=False).classes('a-lead')

    # Validate remembered card choices when the browser redraws after a turn or timeout.
    phase_decision = {
        'werewolf': werewolf_panel, 'choosing_trump': trump_panel,
        'bidding': bid_panel, 'adjusting': adjust_panel,
    }.get(v['phase']) if v['my_turn'] else None
    decision = phase_decision
    pending = state.get('pending')
    if v['must_declare']:
        state['pending'] = None
        decision = partial(choice_panel, v['trick'][-1].card, declare=True)
    elif pending and v['phase'] == 'playing' and v['my_turn'] and pending in v['playable']:
        decision = partial(choice_panel, next(c for c in v['my_hand'] if c.id == pending))
    else:
        state['pending'] = None

    # Discard stale touch selection before rendering the hand in either position.
    selectable = v['playable'] if (v['phase'] == 'playing' and v['my_turn']) else (
        [c.id for c in v['my_hand'] or []] if v['must_pass'] else [])
    if state.get('selected') not in selectable or decision:
        state['selected'] = None

    board_class = f'board board-{n}-seats'
    if v['clairvoyance']:
        board_class += ' clairvoyance'
    with ui.element('div').classes('table-stage'):
        with ui.element('div').classes('table-field'), \
                ui.element('div').classes(board_class).props('role=region aria-label="Game table"'):
            ui.html('<span></span><span></span><span></span>', sanitize=False) \
                .classes('table-engraving').props('aria-hidden=true')
            for index in others:
                x, y = _seat_vector(v, index)
                side = 'seat-left' if x < -.1 else 'seat-right' if x > .1 else 'seat-north'
                upper = ' seat-upper' if y < -.1 else ''
                ui.html(_seat_html(v, index, lobby), sanitize=False).classes(f'table-seat {side}{upper}') \
                    .style(f'--seat-x:{x:.4f};--seat-y:{y:.4f}')
            ui.html(_seat_html(v, me, lobby), sanitize=False).classes('table-self')
            if not phase_decision:
                with ui.element('div').classes('a-trick'):
                    # On a reload all cards are visible. On later updates only new cards fade in.
                    shown = [p.card.id for p in (v['trick'] or v['last_trick'])]
                    if 'seen_trick' not in state:
                        state['seen_trick'] = set(shown)
                    state['seen_trick'] &= set(shown)
                    ui.html(_trick_html(v, paused, state['seen_trick']), sanitize=False).classes('trick')
        if decision:
            with ui.element('div').classes('table-decision'):
                decision()

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

    ui.html(f'<span class="status{"" if mine else " wait"}">{esc(text)}</span>',
            sanitize=False).classes('statusrow')
    hand()

    pending = state.get('pending')
    if pending and state.get('revealed_pending') != pending:
        ui.context.client.run_javascript(
            "requestAnimationFrame(() => document.querySelector('.handrow .hcard.picked')"
            "?.scrollIntoView({block:'nearest',inline:'nearest'}))")
    state['revealed_pending'] = pending

    if state.get('confirm_leave'):
        leave_overlay()
    elif v['phase'] in ('round_over', 'game_over') and not paused:
        results_overlay()
    elif state.get('scores_open'):
        scores_overlay()
