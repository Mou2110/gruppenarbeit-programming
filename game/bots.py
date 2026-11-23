"""Simple computer opponents.

The bots get exactly the same view as a human (game.view_for),
so they cannot see anyone else's cards. Their strategy is deliberately simple:
- Bidding: Dragon, Wizards, Shapeshifter, high trumps and 13s count as safe tricks.
- Playing: if the bot still needs tricks, it plays a card that wins (number cards before Wizards and the
  Dragon) and keeps its strong cards when it cannot win anyway; when it leads, a sure number card comes
  before a Wizard or Dragon. If it needs no more tricks, it plays the card most likely to lose.

Three levels, chosen when a bot is added (see LEVELS):
- normal:   the strategy above, only looks at its own bid.
- spiteful: like normal while its own bid can still be made. Once it is lost, it works against the
            best other player (the leader, or the closest chaser if the bot leads): it takes tricks
            the target needs and leaves tricks to a target who already has enough.
- ruthless: spiteful, plus: plays its cards more cleverly (wins with the cheapest card that is enough,
            gets rid of dangerous cards that still lose, keeps its Jesters), bombs a trick the target
            needs, gives the target the Cloud when they need exactly one more trick, passes the target
            bad cards with the Juggler, and as last bidder steers the round to "over" or "under"
            against the target.
Bots only use what a human could see as well (no card counting over earlier tricks).
"""
from __future__ import annotations

from .cards import Card, Kind, Suit
from .rules import Play, lead_suit, trick_has_bomb, trick_winner

LEVELS = ('normal', 'spiteful', 'ruthless')
LEVEL_NAMES = {'normal': 'Normal', 'spiteful': 'Spiteful', 'ruthless': 'Ruthless'}   # shown in the app


def _needs_tricks(view: dict) -> bool:
    """Does the bot still need tricks? Counts a bid changed by the Cloud as well."""
    return _missing(view['players'][view['my_index']]) > 0


def _win_strength(card: Card, trump: Suit | None) -> float:
    """How well a card wins a trick (higher = better)."""
    if card.kind == Kind.CR7:
        return 300
    if card.kind == Kind.DRAGON:
        return 200
    if card.kind in (Kind.WIZARD, Kind.SHAPESHIFTER):
        return 100
    if card.kind in (Kind.JUGGLER, Kind.CLOUD):
        return (7.5 if card.kind == Kind.JUGGLER else 9.75) + (50 if trump else 0)
    if card.is_number:
        return card.value + (50 if card.suit == trump else 0)
    return {Kind.JESTER: 0, Kind.FAIRY: -1, Kind.BOMB: -2}.get(card.kind, 0)


def _lose_risk(card: Card, trump: Suit | None) -> float:
    """How likely a card is to win a trick you do NOT want (lower = safer)."""
    if card.kind == Kind.BOMB:
        return -3   # nobody gets the trick
    if card.kind == Kind.FAIRY:
        return -2
    if card.kind in (Kind.JESTER, Kind.SHAPESHIFTER):
        return -1   # the Shapeshifter is then played as a Jester
    if card.kind in (Kind.JUGGLER, Kind.CLOUD):
        return 1    # played in a suit that does not win
    return _win_strength(card, trump)


def _most_common_suit(hand: list[Card]) -> Suit | None:
    counts = {suit: 0 for suit in Suit}
    for card in hand:
        if card.is_number:
            counts[card.suit] += 1
    best = max(Suit, key=lambda suit: counts[suit])
    return best if counts[best] else None


def choose_trump(view: dict) -> Suit | None:
    """Choose trump: the suit the bot holds the most cards of.

    As the Werewolf holder it may also choose "no trump" (None) if it has no suit cards.
    As the dealer it always has to pick a suit.
    """
    best = _most_common_suit(view['my_hand'] or [])
    if best is None and view['phase'] == 'choosing_trump':
        return Suit.SEA
    return best


def choose_bid(view: dict, level: str = 'normal') -> int:
    """Estimates the tricks and falls back to the nearest allowed number if necessary.

    Ruthless, as the last bidder, breaks ties (and may go one away from its estimate) so that the
    round becomes "over" (more tricks bid than exist) if the target bid tricks, else "under".
    """
    wish = _estimate_tricks(view)
    allowed = view['allowed_bids'] or [wish]
    others = [p for i, p in enumerate(view['players']) if i != view['my_index']]
    if level == 'ruthless' and view['my_hand'] is not None and all(p['bid'] is not None for p in others):
        target = view['players'][_target(view)]
        want_over = target['bid'] > 0
        bid_so_far = sum(p['bid'] for p in others)
        near = [bid for bid in allowed if abs(bid - wish) <= 1] or allowed
        return min(near, key=lambda bid: ((bid_so_far + bid > view['round']) != want_over, abs(bid - wish), bid))
    return min(allowed, key=lambda bid: (abs(bid - wish), bid))


