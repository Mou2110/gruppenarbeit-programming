"""The game flow: runs a complete game round by round.

The Game class is the "referee" of the game. Only it changes the game state.
Players (or rather the user interface) call its methods, e.g. place_bid() or
play_card(). If a move is not allowed (wrong player, wrong card, wrong phase),
it raises a GameError and changes nothing.
"""
from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from .cards import SPECIAL_KINDS, Card, Kind, Suit, shuffled_deck
from .rules import (
    Play, dealer_chooses_trump, legal_cards, total_rounds, trick_has_bomb, trick_winner, trump_from_card,
)
from .scoring import round_score


class GameError(Exception):
    """Raised when a move breaks the rules."""


class Phase(str, Enum):
    WEREWOLF = 'werewolf'              # the Werewolf holder swaps it for the trump card and picks trump
    CHOOSING_TRUMP = 'choosing_trump'  # trump card is e.g. a Wizard: the dealer picks trump
    BIDDING = 'bidding'                # everyone bids their tricks in turn
    PLAYING = 'playing'                # tricks are being played
    PASSING = 'passing'                # after a Juggler trick everyone passes one card to the left
    ADJUSTING = 'adjusting'            # Cloud trick won: change the bid by 1 right away
    ROUND_OVER = 'round_over'          # round scored, waiting for the next one
    GAME_OVER = 'game_over'            # last round played


@dataclass
class PlayerState:
    """Everything that belongs to one player."""
    id: str
    name: str
    hand: list[Card] = field(default_factory=list)
    bid: int | None = None
    bid_change: int = 0         # because of the Cloud: -1, 0 or +1
    tricks_won: int = 0
    score: int = 0
    round_scores: list[int] = field(default_factory=list)  # points of every round

    @property
    def final_bid(self) -> int | None:
        """The bid that is scored at the end (including the change caused by the Cloud)."""
        return None if self.bid is None else self.bid + self.bid_change


