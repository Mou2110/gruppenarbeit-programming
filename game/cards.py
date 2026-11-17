"""The cards of the game and how a deck is built."""
from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class Suit(str, Enum):
    """The four suits. The value (e.g. 'sea') is also used by the design."""
    SEA = 'sea'
    SARDINE = 'sardine'
    OLIVE = 'olive'
    SUN = 'sun'


class Kind(str, Enum):
    """The type of a card."""
    NUMBER = 'number'              # regular number card 1–13 in one suit
    WIZARD = 'wizard'              # wins the trick (the first Wizard in the trick)
    JESTER = 'jester'              # loses every trick
    # Special cards of the anniversary edition
    SHAPESHIFTER = 'shapeshifter'  # becomes a Wizard or a Jester when played
    DRAGON = 'dragon'              # beats everything, even Wizards – unless the Fairy is in the trick
    FAIRY = 'fairy'                # lowest card, but wins any trick that holds the Dragon
    BOMB = 'bomb'                  # nobody gets the trick
    WEREWOLF = 'werewolf'          # is swapped for the trump card before bidding
    JUGGLER = 'juggler'            # 7½ in a suit of your choice, afterwards everyone passes a card
    CLOUD = 'cloud'                # 9¾ in a suit of your choice, the winner changes their bid by 1


SPECIAL_KINDS = (Kind.SHAPESHIFTER, Kind.DRAGON, Kind.FAIRY, Kind.BOMB,
                 Kind.WEREWOLF, Kind.JUGGLER, Kind.CLOUD)

# Juggler and Cloud have a fixed value between two number cards.
SPECIAL_VALUES = {Kind.JUGGLER: 7.5, Kind.CLOUD: 9.75}


@dataclass(frozen=True)
class Card:
    """A single card.

    frozen=True means a card cannot be changed after it has been created.
    This prevents bugs where a card is modified "by accident".
    """
    id: str                    # unique name, e.g. 'sea-13', 'wizard-2' or 'dragon'
    kind: Kind
    suit: Suit | None = None   # only number cards have a fixed suit
    value: int | None = None   # only number cards have a printed value

    @property
    def is_number(self) -> bool:
        return self.kind == Kind.NUMBER

    @property
    def is_wizard(self) -> bool:
        return self.kind == Kind.WIZARD

    @property
    def is_jester(self) -> bool:
        return self.kind == Kind.JESTER

    @property
    def is_special(self) -> bool:
        return self.kind in SPECIAL_KINDS

    @property
    def needs_suit_choice(self) -> bool:
        """Juggler and Cloud: a suit is chosen when the card is played."""
        return self.kind in (Kind.JUGGLER, Kind.CLOUD)

    @property
    def needs_role_choice(self) -> bool:
        """Shapeshifter: Wizard or Jester is chosen when the card is played."""
        return self.kind == Kind.SHAPESHIFTER

    def __str__(self) -> str:
        # Readable name, e.g. "Sea 13" or "Dragon" – handy for tests and messages.
        if self.is_number:
            return f'{self.suit.value.capitalize()} {self.value}'
        return self.kind.value.capitalize()


def build_deck(special_cards: Iterable[Kind] = ()) -> list[Card]:
    """Builds the deck (not shuffled).

    Base deck: 4 suits x 13 number cards = 52, plus 4 Wizards and 4 Jesters = 60 cards.
    special_cards: which special cards to add (one card each).
    """
    deck: list[Card] = []
    for suit in Suit:
        for value in range(1, 14):
            deck.append(Card(id=f'{suit.value}-{value}', kind=Kind.NUMBER, suit=suit, value=value))
    for i in range(1, 5):
        deck.append(Card(id=f'wizard-{i}', kind=Kind.WIZARD))
        deck.append(Card(id=f'jester-{i}', kind=Kind.JESTER))
    for kind in dict.fromkeys(special_cards):  # dict.fromkeys removes duplicate entries
        if kind not in SPECIAL_KINDS:
            raise ValueError(f'{kind} is not a special card.')
        deck.append(Card(id=kind.value, kind=kind))
    return deck


def shuffled_deck(rng: random.Random | None = None, special_cards: Iterable[Kind] = ()) -> list[Card]:
    """Returns a freshly shuffled deck.

    rng is optional: tests can pass a fixed random generator
    so that the order is exactly the same every time.
    """
    deck = build_deck(special_cards)
    (rng or random).shuffle(deck)
    return deck
