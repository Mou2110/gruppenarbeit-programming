"""Card art remains identifiable wherever the shared card renderer is used."""
import pytest

from game.cards import Card, Kind, SPECIAL_KINDS, Suit
from views.cards import KIND_LABEL, SUIT_LABEL, card_html
from views.rules import rules_content


@pytest.mark.parametrize('kind, rank', [
    (Kind.WIZARD, 'W'), (Kind.JESTER, 'J'), (Kind.SHAPESHIFTER, 'S'),
    (Kind.DRAGON, 'D'), (Kind.FAIRY, 'F'), (Kind.BOMB, 'B'),
    (Kind.WEREWOLF, 'WW'), (Kind.JUGGLER, '7½'), (Kind.CLOUD, '9¾'),
])
def test_illustrated_cards_keep_a_readable_corner_rank_and_accessible_name(kind, rank):
    face = card_html(Card(kind.value, kind), 'sm')
    assert f'art-{kind.value}' in face
    assert f'class="card-rank">{rank}</span>' in face
    assert f'aria-label="{KIND_LABEL[kind]}"' in face


@pytest.mark.parametrize('suit', list(Suit))
def test_number_cards_preserve_their_live_value_and_suit(suit):
    label = SUIT_LABEL[suit]
    face = card_html(Card(f'{suit.value}-13', Kind.NUMBER, suit, 13))
    assert f'number-face s-{suit.value}' in face
    assert 'class="card-rank">13</span>' in face
    assert f'aria-label="{label} 13"' in face


@pytest.mark.parametrize('kind', [Kind.JUGGLER, Kind.CLOUD])
def test_assigning_a_suit_labels_the_face_without_covering_its_art(kind):
    face = card_html(Card(kind.value, kind), chosen=Suit.SUN)
    assert f'art-{kind.value}' in face
    assert 'class="chosen-suit' not in face
    assert f'aria-label="{KIND_LABEL[kind]} as Sun"' in face


def test_the_rules_use_the_same_face_for_each_card_kind_and_suit():
    rules = rules_content()
    for kind in (Kind.WIZARD, Kind.JESTER, *SPECIAL_KINDS):
        assert card_html(Card(kind.value, kind), 'sm') in rules
    for suit in Suit:
        assert card_html(Card(f'{suit.value}-12', Kind.NUMBER, suit, 12), 'sm') in rules
