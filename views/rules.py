"""The rules reference shared by the start page and the game table."""

SUIT_CHIPS = ''.join(f'<span class="mini s-{s}">{name}</span>' for s, name in
                     [('sea', 'Sea'), ('sardine', 'Sardine'), ('olive', 'Olive'), ('sun', 'Sun')])

RULES = [
    ('The cards', 'Four suits numbered 1 to 13, plus 4 Wizards and 4 Jesters. Wizards beat everything, '
                  'Jesters lose everything. Neither has a suit.<div class="minis">' + SUIT_CHIPS +
                  '<span class="mini k-wizard">Wizard</span><span class="mini k-jester">Jester</span></div>'),
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
    ('k-shift', 'Shapeshifter', 'Play it as a Wizard or as a Jester, your choice.'),
    ('k-dragon', 'Dragon', 'Beats every card, even Wizards. Only the Fairy beats it.'),
    ('k-fairy', 'Fairy', 'The lowest card, but it wins any trick that holds the Dragon.'),
    ('k-bomb', 'Bomb', 'Nobody gets the trick it lands in. Whoever would have won leads next.'),
    ('k-multi', 'Juggler 7½', 'Counts in a suit you pick. After its trick, everyone passes one card to the left.'),
    ('k-multi', 'Cloud 9¾', 'Counts in a suit you pick. Whoever wins its trick must change their bid by one right away.'),
    ('k-wolf', 'Werewolf', 'Swap it for the trump card before bidding and choose the trump yourself.'),
]


def rules_content() -> str:
    """Render the full rules reference, including special cards."""
    rules = ''.join(f'<div class="rule"><h3>{title}</h3><p>{text}</p></div>' for title, text in RULES)
    specials = ''.join(f'<div class="spec"><span class="swatch {css}"></span><p><b>{name}</b> · {text}</p></div>'
                       for css, name, text in SPECIALS)
    return f'{rules}<div class="rule"><h3>Special cards (optional)</h3>{specials}</div>'
