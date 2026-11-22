"""Tests for the bonus joke card CR7: it always wins the trick, even against the Bomb.

It is optional and switched off by default; the host can add it in the lobby settings.
"""
from game.cards import BONUS_KINDS, SPECIAL_KINDS, Card, Kind, Suit, build_deck
from game.engine import Game
from game.lobby import Settings
from game.rules import Play, dealer_chooses_trump, legal_cards, trick_has_bomb, trick_winner
from views.cards import card_html, card_name

CR7 = Card('cr7', Kind.CR7)
WIZARD = Card('wizard-1', Kind.WIZARD)
DRAGON = Card('dragon', Kind.DRAGON)
FAIRY = Card('fairy', Kind.FAIRY)
BOMB = Card('bomb', Kind.BOMB)
JESTER = Card('jester-1', Kind.JESTER)


def num(suit, value):
    return Card(f'{suit.value}-{value}', Kind.NUMBER, suit, value)


def test_cr7_is_an_optional_card_and_off_by_default():
    assert BONUS_KINDS == (Kind.CR7,) and Kind.CR7 not in SPECIAL_KINDS   # not one of the original cards
    assert Kind.CR7 not in Settings().special_cards
    assert Settings().special_cards == list(SPECIAL_KINDS)


def test_the_deck_has_exactly_one_cr7_when_chosen():
    assert [c.id for c in build_deck([Kind.CR7]) if c.kind == Kind.CR7] == ['cr7']
    assert not any(c.kind == Kind.CR7 for c in build_deck())


def test_cr7_beats_the_wizard_even_when_the_wizard_came_first():
    assert trick_winner([WIZARD, CR7, num(Suit.SEA, 13)], trump=Suit.SEA) == 1


def test_cr7_beats_the_dragon_and_the_fairy():
    assert trick_winner([DRAGON, FAIRY, CR7], trump=None) == 2
    assert trick_winner([CR7, DRAGON], trump=None) == 0


def test_cr7_beats_the_highest_trump():
    assert trick_winner([num(Suit.SUN, 13), CR7, num(Suit.SUN, 12)], trump=Suit.SUN) == 1


def test_cr7_beats_a_shapeshifter_played_as_wizard():
    shapeshifter = Play(0, Card('shapeshifter', Kind.SHAPESHIFTER), as_wizard=True)
    assert trick_winner([shapeshifter, Play(1, CR7)], trump=None) == 1


def test_not_even_the_bomb_stops_cr7():
    trick = [BOMB, CR7, JESTER]
    assert not trick_has_bomb(trick)                 # the Bomb has no effect: CR7's player gets the trick
    assert trick_winner(trick, trump=None) == 1


def test_without_cr7_the_bomb_still_works():
    assert trick_has_bomb([BOMB, WIZARD, JESTER])


def test_the_table_does_not_show_the_trick_as_bombed_when_cr7_is_in_it():
    from views.table import trick_bombed
    assert not trick_bombed([Play(0, BOMB), Play(1, CR7)])
    assert trick_bombed([Play(0, BOMB), Play(1, WIZARD)])


def test_after_cr7_is_led_everyone_may_play_anything():
    hand = [num(Suit.SEA, 3), num(Suit.OLIVE, 9), JESTER]
    assert legal_cards(hand, [CR7]) == hand


def test_cr7_may_always_be_played_even_if_you_could_follow_suit():
    hand = [CR7, num(Suit.SEA, 3)]
    assert CR7 in legal_cards(hand, [num(Suit.SEA, 10)])


def test_cr7_turned_up_as_trump_means_no_trump():
    assert not dealer_chooses_trump(CR7)


def test_cr7_has_a_name_and_a_face():
    assert card_name(CR7) == 'CR7'
    html = card_html(CR7)
    assert 'art-cr7' in html and 'aria-label="CR7"' in html


def test_a_whole_game_with_cr7_can_be_played_by_bots():
    from game import bots
    import random
    game = Game([('a', 'A'), ('b', 'B'), ('c', 'C')], special_cards=[Kind.CR7], rng=random.Random(7))
    assert game.num_rounds == 20
    for _ in range(5000):
        if game.round_number > 3:
            break
        if game.phase.value in ('round_over',):
            game.next_round()
            continue
        player = game.players[game.current]
        view = game.view_for(player.id)
        if game.phase.value in ('werewolf', 'choosing_trump'):
            game.choose_trump(player.id, bots.choose_trump(view))
        elif game.phase.value == 'bidding':
            game.place_bid(player.id, bots.choose_bid(view))
        elif game.phase.value == 'playing':
            card_id, suit, as_wizard = bots.choose_card(view)
            game.play_card(player.id, card_id, suit=suit, as_wizard=as_wizard)
        else:
            raise AssertionError(f'unexpected phase {game.phase}')
    assert game.round_number > 3


def test_the_host_can_switch_cr7_on_in_the_lobby():
    from game.lobby import LobbyRegistry
    registry = LobbyRegistry(clock=lambda: 1000.0)
    lobby = registry.create('host', 'Erik')
    lobby.update_settings('host', special_cards=[Kind.CR7, Kind.BOMB])
    assert lobby.settings.special_cards == [Kind.BOMB, Kind.CR7]
    for _ in range(2):
        lobby.add_bot('host')
    lobby.connect('host')
    lobby.set_ready('host', True)
    assert lobby.game.special_cards and Kind.CR7 in lobby.game.special_cards