def _estimate_tricks(view: dict) -> int:
    hand = view['my_hand']
    if hand is None:
        # Clairvoyance round: your own card is unknown -> bid a careful 0.
        return 0
    trump = view['trump']
    sure = 0
    for card in hand:
        if card.kind in (Kind.CR7, Kind.DRAGON, Kind.WIZARD, Kind.SHAPESHIFTER):
            sure += 1
        elif card.is_number and trump is not None and card.suit == trump and card.value >= 10:
            sure += 1
        elif card.is_number and card.value == 13:
            sure += 1
    return min(sure, view['round'])


def choose_card(view: dict, level: str = 'normal') -> tuple[str, Suit | None, bool | None]:
    """Returns (card id, chosen suit, as Wizard?) for the next move."""
    playable = view['playable']
    hand = view['my_hand']
    if hand is None:
        return playable[0], None, None
    cards = [c for c in hand if c.id in playable]
    wants = _needs_tricks(view)
    if level in ('spiteful', 'ruthless'):
        spite = _spite_wants(view)
        if spite is not None:
            wants = spite
    card = _ruthless_card(view, cards, wants) if level == 'ruthless' and view['trick'] else None
    if card is None:
        card = _normal_card(view, cards, wants, smart=level == 'ruthless')

    suit, as_wizard = choose_declaration(view, card, view['trick'], wants)
    return card.id, suit, as_wizard


def _is_sure_number(card: Card, trump: Suit | None) -> bool:
    """A number card that usually wins: a 13, or a high trump."""
    return card.is_number and (card.value == 13 or (trump is not None and card.suit == trump and card.value >= 10))


def _normal_card(view: dict, cards: list[Card], wants: bool, smart: bool = False) -> Card:
    """The card a bot plays (all levels, unless Ruthless found something better).

    Every level avoids wasting cards (play-testing: bots threw their special cards in the first tricks,
    and a second Wizard onto a trick that a Wizard already wins): it never throws a card into a trick
    it cannot win, and it uses number cards before Wizards and the Dragon.
    smart (Ruthless only) plays more cleverly: it wins with the cheapest card that is enough, gets rid of
    its most dangerous card that still loses, and keeps its Jesters for later.
    """
    trump, me = view['trump'], view['my_index']
    strength = lambda c: _win_strength(c, trump)            # noqa: E731
    if view['trick']:
        winners = [c for c in cards if _winner_after(view, c, wants) == me]
        if wants:
            if winners:
                if smart:
                    return min(winners, key=strength)        # win, but as cheaply as possible
                numbers = [c for c in winners if c.is_number]
                if numbers:
                    return max(numbers, key=strength)        # the strongest number card that wins
                return min(winners, key=strength)            # else the weakest special card that is enough
            # Cannot win this trick anyway: throw the weakest card, number cards before special cards.
            return min(cards, key=lambda c: (not c.is_number, strength(c)))
        losers = [c for c in cards if c not in winners and c.kind != Kind.FAIRY]   # a later Dragon makes the Fairy win
        if smart and losers:
            return max(losers, key=strength)                 # get rid of the most dangerous card that still loses
        if losers:
            # A card that loses this trick anyway: a number card first, keep the Jester and friends for later.
            return min(losers, key=lambda c: (not c.is_number, _lose_risk(c, trump)))
        return min(cards, key=lambda c: _lose_risk(c, trump))
    if wants:
        sure = [c for c in cards if _is_sure_number(c, trump)]
        return max(sure or cards, key=strength)             # lead a sure number card before a Wizard or Dragon
    if smart:
        return min(cards, key=lambda c: (not c.is_number, _lose_risk(c, trump)))   # keep the Jester for later
    return min(cards, key=lambda c: _lose_risk(c, trump))


# ---------------------------------------------------------------- Spiteful and Ruthless

def _missing(player: dict) -> int:
    """Tricks a player still needs for their bid (negative = already too many)."""
    return (player['bid'] or 0) + (player.get('bid_change') or 0) - player['tricks_won']


def _can_still_make(player: dict, cards_left: int) -> bool:
    return 0 <= _missing(player) <= cards_left


def _target(view: dict) -> int:
    """Seat of the player to work against: the best other player by score."""
    me = view['my_index']
    others = [i for i in range(len(view['players'])) if i != me]
    return max(others, key=lambda i: view['players'][i]['score'])