class Game:
    def __init__(self, players: list[tuple[str, str]], special_cards: Iterable[Kind] = (),
                 clairvoyance: bool = False, no_matching_bids: bool = True,
                 rng: random.Random | None = None) -> None:
        """players: list of (id, name) in clockwise seating order.

        special_cards: which special cards are in play (e.g. all of cards.SPECIAL_KINDS).
        clairvoyance: clairvoyance in round 1 (your own card hidden, everyone else's visible).
            Unlike the rulebook this also works with special cards: the Werewolf then sits out round 1.
            Whoever plays a card with a choice (Shapeshifter, Juggler, Cloud) blind decides
            as soon as it lies face up in the trick (see declare).
        no_matching_bids: the sum of all bids must not equal the number of tricks.
            This gives the last player one bidding option fewer.
        rng: optional random generator so that tests always run the same way.
        """
        ids = [pid for pid, _ in players]
        if len(set(ids)) != len(ids):
            raise ValueError('Every player needs their own id.')
        self.special_cards = tuple(dict.fromkeys(special_cards))
        if any(kind not in SPECIAL_KINDS for kind in self.special_cards):
            raise ValueError('Unknown special card.')

        self.players = [PlayerState(id=pid, name=name) for pid, name in players]
        self.num_rounds = total_rounds(len(self.players))
        self.clairvoyance = clairvoyance
        self.no_matching_bids = no_matching_bids
        self.rng = rng or random.Random()

        self.round_number = 0
        self.dealer = 0               # index of the dealer
        self.phase = Phase.ROUND_OVER
        self.current = 0              # index of the player whose turn it is
        self.trump_card: Card | None = None
        self.trump: Suit | None = None
        self.trick: list[Play] = []                 # the current trick
        self.tricks_played: list[list[Play]] = []   # all finished tricks of this round
        self.last_trick: list[Play] = []            # the most recently finished trick (for display)
        self.last_trick_winner: int | None = None   # who got it (None with a Bomb)
        self.last_trick_leader: int | None = None   # who leads the next trick
        self.last_trick_bombed = False
        self.werewolf_holder: int | None = None     # who held the Werewolf this round
        self.cloud_owner: int | None = None         # whose tricks contain the Cloud
        self.passes: dict[int, Card] = {}           # Juggler: cards selected for passing
        self.received: dict[int, Card] = {}         # Juggler: which card everyone received
        self.pass_count = 0                         # how often cards have been passed (for display)
        self._next_leader = 0
        self.awaiting_choice: int | None = None     # clairvoyance: player who still has to choose for their card

        self._start_round()

    # ------------------------------------------------------------------ Helpers

    def _index_of(self, player_id: str) -> int:
        for i, p in enumerate(self.players):
            if p.id == player_id:
                return i
        raise GameError(f'Unknown player: {player_id}')

    def _next(self, index: int) -> int:
        """The next seat clockwise (= left neighbour)."""
        return (index + 1) % len(self.players)

    def _require_turn(self, player_id: str, phase: Phase) -> int:
        """Checks that the phase is right and that it is this player's turn. Returns their index."""
        if self.phase != phase:
            raise GameError(f'That is not possible right now (phase: {self.phase.value}).')
        index = self._index_of(player_id)
        if index != self.current:
            raise GameError("It's not your turn.")
        return index

    # ------------------------------------------------------------- Round flow

    def _start_round(self) -> None:
        """Deals the cards for the next round and turns up the trump card."""
        self.round_number += 1
        specials = self.special_cards
        if self.is_clairvoyance_round():
            # Clairvoyance: you could not see your own Werewolf, so it sits out round 1.
            specials = tuple(k for k in specials if k != Kind.WEREWOLF)
        deck = shuffled_deck(self.rng, specials)
        for p in self.players:
            p.hand, p.bid, p.bid_change, p.tricks_won = [], None, 0, 0

        # Dealing starts left of the dealer, one card at a time around the table.
        seat = self._next(self.dealer)
        for _ in range(self.round_number * len(self.players)):
            self.players[seat].hand.append(deck.pop())
            seat = self._next(seat)

        # The next card decides trump (without special cards none is left in the last round).
        self.trump_card = deck.pop() if deck else None
        self.trump = trump_from_card(self.trump_card)
        self.trick, self.tricks_played, self.last_trick = [], [], []
        self.last_trick_winner = self.last_trick_leader = None
        self.last_trick_bombed = False
        self.cloud_owner = None
        self.passes, self.received = {}, {}

        holder = next((i for i, p in enumerate(self.players)
                       if any(c.kind == Kind.WEREWOLF for c in p.hand)), None)
        self.werewolf_holder = holder
        if holder is not None:
            if self.trump_card is None:  # with special cards there is always a card left over
                raise RuntimeError('Werewolf without a trump card – this must not happen.')
            # The Werewolf comes first: its holder swaps and decides trump.
            self.phase = Phase.WEREWOLF
            self.current = holder
        elif dealer_chooses_trump(self.trump_card):
            self.phase = Phase.CHOOSING_TRUMP
            self.current = self.dealer
        else:
            self.phase = Phase.BIDDING
            self.current = self._next(self.dealer)

    def choose_trump(self, player_id: str, suit: Suit | None) -> None:
        """Decide trump.

        - Werewolf phase: the holder swaps the Werewolf for the turned-up trump card
          and picks a suit or "no trump" (suit=None).
        - Otherwise the dealer picks a suit, e.g. because a Wizard was turned up.
        """
        if self.phase == Phase.WEREWOLF:
            index = self._require_turn(player_id, Phase.WEREWOLF)
            player = self.players[index]
            wolf = next(c for c in player.hand if c.kind == Kind.WEREWOLF)
            player.hand.remove(wolf)
            player.hand.append(self.trump_card)
            self.trump_card = wolf
            self.trump = suit
        else:
            self._require_turn(player_id, Phase.CHOOSING_TRUMP)
            if suit is None:
                raise GameError('Please choose a trump suit.')
            self.trump = suit
        self.phase = Phase.BIDDING
        self.current = self._next(self.dealer)

    def forbidden_bid(self) -> int | None:
        """The bid the current player is NOT allowed to make (or None).

        Only the last player of a round has a forbidden number: exactly the one that
        would make the sum of all bids equal the number of tricks.
        """
        if not self.no_matching_bids or self.phase != Phase.BIDDING:
            return None
        others = [p.bid for i, p in enumerate(self.players) if i != self.current]
        if any(b is None for b in others):
            return None  # other players still bid after this one
        forbidden = self.round_number - sum(others)
        return forbidden if 0 <= forbidden <= self.round_number else None

    def allowed_bids(self) -> list[int]:
        """All bids the current player is allowed to make."""
        forbidden = self.forbidden_bid()
        return [b for b in range(self.round_number + 1) if b != forbidden]

    def place_bid(self, player_id: str, bid: int) -> None:
        """A player says how many tricks they will take."""
        index = self._require_turn(player_id, Phase.BIDDING)
        if not 0 <= bid <= self.round_number:
            raise GameError(f'The bid must be between 0 and {self.round_number}.')
        if bid == self.forbidden_bid():
            raise GameError(f'{bid} is not allowed: the bids must not add up to {self.round_number}.')
        self.players[index].bid = bid

        if all(p.bid is not None for p in self.players):
            # Everyone has bid: the dealer's left neighbour leads the first trick.
            self.phase = Phase.PLAYING
            self.current = self._next(self.dealer)
        else:
            self.current = self._next(index)

    def play_card(self, player_id: str, card_id: str, suit: Suit | None = None,
                  as_wizard: bool | None = None) -> None:
        """A player puts a card into the current trick.

        suit: suit for the Juggler or Cloud (required for these cards).
        as_wizard: role for the Shapeshifter, True = Wizard, False = Jester (required).
        """
        index = self._require_turn(player_id, Phase.PLAYING)
        if self.awaiting_choice is not None:
            raise GameError('A choice has to be made for the revealed card first.')
        player = self.players[index]
        card = next((c for c in player.hand if c.id == card_id), None)
        if card is None:
            raise GameError("You don't have that card in your hand.")
        if card not in legal_cards(player.hand, self.trick):
            raise GameError('You have to follow the lead suit.')

        blind = self.is_clairvoyance_round() and suit is None and as_wizard is None
        if blind and (card.needs_suit_choice or card.needs_role_choice):
            # Clairvoyance: the card is revealed first, then the player chooses (see declare).
            player.hand.remove(card)
            self.trick.append(Play(index, card))
            self.awaiting_choice = index
            return
        if card.needs_suit_choice:
            if suit is None:
                raise GameError(f'You have to choose a suit for the {card}.')
            play = Play(index, card, suit=suit)
        elif card.needs_role_choice:
            if as_wizard is None:
                raise GameError('Should the Shapeshifter be a Wizard or a Jester?')
            play = Play(index, card, as_wizard=bool(as_wizard))
        else:
            play = Play(index, card)

        player.hand.remove(card)
        self.trick.append(play)
        if len(self.trick) < len(self.players):
            self.current = self._next(index)
            return
        self._finish_trick()

    def declare(self, player_id: str, suit: Suit | None = None, as_wizard: bool | None = None) -> None:
        """Clairvoyance: after the card is revealed the player picks a suit (Juggler/Cloud) or role (Shapeshifter)."""
        index = self._require_turn(player_id, Phase.PLAYING)
        if self.awaiting_choice != index:
            raise GameError("You don't have to choose anything right now.")
        play = self.trick[-1]
        if play.card.needs_suit_choice:
            if suit is None:
                raise GameError(f'You have to choose a suit for the {play.card}.')
            self.trick[-1] = Play(index, play.card, suit=suit)
        else:
            if as_wizard is None:
                raise GameError('Should the Shapeshifter be a Wizard or a Jester?')
            self.trick[-1] = Play(index, play.card, as_wizard=bool(as_wizard))
        self.awaiting_choice = None
        if len(self.trick) < len(self.players):
            self.current = self._next(index)
        else:
            self._finish_trick()

    def _finish_trick(self) -> None:
        """A trick is complete: determine the winner and what happens next."""
        plays = self.trick
        leader = plays[trick_winner(plays, self.trump)].player   # wins (or would have won)
        bombed = trick_has_bomb(plays)
        cloud_won = False
        if not bombed:
            self.players[leader].tricks_won += 1
            if any(p.card.kind == Kind.CLOUD for p in plays):
                self.cloud_owner = leader
                cloud_won = True
        # With a Bomb the trick belongs to nobody, but whoever would have won leads next.
        self.tricks_played.append(plays)
        self.last_trick, self.last_trick_leader = plays, leader
        self.last_trick_winner = None if bombed else leader
        self.last_trick_bombed = bombed
        self.trick = []

        if cloud_won:
            # House rule: whoever wins the trick with the Cloud changes their bid by 1 RIGHT AWAY
            # (the rulebook says at the end of the round). From 0 only +1 is possible, which happens automatically.
            owner = self.players[leader]
            if owner.bid == 0:
                owner.bid_change = 1
            else:
                self.phase = Phase.ADJUSTING
                self.current = leader
                return
        self._continue_after_trick()

    def _continue_after_trick(self) -> None:
        """What happens after a finished trick: scoring, passing cards or the next trick."""
        plays, leader = self.last_trick, self.last_trick_leader
        if not self.players[leader].hand:  # all hands are empty: the round is over
            self._score_round()
        elif any(p.card.kind == Kind.JUGGLER for p in plays):
            # Juggler: everyone passes one card to the left at the same time (not after the last trick).
            self.phase = Phase.PASSING
            self.passes = {}
            self._next_leader = leader
            self.current = leader
        else:
            self.phase = Phase.PLAYING
            self.current = leader

    def must_pass(self, player_id: str) -> bool:
        """True if this player still has to choose a card in the Juggler phase."""
        return self.phase == Phase.PASSING and self._index_of(player_id) not in self.passes

    def pass_card(self, player_id: str, card_id: str) -> None:
        """Juggler: a player chooses the card they pass to their left neighbour.

        Only when everyone has chosen are the cards passed, all at the same time.
        """
        if self.phase != Phase.PASSING:
            raise GameError('No cards are being passed right now.')
        index = self._index_of(player_id)
        if index in self.passes:
            raise GameError('You have already chosen a card.')
        card = next((c for c in self.players[index].hand if c.id == card_id), None)
        if card is None:
            raise GameError("You don't have that card in your hand.")
        self.passes[index] = card
        if len(self.passes) < len(self.players):
            return

        for i, passed in self.passes.items():
            self.players[i].hand.remove(passed)
        self.received = {}
        for i, passed in self.passes.items():
            target = self._next(i)
            self.players[target].hand.append(passed)
            self.received[target] = passed
        self.passes = {}
        self.pass_count += 1
        self.phase = Phase.PLAYING
        self.current = self._next_leader

    def adjust_options(self) -> list[int]:
        """Cloud: by how much the owner can change their bid."""
        if self.phase != Phase.ADJUSTING:
            return []
        bid = self.players[self.current].bid
        return [-1, 1] if bid > 0 else [1]

    def adjust_bid(self, player_id: str, change: int) -> None:
        """Cloud: the winner of the Cloud trick changes their bid by -1 or +1, then the game goes on."""
        index = self._require_turn(player_id, Phase.ADJUSTING)
        if change not in self.adjust_options():
            raise GameError('The bid can only be changed by 1 up or down (not below 0).')
        self.players[index].bid_change = change
        self._continue_after_trick()

    def _score_round(self) -> None:
        """Scores the round and adds up the points."""
        for p in self.players:
            points = round_score(p.final_bid, p.tricks_won)
            p.round_scores.append(points)
            p.score += points
        self.phase = Phase.GAME_OVER if self.round_number == self.num_rounds else Phase.ROUND_OVER

    def next_round(self) -> None:
        """Starts the next round after the scores have been shown."""
        if self.phase != Phase.ROUND_OVER:
            raise GameError('The round is not over yet.')
        self.dealer = self._next(self.dealer)
        self._start_round()

    # ------------------------------------------------------------------ View

    def is_clairvoyance_round(self) -> bool:
        return self.clairvoyance and self.round_number == 1

    def view_for(self, player_id: str) -> dict:
        """What a specific player is allowed to see.

        Essential for multiplayer: the user interface only ever gets this view,
        never the full game state. That way nobody can see the others' cards.
        In the clairvoyance round it is the other way round: your own card is hidden,
        everyone else's is visible.
        """
        me = self._index_of(player_id)
        clairvoyant = self.is_clairvoyance_round()

        players = []
        for i, p in enumerate(self.players):
            show_hand = (i != me) if clairvoyant else False
            players.append({
                'id': p.id,
                'name': p.name,
                'bid': p.bid,
                'bid_change': p.bid_change,
                'tricks_won': p.tricks_won,
                'score': p.score,
                'cards_left': len(p.hand),
                'round_scores': list(p.round_scores),
                'visible_hand': list(p.hand) if show_hand else None,
                'has_passed': i in self.passes,
            })

        my_hand = self.players[me].hand
        my_turn = self.current == me and self.phase not in (Phase.PASSING, Phase.ROUND_OVER, Phase.GAME_OVER)
        playable: list[str] = []
        if my_turn and self.phase == Phase.PLAYING and self.awaiting_choice is None:
            playable = [c.id for c in legal_cards(my_hand, self.trick)]

        return {
            'round': self.round_number,
            'total_rounds': self.num_rounds,
            'phase': self.phase.value,
            'dealer': self.dealer,
            'current': self.current,
            'my_index': me,
            'my_turn': my_turn,
            'clairvoyance': clairvoyant,
            'special_cards': list(self.special_cards),
            'my_hand': None if clairvoyant else list(my_hand),  # None = hidden
            'my_hand_size': len(my_hand),
            'playable': playable,
            'allowed_bids': self.allowed_bids() if my_turn and self.phase == Phase.BIDDING else [],
            'forbidden_bid': self.forbidden_bid() if my_turn else None,
            'adjust_options': self.adjust_options() if my_turn else [],
            'must_pass': self.must_pass(player_id),
            'must_declare': self.awaiting_choice == me,
            'awaiting_choice': self.awaiting_choice,
            'pass_target': self._next(me),
            'pass_count': self.pass_count,
            'received': self.received.get(me),
            'trump_card': self.trump_card,
            'trump': self.trump,
            'werewolf_holder': self.werewolf_holder,
            'cloud_owner': self.cloud_owner,
            'trick': list(self.trick),
            'last_trick': list(self.last_trick),
            'last_trick_winner': self.last_trick_winner,
            'last_trick_leader': self.last_trick_leader,
            'last_trick_bombed': self.last_trick_bombed,
            'players': players,
        }
