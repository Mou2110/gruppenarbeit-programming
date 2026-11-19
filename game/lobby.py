"""Lobbies: waiting rooms where players gather and then play a game together.

This file knows nothing about the user interface. It only keeps track of who is in which lobby,
starts the game and lets bots (or absent players) move automatically.
The user interface registers with subscribe() and is notified of every change.
"""
from __future__ import annotations

import pickle
import random
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from . import bots
from .accounts import account_of
from .cards import SPECIAL_KINDS, Kind, Suit
from .engine import Game, GameError, Phase

MIN_PLAYERS, MAX_PLAYERS = 3, 6
NAME_MAX = 16
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # without 0/O and 1/I, which are easy to mix up
BOT_NAMES = ['Marta', 'Joana', 'Tiago', 'Inês', 'Rui', 'Sofia']

BOT_DELAY = 0.9       # seconds between two automatic moves
TRICK_PAUSE = 1.6     # how long a finished trick stays visible to everyone
ABSENT_GRACE = 5.0    # how long someone may be offline (e.g. reloading the page) before they count as "away"


class LobbyError(Exception):
    """An action in the lobby is not possible right now."""


@dataclass
class Member:
    id: str
    name: str
    ready: bool = False
    is_bot: bool = False


@dataclass
class Settings:
    special_cards: list[Kind] = field(default_factory=lambda: list(SPECIAL_KINDS))
    clairvoyance: bool = True       # clairvoyance in round 1
    no_matching_bids: bool = True   # bids must not add up to the number of tricks


CHAT_MAX = 200     # characters per message
CHAT_KEEP = 100    # this many messages are kept in the history
CHAT_GAP = 0.4     # minimum seconds between two messages from one player


@dataclass
class ChatMessage:
    member_id: str
    name: str
    text: str
    at: float          # time (Unix time)
    number: int = 0    # running number in this lobby


def clean_name(name: str) -> str:
    return ' '.join(str(name).split())[:NAME_MAX]