def _winner_after(view: dict, card: Card | None, wants: bool) -> int | None:
    """Seat that would win the trick so far (plus this card). None = nobody (Bomb) or empty trick."""
    plays = list(view['trick'])
    if card is not None:
        suit, as_wizard = choose_declaration(view, card, plays, wants)
        plays.append(Play(player=view['my_index'], card=card, suit=suit, as_wizard=as_wizard))
    if not plays or trick_has_bomb(plays):
        return None
    return plays[trick_winner(plays, view['trump'])].player


def _spite_wants(view: dict) -> bool | None:
    """Spiteful: once its own bid is lost, does the bot want this trick to hurt the target?

    None = no reason for spite, play normally.
    """
    players = view['players']
    if _can_still_make(players[view['my_index']], view['my_hand_size']):
        return None
    t = _target(view)
    target = players[t]
    if not _can_still_make(target, target['cards_left']):
        return None                                   # the target has already missed their bid
    if any(p.player == t for p in view['trick']) and _winner_after(view, None, False) != t:
        return None                                   # the target has already lost this trick
    return _missing(target) > 0                       # take tricks they need, leave tricks they do not


def _ruthless_card(view: dict, cards: list[Card], wants: bool) -> Card | None:
    """Ruthless: a card for a trick that has already been started, or None for the normal choice."""
    me, trump = view['my_index'], view['trump']
    t = _target(view)
    target = view['players'][t]
    target_alive = _can_still_make(target, target['cards_left'])
    winners = [c for c in cards if _winner_after(view, c, wants) == me]

    if target_alive and _winner_after(view, None, wants) == t and (not wants or not winners):
        # The target is winning this trick and I do not want it (or cannot get it) anyway.
        bomb = next((c for c in cards if c.kind == Kind.BOMB), None)
        if bomb is not None and _missing(target) > 0:
            return bomb                               # nobody gets the trick they need
        cloud = next((c for c in cards if c.kind == Kind.CLOUD), None)
        if cloud is not None and _missing(target) == 1 and _winner_after(view, cloud, wants) == t:
            return cloud                              # they reach their bid, then must change it by one

    if wants:
        if winners and len(view['trick']) == len(view['players']) - 1:
            return min(winners, key=lambda c: _win_strength(c, trump))   # last to play: win as cheaply as possible
        return None
    losers = [c for c in cards if c not in winners and c.kind != Kind.FAIRY]   # a later Dragon makes the Fairy win
    if losers:
        return max(losers, key=lambda c: _win_strength(c, trump))    # get rid of a dangerous card safely
    return None


def choose_declaration(view: dict, card: Card, trick, wants: bool | None = None) -> tuple[Suit | None, bool | None]:
    """Choose the suit (Juggler/Cloud) or role (Shapeshifter) for a card.

    wants: does the bot want the trick? None = it wants it if it still needs tricks.
    """
    if wants is None:
        wants = _needs_tricks(view)
    trump = view['trump']
    suit = as_wizard = None
    if card.needs_role_choice:
        as_wizard = wants
    if card.needs_suit_choice:
        lead = lead_suit(trick)
        if wants:
            suit = trump or lead or _most_common_suit(view['my_hand'] or []) or Suit.SEA
        else:
            # A suit that is neither trump nor the lead suit can (almost) never win.
            suit = next((s for s in Suit if s not in (trump, lead)), Suit.SEA)
    return suit, as_wizard


def declare_played_card(view: dict) -> tuple[Suit | None, bool | None]:
    """Clairvoyance: choose for your own card that was just revealed."""
    trick = view['trick']
    return choose_declaration(view, trick[-1].card, trick[:-1])


def choose_pass(view: dict, level: str = 'normal') -> str:
    """Juggler: which card the bot passes to its left neighbour.

    Ruthless: if the left neighbour is the target, it gets a sure winner when it already has
    enough tricks, and the weakest card when it still needs tricks.
    """
    hand = view['my_hand'] or []
    trump = view['trump']
    if level == 'ruthless' and hand and view['pass_target'] == _target(view):
        target = view['players'][view['pass_target']]
        if _missing(target) == 0:
            return max(hand, key=lambda c: _win_strength(c, trump)).id
        if _missing(target) > 0:
            return min(hand, key=lambda c: _win_strength(c, trump)).id
    if _needs_tricks(view):
        return min(hand, key=lambda c: _win_strength(c, trump)).id  # pass the weakest
    return max(hand, key=lambda c: _lose_risk(c, trump)).id         # pass the most dangerous


def choose_adjustment(view: dict) -> int:
    """Cloud: change the bid so that it is as close as possible to the tricks won."""
    me = view['players'][view['my_index']]
    options = view['adjust_options']
    return min(options, key=lambda change: (abs(me['bid'] + change - me['tricks_won']), -change))
