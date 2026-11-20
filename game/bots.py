"""Simple computer opponents.

The bots get exactly the same view as a human (game.view_for),
so they cannot see anyone else's cards. Their strategy is deliberately simple:
- Bidding: Dragon, Wizards, Shapeshifter, high trumps and 13s count as safe tricks.
- Playing: if the bot still needs tricks, it plays its strongest legal card,
  otherwise the one most likely to lose.
"""
from __future__ import annotations

from .cards import Card, Kind, Suit
from .rules import lead_suit


def _needs_tricks(view: dict) -> bool:
    me = view['players'][view['my_index']]
    return (me['bid'] or 0) > me['tricks_won']


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


def choose_bid(view: dict) -> int:
    """Estimates the tricks and falls back to the nearest allowed number if necessary."""
    wish = _estimate_tricks(view)
    allowed = view['allowed_bids'] or [wish]
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


def choose_card(view: dict) -> tuple[str, Suit | None, bool | None]:
    """Returns (card id, chosen suit, as Wizard?) for the next move."""
    playable = view['playable']
    hand = view['my_hand']
    if hand is None:
        return playable[0], None, None
    cards = [c for c in hand if c.id in playable]
    trump = view['trump']
    wants = _needs_tricks(view)
    if wants:
        card = max(cards, key=lambda c: _win_strength(c, trump))
    else:
        card = min(cards, key=lambda c: _lose_risk(c, trump))

    suit, as_wizard = choose_declaration(view, card, view['trick'])
    return card.id, suit, as_wizard


def choose_declaration(view: dict, card: Card, trick) -> tuple[Suit | None, bool | None]:
    """Choose the suit (Juggler/Cloud) or role (Shapeshifter) for a card."""
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


def choose_pass(view: dict) -> str:
    """Juggler: which card the bot passes to its left neighbour."""
    hand = view['my_hand'] or []
    trump = view['trump']
    if _needs_tricks(view):
        return min(hand, key=lambda c: _win_strength(c, trump)).id  # pass the weakest
    return max(hand, key=lambda c: _lose_risk(c, trump)).id         # pass the most dangerous


def choose_adjustment(view: dict) -> int:
    """Cloud: change the bid so that it is as close as possible to the tricks won."""
    me = view['players'][view['my_index']]
    options = view['adjust_options']
    return min(options, key=lambda change: (abs(me['bid'] + change - me['tricks_won']), -change))