class Lobby:
    def __init__(self, code: str, host_id: str, host_name: str,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.code = code
        self.host_id: str | None = host_id
        self.members = [Member(host_id, clean_name(host_name) or 'Player 1')]
        self.settings = Settings()
        self.game: Game | None = None
        self.clock = clock
        self.pause_until = 0.0
        self.next_auto_at = 0.0
        self.votes: set[str] = set()                 # who pressed "continue" after the round
        self.left: set[str] = set()                  # who left the running game for good (counts as last)
        self.connections: dict[str, int] = {}        # open browser tabs per player
        self.last_seen: dict[str, float] = {}
        self.listeners: dict[object, Callable[[], None]] = {}
        self.chat: list[ChatMessage] = []
        self.chat_count = 0
        self.chat_listeners: dict[object, Callable[[ChatMessage], None]] = {}
        self.last_chat: dict[str, float] = {}
        self.version = 0
        self.created = clock()

    # ------------------------------------------------------------ Basics

    def member(self, member_id: str) -> Member | None:
        return next((m for m in self.members if m.id == member_id), None)

    def humans(self) -> list[Member]:
        return [m for m in self.members if not m.is_bot]

    def is_host(self, member_id: str) -> bool:
        return member_id == self.host_id

    def subscribe(self, key: object, callback: Callable[[], None]) -> None:
        self.listeners[key] = callback

    def unsubscribe(self, key: object) -> None:
        self.listeners.pop(key, None)

    def _changed(self) -> None:
        """Something has changed: let all registered pages redraw."""
        self.version += 1
        for key, callback in list(self.listeners.items()):
            try:
                callback()
            except Exception:  # page no longer exists
                self.listeners.pop(key, None)

    # ------------------------------------------------------------ Saving

    def __getstate__(self) -> dict:
        """What gets saved: everything except open connections, pages and clock times of this server."""
        state = self.__dict__.copy()
        for key in ('clock', 'listeners', 'connections', 'last_seen', 'chat_listeners', 'last_chat'):
            state.pop(key, None)
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        self.clock = time.monotonic
        self.listeners, self.connections, self.last_seen = {}, {}, {}
        self.chat_listeners, self.last_chat = {}, {}
        self.__dict__.setdefault('chat', [])          # lobbies that were saved before the chat existed
        self.__dict__.setdefault('chat_count', len(self.chat))
        self.__dict__.setdefault('left', set())       # lobbies that were saved before leavers were tracked

    def restored(self, clock: Callable[[], float]) -> 'Lobby':
        """After loading: reset the times. Everyone first gets time to reconnect."""
        self.clock = clock
        now = clock()
        self.created = now
        self.pause_until = 0.0
        self.next_auto_at = now + BOT_DELAY
        self.last_seen = {m.id: now for m in self.members}
        return self

    def rebind(self, old_id: str, new_id: str, name: str | None = None) -> bool:
        """A guest logs in: their seat is moved to the account (even in the middle of a game)."""
        member = self.member(old_id)
        if member is None or self.member(new_id) is not None:
            return False
        member.id = new_id
        if name:
            member.name = clean_name(name)
        if self.host_id == old_id:
            self.host_id = new_id
        if self.game is not None:
            for player in self.game.players:
                if player.id == old_id:
                    player.id = new_id
                    if name:
                        player.name = clean_name(name)
        if old_id in self.votes:
            self.votes = (self.votes - {old_id}) | {new_id}
        for table in (self.connections, self.last_seen):
            if old_id in table:
                table[new_id] = table.pop(old_id)
        self._changed()
        return True

    # ------------------------------------------------------------ Chat

    def say(self, member_id: str, text: str) -> ChatMessage | None:
        """Send a chat message. Empty messages are ignored."""
        member = self.member(member_id)
        if member is None or member.is_bot:
            raise LobbyError('Only players at this table can chat.')
        text = ' '.join(str(text).split())[:CHAT_MAX]
        if not text:
            return None
        now = self.clock()
        if now - self.last_chat.get(member_id, -1e9) < CHAT_GAP:
            raise LobbyError('Slow down a little.')
        self.last_chat[member_id] = now
        self.chat_count += 1
        message = ChatMessage(member_id, member.name, text, time.time(), self.chat_count)
        self.chat.append(message)
        del self.chat[:-CHAT_KEEP]
        self.version += 1   # so that the message is saved too
        for key, callback in list(self.chat_listeners.items()):
            try:
                callback(message)
            except Exception:
                self.chat_listeners.pop(key, None)
        return message

    def _require_host(self, member_id: str) -> None:
        if not self.is_host(member_id):
            raise LobbyError('Only the host can do that.')

    def _require_waiting(self) -> None:
        if self.game is not None:
            raise LobbyError('The game has already started.')

    # ------------------------------------------------------------ Connections

    def connect(self, member_id: str) -> None:
        self.connections[member_id] = self.connections.get(member_id, 0) + 1
        self.last_seen[member_id] = self.clock()

    def disconnect(self, member_id: str) -> None:
        self.connections[member_id] = max(0, self.connections.get(member_id, 0) - 1)
        self.last_seen[member_id] = self.clock()

    def is_online(self, member_id: str) -> bool:
        return self.connections.get(member_id, 0) > 0

    def is_absent(self, member_id: str) -> bool:
        """Offline and gone for longer than ABSENT_GRACE. The game then waits for them – no bot takes over."""
        if self.is_online(member_id):
            return False
        return self.clock() - self.last_seen.get(member_id, self.created) > ABSENT_GRACE

    def cards_played(self) -> bool:
        """Is a game running in which at least one card has already been played?"""
        game = self.game
        if game is None or game.phase == Phase.GAME_OVER:
            return False
        return game.round_number > 1 or bool(game.tricks_played) or bool(game.trick)

    def anyone_online(self) -> bool:
        return any(self.is_online(m.id) for m in self.humans())

    def _plays_automatically(self, member_id: str) -> bool:
        member = self.member(member_id)
        # Only real bots move automatically. If someone is away (break, crash), the game waits for them.
        # A bot only takes over a human's seat if they leave the game for good themselves.
        return member is not None and member.is_bot

    # ------------------------------------------------------------ Waiting room

    def join(self, member_id: str, name: str = '') -> Member:
        existing = self.member(member_id)
        if existing:
            return existing
        self._require_waiting()
        if len(self.members) >= MAX_PLAYERS:
            raise LobbyError('This lobby is full.')
        member = Member(member_id, clean_name(name) or f'Player {len(self.members) + 1}')
        self.members.append(member)
        if self.host_id is None:
            self.host_id = member_id
        self._changed()
        return member

    def leave(self, member_id: str) -> None:
        member = self.member(member_id)
        if member is None:
            return
        if self.game is None:
            self.members.remove(member)
        else:
            member.is_bot = True  # during the game a bot takes over the seat
            self.left.add(member_id)  # ... but the result still counts for them, in last place
        if self.is_host(member_id):
            self.host_id = next((m.id for m in self.humans()), None)
        self._changed()

    def rename(self, member_id: str, name: str) -> None:
        member = self.member(member_id)
        name = clean_name(name)
        if member is None or self.game is not None or not name or name == member.name:
            return
        member.name = name
        self._changed()

    def set_ready(self, member_id: str, ready: bool) -> None:
        self._require_waiting()
        member = self.member(member_id)
        if member is None:
            raise LobbyError('You are not in this lobby.')
        member.ready = ready
        self._changed()
        self._maybe_start()

    def add_bot(self, by: str) -> None:
        self._require_host(by)
        self._require_waiting()
        if len(self.members) >= MAX_PLAYERS:
            raise LobbyError('This lobby is full.')
        used = {m.name for m in self.members}
        name = next((n for n in BOT_NAMES if n not in used), f'Bot {len(self.members) + 1}')
        self.members.append(Member(f'bot-{secrets.token_hex(4)}', name, ready=True, is_bot=True))
        self._changed()
        self._maybe_start()

    def remove_bot(self, by: str, bot_id: str) -> None:
        self._require_host(by)
        self._require_waiting()
        member = self.member(bot_id)
        if member is None or not member.is_bot:
            raise LobbyError('That is not a bot.')
        self.members.remove(member)
        self._changed()

    def update_settings(self, by: str, *, special_cards: list[Kind] | None = None,
                        clairvoyance: bool | None = None, no_matching_bids: bool | None = None) -> None:
        """Change the settings (host only). Afterwards everyone has to press "Ready" again."""
        self._require_host(by)
        self._require_waiting()
        if special_cards is not None:
            self.settings.special_cards = [k for k in SPECIAL_KINDS if k in special_cards]
        if clairvoyance is not None:
            self.settings.clairvoyance = clairvoyance
        if no_matching_bids is not None:
            self.settings.no_matching_bids = no_matching_bids
        for member in self.humans():
            member.ready = False
        self._changed()

    def missing_for_start(self) -> str | None:
        """Why the game is not starting yet (or None if everything is ready)."""
        if len(self.members) < MIN_PLAYERS:
            return f'At least {MIN_PLAYERS} players are needed'
        waiting = [m for m in self.members if not m.ready and not m.is_bot]
        if waiting:
            return f'Waiting for {len(waiting)} player{"s" if len(waiting) != 1 else ""} to get ready'
        return None

    def _maybe_start(self) -> None:
        if self.game is None and self.missing_for_start() is None:
            self.start_game()

    def start_game(self) -> None:
        self._require_waiting()
        if self.missing_for_start() is not None:
            raise LobbyError(self.missing_for_start())
        self.game = Game([(m.id, m.name) for m in self.members],
                         special_cards=self.settings.special_cards,
                         clairvoyance=self.settings.clairvoyance,
                         no_matching_bids=self.settings.no_matching_bids,
                         rng=random.Random())
        self.votes = set()
        self.left = set()
        self.pause_until = 0.0
        self.next_auto_at = self.clock() + BOT_DELAY
        self._changed()

    # ------------------------------------------------------------ Game

    def is_paused(self) -> bool:
        return self.clock() < self.pause_until

    def act(self, member_id: str, action: str, **kwargs) -> None:
        """A player makes a move. Invalid moves raise a GameError."""
        game = self.game
        if game is None:
            raise GameError('There is no game running.')
        tricks_before = (game.round_number, len(game.tricks_played))
        if action == 'trump':
            game.choose_trump(member_id, kwargs['suit'])
        elif action == 'bid':
            game.place_bid(member_id, kwargs['bid'])
        elif action == 'play':
            self.pause_until = 0.0  # whoever leads does not have to wait for the pause to end
            game.play_card(member_id, kwargs['card_id'], suit=kwargs.get('suit'), as_wizard=kwargs.get('as_wizard'))
        elif action == 'declare':
            game.declare(member_id, suit=kwargs.get('suit'), as_wizard=kwargs.get('as_wizard'))
        elif action == 'pass':
            game.pass_card(member_id, kwargs['card_id'])
        elif action == 'adjust':
            game.adjust_bid(member_id, kwargs['change'])
        else:
            raise ValueError(f'Unknown action {action}')
        self._after_move(tricks_before)
        self._changed()

    def _after_move(self, tricks_before: tuple[int, int]) -> None:
        game = self.game
        now = self.clock()
        if (game.round_number, len(game.tricks_played)) != tricks_before and game.last_trick:
            self.pause_until = now + TRICK_PAUSE     # briefly show the finished trick
            self.next_auto_at = self.pause_until
        else:
            self.next_auto_at = now + BOT_DELAY

    rematch: set = frozenset()  # who pressed "play again" (class default keeps old saved lobbies working)

    def vote_continue(self, member_id: str) -> None:
        """After a round: once everyone has pressed "continue", the game goes on."""
        if self.game is None or self.game.phase not in (Phase.ROUND_OVER, Phase.GAME_OVER):
            return
        self.votes.add(member_id)
        self._check_votes()
        self._changed()

    def play_again(self, member_id: str) -> None:
        """At the end of a game: "continue" and also be ready for the next game right away."""
        if self.game is None or self.game.phase != Phase.GAME_OVER:
            return
        if not any(m.id == member_id and not m.is_bot for m in self.members):
            return
        self.rematch = self.rematch | {member_id}
        self.vote_continue(member_id)

    def waiting_for_votes(self) -> list[Member]:
        return [m for m in self.members if not self._plays_automatically(m.id) and m.id not in self.votes]

    def _check_votes(self) -> bool:
        game = self.game
        if game is None or game.phase not in (Phase.ROUND_OVER, Phase.GAME_OVER) or self.is_paused():
            return False
        if self.waiting_for_votes():
            return False
        if game.phase == Phase.ROUND_OVER:
            game.next_round()
            self.next_auto_at = self.clock() + BOT_DELAY
        else:
            self.game = None  # back to the waiting room
            for member in self.humans():
                member.ready = member.id in self.rematch
            self.rematch = set()
            self.votes = set()
            self._maybe_start()      # everyone chose "play again": the next game starts right away
            return True
        self.votes = set()
        return True

    def tick(self) -> bool:
        """Called regularly: ends pauses and lets bots or absent players move."""
        game = self.game
        if game is None:
            return False
        now = self.clock()
        changed = False
        if self.pause_until and now >= self.pause_until:
            self.pause_until = 0.0
            changed = True
        if not self.is_paused() and now >= self.next_auto_at and self.anyone_online():
            # If no human is left at all (e.g. all browsers crashed), the game waits
            # instead of being finished by the bots. That way players can rejoin later.
            if self._auto_move():
                changed = True
            elif self._check_votes():
                changed = True
        if changed:
            self._changed()
        return changed

    def _auto_move(self) -> bool:
        """Makes a move for a bot or absent player if it is their turn."""
        game = self.game
        phase = game.phase
        if phase in (Phase.ROUND_OVER, Phase.GAME_OVER):
            return False
        tricks_before = (game.round_number, len(game.tricks_played))
        if phase == Phase.PASSING:
            moved = False
            for player in game.players:
                if game.must_pass(player.id) and self._plays_automatically(player.id):
                    game.pass_card(player.id, bots.choose_pass(game.view_for(player.id)))
                    moved = True
            if moved:
                self._after_move(tricks_before)
            return moved

        player = game.players[game.current]
        if not self._plays_automatically(player.id):
            return False
        view = game.view_for(player.id)
        if phase in (Phase.WEREWOLF, Phase.CHOOSING_TRUMP):
            game.choose_trump(player.id, bots.choose_trump(view))
        elif phase == Phase.BIDDING:
            game.place_bid(player.id, bots.choose_bid(view))
        elif phase == Phase.ADJUSTING:
            game.adjust_bid(player.id, bots.choose_adjustment(view))
        elif game.awaiting_choice is not None:
            suit, as_wizard = bots.declare_played_card(view)
            game.declare(player.id, suit=suit, as_wizard=as_wizard)
        else:
            card_id, suit, as_wizard = bots.choose_card(view)
            game.play_card(player.id, card_id, suit=suit, as_wizard=as_wizard)
        self._after_move(tricks_before)
        return True


class LobbyRegistry:
    """All open lobbies on the server, found by their code."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.lobbies: dict[str, Lobby] = {}
        self.clock = clock
        self.store = None                 # optional: saves game states permanently (game/persistence.py)
        self.saved: dict[str, int] = {}   # which version of each lobby has already been saved
        self.recorded: set[str] = set()   # lobbies whose finished game is already in the history

    def attach_store(self, store) -> None:
        """Connect the database and restore all saved lobbies."""
        self.store = store
        for code, lobby in store.load_lobbies().items():
            if isinstance(lobby, Lobby):
                self.lobbies[code] = lobby.restored(self.clock)
                self.saved[code] = lobby.version
                if lobby.game is not None and lobby.game.phase == Phase.GAME_OVER:
                    self.recorded.add(code)

    def _persist(self) -> None:
        """Save changed lobbies and write finished games to the history."""
        if self.store is None:
            return
        for code, lobby in self.lobbies.items():
            if self.saved.get(code) != lobby.version:
                try:
                    self.store.save_lobby(code, pickle.dumps(lobby))
                    self.saved[code] = lobby.version
                except Exception:
                    pass
            game = lobby.game
            if game is not None and game.phase == Phase.GAME_OVER:
                if code not in self.recorded:
                    self.recorded.add(code)
                    # Players who left keep their account: they are saved in last place.
                    bots_ = {m.id for m in lobby.members if m.is_bot and m.id not in lobby.left}
                    self.store.record_game(code, game.round_number, [
                        {'name': p.name, 'score': p.score, 'bot': p.id in bots_,
                         'account': None if p.id in bots_ else account_of(p.id),
                         'left': p.id in lobby.left,
                         'correct': sum(1 for s in p.round_scores if s > 0)} for p in game.players])
            else:
                self.recorded.discard(code)

    def create(self, host_id: str, host_name: str = '') -> Lobby:
        while True:
            code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(4))
            if code not in self.lobbies:
                break
        lobby = Lobby(code, host_id, host_name, clock=self.clock)
        self.lobbies[code] = lobby
        return lobby

    def get(self, code: str) -> Lobby | None:
        return self.lobbies.get(str(code).strip().upper())

    def lobbies_of(self, member_id: str) -> list[Lobby]:
        """All lobbies in which this player (still personally) has a seat, newest first."""
        def sits_in(lobby: Lobby) -> bool:
            member = lobby.member(member_id)
            return member is not None and not member.is_bot
        return sorted((lobby for lobby in self.lobbies.values() if sits_in(lobby)),
                      key=lambda lobby: lobby.created, reverse=True)

    def games_of(self, member_id: str) -> list[Lobby]:
        """For "Your games": only running games in which at least one card has already been played."""
        return [lobby for lobby in self.lobbies_of(member_id) if lobby.cards_played()]

    def tick_all(self) -> None:
        for code, lobby in list(self.lobbies.items()):
            lobby.tick()
            nobody_online = not any(lobby.is_online(m.id) for m in lobby.humans())
            idle = self.clock() - max(lobby.last_seen.values(), default=lobby.created)
            # Waiting rooms disappear after 30 minutes without players, running games only after a day,
            # so that players can still come back after a crash or a break.
            limit = 30 * 60 if lobby.game is None else 24 * 3600
            if not lobby.humans() or (nobody_online and idle > limit):
                del self.lobbies[code]  # clean up empty or long-abandoned lobbies
                self.saved.pop(code, None)
                if self.store is not None:
                    self.store.delete_lobby(code)
        self._persist()


registry = LobbyRegistry()
