"""The rules of the game: number of rounds, trump, allowed cards and who wins a trick.

All functions here are "pure": they receive cards and return a result without
storing anything. This makes them easy to test.

Based on the rulebook of the Wizard anniversary edition (25 years) including special cards.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .cards import SPECIAL_VALUES, Card, Kind, Suit

# How a card behaves when it is led (see rulebook):
# - Like a Wizard: afterwards everyone may play anything.
WIZARD_LIKE = (Kind.WIZARD, Kind.DRAGON, Kind.CR7)
# - Like a Jester: the next card decides.
JESTER_LIKE = (Kind.JESTER, Kind.FAIRY, Kind.BOMB)
# - Cards with value and suit: their suit must be followed.
VALUE_KINDS = (Kind.NUMBER, Kind.JUGGLER, Kind.CLOUD)

# Turned up as the trump card: for these cards the dealer chooses the trump suit.
DEALER_CHOOSES = (Kind.WIZARD, Kind.SHAPESHIFTER, Kind.DRAGON, Kind.WEREWOLF, Kind.JUGGLER, Kind.CLOUD, Kind.CR7)


@dataclass(frozen=True)
class Play:
    """A card played into a trick – together with the choice made when playing it."""
    player: int                    # seat of the player who played the card
    card: Card
    suit: Suit | None = None       # chosen suit for Juggler and Cloud
    as_wizard: bool | None = None  # chosen role for the Shapeshifter (True = Wizard, False = Jester)

    @property
    def acts_as(self) -> Kind:
        """What the card counts as in the trick (the Shapeshifter becomes a Wizard or a Jester)."""
        if self.card.kind == Kind.SHAPESHIFTER:
            return Kind.WIZARD if self.as_wizard else Kind.JESTER
        return self.card.kind

    @property
    def effective_suit(self) -> Suit | None:
        if self.card.is_number:
            return self.card.suit
        if self.card.kind in SPECIAL_VALUES:
            return self.suit
        return None

    @property
    def value(self) -> float | None:
        if self.card.is_number:
            return self.card.value
        return SPECIAL_VALUES.get(self.card.kind)


def _as_plays(trick: Sequence[Play | Card]) -> list[Play]:
    """Allows calling the rules with a plain list of cards as well (handy for tests)."""
    return [item if isinstance(item, Play) else Play(player=i, card=item) for i, item in enumerate(trick)]


def total_rounds(num_players: int, deck_size: int = 60) -> int:
    """How many rounds are played: as many as it takes to deal out the 60 base cards.

    Example: 4 players -> 60 // 4 = 15 rounds. With special cards the number of rounds stays the same;
    according to the rulebook this leaves a card for trump even in the last round.
    """
    if not 3 <= num_players <= 6:
        raise ValueError('Only 3 to 6 people can play.')
    return deck_size // num_players


def trump_from_card(card: Card | None) -> Suit | None:
    """Which suit is trump when this card is turned up.

    - Number card -> its suit is trump
    - Jester, Fairy, Bomb or no card (last round without special cards) -> no trump
    - Wizard and most special cards -> the dealer chooses (see dealer_chooses_trump)
    """
    if card is not None and card.is_number:
        return card.suit
    return None


def dealer_chooses_trump(card: Card | None) -> bool:
    """True if the dealer has to choose the trump suit."""
    return card is not None and card.kind in DEALER_CHOOSES


def lead_suit(trick: Sequence[Play | Card]) -> Suit | None:
    """The suit that has to be followed in this trick.

    - Jester-like cards at the start (Jester, Fairy, Bomb, Shapeshifter as Jester) do not count;
      the first other card decides.
    - If that is a card with a suit (number card, Juggler, Cloud), this suit must be followed.
    - If it is a Wizard, a Shapeshifter as Wizard or the Dragon, everyone may play anything -> None.
    """
    for play in _as_plays(trick):
        kind = play.acts_as
        if kind in JESTER_LIKE:
            continue
        if kind in VALUE_KINDS:
            return play.effective_suit
        return None
    return None


def legal_cards(hand: list[Card], trick: Sequence[Play | Card]) -> list[Card]:
    """All cards from the hand that may be played right now.

    Whoever holds a number card of the lead suit must follow suit. Wizards, Jesters and all
    special cards may still always be played. The Werewolf is never played
    (it is swapped for the trump card before bidding).
    """
    hand = [c for c in hand if c.kind != Kind.WEREWOLF]
    required = lead_suit(trick)
    if required is None:
        return list(hand)
    if not any(c.is_number and c.suit == required for c in hand):
        return list(hand)
    return [c for c in hand if not c.is_number or c.suit == required]


def trick_winner(trick: Sequence[Play | Card], trump: Suit | None) -> int:
    """Position (0, 1, 2 ...) of the card that wins the trick – or, with a Bomb, WOULD have won it.

    Order of checks:
    1. Dragon in the trick: it wins – unless the Fairy is in there too, then the Fairy wins.
    2. Otherwise the first Wizard played wins (including a Shapeshifter played as Wizard).
    3. Otherwise the highest trump card (Juggler counts 7½, Cloud 9¾ in their chosen suit).
    4. Otherwise the highest card of the lead suit.
    5. If only Jester-like cards are in the trick, the first Jester wins.
       (The Fairy loses to every Jester, the Bomb has no value.)
    """
    plays = _as_plays(trick)
    if not plays:
        raise ValueError('An empty trick has no winner.')
    kinds = [p.acts_as for p in plays]

    if Kind.CR7 in kinds:              # our bonus card beats everything (with a Bomb nobody gets the trick)
        return kinds.index(Kind.CR7)

    if Kind.DRAGON in kinds:
        if Kind.FAIRY in kinds:
            return kinds.index(Kind.FAIRY)
        return kinds.index(Kind.DRAGON)

    if Kind.WIZARD in kinds:
        return kinds.index(Kind.WIZARD)

    valued = [(i, p) for i, p in enumerate(plays) if p.acts_as in VALUE_KINDS]
    if valued:
        if trump is not None:
            trumps = [(i, p) for i, p in valued if p.effective_suit == trump]
            if trumps:
                return max(trumps, key=lambda pair: pair[1].value)[0]
        required = lead_suit(plays)
        following = [(i, p) for i, p in valued if p.effective_suit == required]
        if following:
            return max(following, key=lambda pair: pair[1].value)[0]
        return valued[0][0]  # cannot happen under the rules, just to be safe

    if Kind.JESTER in kinds:
        return kinds.index(Kind.JESTER)
    # Only Fairy and Bomb – impossible with at least 3 players, just to be safe.
    return next((i for i, k in enumerate(kinds) if k != Kind.BOMB), 0)


def trick_has_bomb(trick: Sequence[Play | Card]) -> bool:
    """True if the Bomb is in the trick: then nobody gets the trick."""
    return any(p.card.kind == Kind.BOMB for p in _as_plays(trick))
