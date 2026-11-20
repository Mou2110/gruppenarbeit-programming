"""The rules reference shared by the start page and the game table."""

from nicegui import ui

from game.cards import Card, Kind, Suit

from .cards import CARD_RANK, KIND_LABEL, card_html
from .common import ICON_CLOSE, icon_button

RULES = [
    ('Rounds', 'Round 1 deals one card each, round 2 two cards, and so on: 20 rounds with 3 players, '
               '15 with 4, 12 with 5 and 10 with 6.'),
    ('Trump', 'After dealing, the next card is turned up and its suit is trump. A Jester means no trump, '
              'a Wizard lets the dealer choose. Without special cards the last round has no trump.'),
    ('Bidding', 'Starting left of the dealer, everyone says how many tricks they will win. '
                "The bids must not add up to the number of tricks, so the last player has one option less."),
    ('Playing a trick', 'Follow the suit of the first card if you can. Wizards, Jesters and special cards may '
                        'always be played. The trick goes to the first Wizard, otherwise the highest trump, '
                        'otherwise the highest card of the lead suit. The winner leads the next trick.'),
    ('Scoring', 'Bid hit exactly: 20 points plus 10 per trick. Bid missed: minus 10 for every trick you are off. '
                'Most points after the last round wins.'),
    ('Round 1 · Clairvoyance', "In round 1 you can't see your own card, only everyone else's. "
                               'The Werewolf sits out round 1. If your hidden card turns out to be a Shapeshifter, '
                               'Juggler or Cloud, you make your choice once it is revealed.'),
]

SPECIALS = [
    (Kind.SHAPESHIFTER, 'Play it as a Wizard or as a Jester, your choice.'),
    (Kind.DRAGON, 'Beats every card, even Wizards. Only the Fairy beats it.'),
    (Kind.FAIRY, 'The lowest card, but it wins any trick that holds the Dragon.'),
    (Kind.BOMB, 'Nobody gets the trick it lands in. Whoever would have won leads next.'),
    (Kind.JUGGLER, 'Counts in a suit you pick. After its trick, everyone passes one card to the left.'),
    (Kind.CLOUD, 'Counts in a suit you pick. Whoever wins its trick must change their bid by one right away.'),
    (Kind.WEREWOLF, 'Swap it for the trump card before bidding and choose the trump yourself.'),
]


def _section(title: str, body: str, collapsible: bool) -> str:
    """One rule section. collapsible: a <details> element that opens and closes with a click (no JavaScript)."""
    if collapsible:
        return f'<details class="rule"><summary><h3>{title}</h3></summary>{body}</details>'
    return f'<div class="rule"><h3>{title}</h3>{body}</div>'


def rules_content(collapsible: bool = False) -> str:
    """Render the full rules reference, including special cards.

    collapsible=True (start page): every section starts closed and opens with a click.
    """
    examples = [Card(f'{suit.value}-12', Kind.NUMBER, suit, 12) for suit in Suit]
    examples.extend(Card(kind.value, kind) for kind in (Kind.WIZARD, Kind.JESTER))
    faces = ''.join(card_html(card, 'sm') for card in examples)
    deck = _section('The cards', '<p>Four suits numbered 1 to 13, plus 4 Wizards and 4 Jesters. '
                    'Wizards usually win and Jesters usually lose. Neither has a suit.</p>'
                    f'<div class="rule-card-samples">{faces}</div>', collapsible)

    rules = ''.join(_section(title, f'<p>{text}</p>', collapsible) for title, text in RULES)
    specials = []
    for kind, text in SPECIALS:
        card = Card(kind.value, kind)
        name = KIND_LABEL[kind]
        if card.needs_suit_choice:
            name += f' {CARD_RANK[kind]}'
        specials.append(f'<div class="spec">{card_html(card, "sm")}<p><b>{name}</b> · {text}</p></div>')
    return f'{deck}{rules}{_section("Special cards (optional)", "".join(specials), collapsible)}'


def game_rules_dialog() -> ui.dialog:
    with ui.dialog().props('aria-labelledby=game-rules-title').mark('game-rules-dialog') as dialog:
        with ui.element('div').classes('panel rules-dialog-panel'):
            with ui.element('div').classes('rules-dialog-header'):
                ui.html('<h2 id="game-rules-title">Game rules</h2>', sanitize=False)
                icon_button(ICON_CLOSE, 'Close game rules', dialog.close, marker='close-game-rules') \
                    .props('autofocus title="Close game rules"')
            ui.html(rules_content(), sanitize=False).classes('rules-dialog-body') \
                .props('tabindex=0 role=region aria-labelledby=game-rules-title')
    return dialog
