"""Game flow tests for the special cards (Werewolf, Juggler, Bomb, Cloud, Shapeshifter ...)."""
import random

import pytest

import game.engine as engine_module
from game.cards import SPECIAL_KINDS, Card, Kind, Suit, build_deck
from game.engine import Game, GameError, Phase
from game.scoring import round_score

SEA, SARDINE, OLIVE, SUN = Suit.SEA, Suit.SARDINE, Suit.OLIVE, Suit.SUN
PLAYERS = [('a', 'Ana'), ('b', 'Ben'), ('c', 'Caro'), ('d', 'Dani')]
IDS = [pid for pid, _ in PLAYERS]


def num(suit, value):
    return Card(id=f'{suit.value}-{value}', kind=Kind.NUMBER, suit=suit, value=value)


def special(kind):
    return Card(id=kind.value, kind=kind)


WIZ = Card('wizard-1', Kind.WIZARD)
SHIFT, DRAGON, FAIRY, BOMB, WOLF, JUGGLER, CLOUD = (special(k) for k in SPECIAL_KINDS)


def rig(monkeypatch, order):
    """Fixes the card order for round 1: first the cards for seats 1, 2, 3, 0, then the trump card."""
    def fake_shuffled_deck(rng=None, special_cards=()):
        ids = {c.id for c in order}
        rest = [c for c in build_deck(special_cards) if c.id not in ids]
        return rest + list(reversed(order))  # pop() takes from the end
    monkeypatch.setattr(engine_module, 'shuffled_deck', fake_shuffled_deck)


def game_in_play(hands, bids, leader=1, trump=None, round_number=None):
    """A game straight in the playing phase with fixed hands (seat -> cards)."""
    game = Game(PLAYERS, special_cards=SPECIAL_KINDS, rng=random.Random(0))
    for seat, cards in hands.items():
        game.players[seat].hand = list(cards)
    for seat, bid in bids.items():
        game.players[seat].bid = bid
    game.round_number = round_number or len(hands[0])
    game.trump = trump
    game.trick, game.tricks_played, game.cloud_owner = [], [], None
    game.phase, game.current = Phase.PLAYING, leader
    return game


ALL_ZERO = {0: 0, 1: 0, 2: 0, 3: 0}


# ---------------------------------------------------------------- Werewolf and choosing trump

def test_werewolf_holder_swaps_and_may_choose_no_trump(monkeypatch):
    rig(monkeypatch, [WOLF, num(SEA, 3), num(SEA, 4), num(SEA, 5), WIZ])
    game = Game(PLAYERS, special_cards=SPECIAL_KINDS)
    assert game.phase == Phase.WEREWOLF and game.current == 1
    with pytest.raises(GameError):
        game.choose_trump('c', SUN)          # only the holder may
    game.choose_trump('b', None)
    assert game.trump is None
    assert game.trump_card == WOLF
    assert game.players[1].hand == [WIZ]     # they get the turned-up card
    assert game.phase == Phase.BIDDING and game.current == 1


def test_werewolf_holder_chooses_a_suit(monkeypatch):
    rig(monkeypatch, [num(SEA, 3), num(SEA, 4), WOLF, num(SEA, 5), num(OLIVE, 2)])
    game = Game(PLAYERS, special_cards=SPECIAL_KINDS)
    assert game.phase == Phase.WEREWOLF and game.current == 3
    game.choose_trump('d', SUN)
    assert game.trump == SUN
    assert game.players[3].hand == [num(OLIVE, 2)]


@pytest.mark.parametrize('card', [WIZ])
def test_these_trump_cards_let_the_dealer_choose(monkeypatch, card):
    rig(monkeypatch, [num(SEA, 3), num(SEA, 4), num(SEA, 5), num(SEA, 6), card])
    game = Game(PLAYERS, special_cards=SPECIAL_KINDS)
    assert game.phase == Phase.CHOOSING_TRUMP and game.current == game.dealer
    with pytest.raises(GameError):
        game.choose_trump('a', None)         # the dealer has to pick a suit
    game.choose_trump('a', OLIVE)
    assert game.trump == OLIVE and game.phase == Phase.BIDDING


@pytest.mark.parametrize('card', [FAIRY, BOMB, WOLF, DRAGON, SHIFT, JUGGLER, CLOUD])
def test_special_card_as_trump_card_means_no_trump(monkeypatch, card):
    rig(monkeypatch, [num(SEA, 3), num(SEA, 4), num(SEA, 5), num(SEA, 6), card])
    game = Game(PLAYERS, special_cards=SPECIAL_KINDS)
    assert game.phase == Phase.BIDDING and game.trump is None


def test_clairvoyance_with_special_cards_has_no_werewolf_in_round_one():
    for seed in range(200):
        game = Game(PLAYERS, special_cards=SPECIAL_KINDS, clairvoyance=True, rng=random.Random(seed))
        assert game.phase != Phase.WEREWOLF
        assert game.trump_card is None or game.trump_card.kind != Kind.WEREWOLF
        assert all(c.kind != Kind.WEREWOLF for p in game.players for c in p.hand)


def test_clairvoyance_choice_is_made_after_the_card_is_revealed():
    game = game_in_play({1: [JUGGLER], 2: [SHIFT], 3: [num(SEA, 3)], 0: [num(SUN, 2)]}, ALL_ZERO,
                        trump=SUN, round_number=1)
    game.clairvoyance = True
    game.play_card('b', 'juggler')                 # played blind
    assert game.awaiting_choice == 1 and game.current == 1
    assert game.view_for('b')['must_declare'] and game.view_for('b')['playable'] == []
    with pytest.raises(GameError):
        game.play_card('c', 'shapeshifter')        # Ben has to choose first
    with pytest.raises(GameError):
        game.declare('b')                          # suit missing
    game.declare('b', suit=OLIVE)
    assert game.trick[0].suit == OLIVE and game.current == 2
    game.play_card('c', 'shapeshifter')
    game.declare('c', as_wizard=False)
    assert game.trick[1].as_wizard is False
    game.play_card('d', 'sea-3')
    game.play_card('a', 'sun-2')
    assert game.players[0].tricks_won == 1         # trump Sun 2 wins


def test_declare_is_rejected_when_nothing_to_choose():
    game = game_in_play({1: [num(SEA, 1)], 2: [num(SEA, 2)], 3: [num(SEA, 3)], 0: [num(SEA, 4)]}, ALL_ZERO,
                        round_number=1)
    with pytest.raises(GameError):
        game.declare('b', suit=SEA)


# ---------------------------------------------------------------- Choices when playing a card

def test_juggler_cloud_and_shapeshifter_need_a_choice():
    game = game_in_play({1: [JUGGLER, SHIFT], 2: [num(SEA, 2)] * 2, 3: [num(SEA, 3)] * 2, 0: [num(SEA, 4)] * 2},
                        ALL_ZERO)
    with pytest.raises(GameError):
        game.play_card('b', 'juggler')
    with pytest.raises(GameError):
        game.play_card('b', 'shapeshifter')
    assert game.trick == [] and len(game.players[1].hand) == 2   # nothing has changed
    game.play_card('b', 'shapeshifter', as_wizard=True)
    assert game.trick[0].as_wizard is True


def test_shapeshifter_as_wizard_takes_the_trick():
    game = game_in_play({1: [SHIFT], 2: [num(SEA, 13)], 3: [WIZ], 0: [num(SEA, 1)]}, ALL_ZERO, trump=SEA)
    game.play_card('b', 'shapeshifter', as_wizard=True)
    game.play_card('c', 'sea-13')
    game.play_card('d', 'wizard-1')
    game.play_card('a', 'sea-1')
    assert game.players[1].tricks_won == 1     # first "Wizard" in the trick


def test_fairy_takes_the_trick_with_the_dragon():
    game = game_in_play({1: [DRAGON], 2: [WIZ], 3: [FAIRY], 0: [num(SUN, 13)]}, ALL_ZERO, trump=SUN)
    for pid, cid in [('b', 'dragon'), ('c', 'wizard-1'), ('d', 'fairy'), ('a', 'sun-13')]:
        game.play_card(pid, cid)
    assert game.players[3].tricks_won == 1


# ---------------------------------------------------------------- Bomb

def test_bomb_trick_belongs_to_nobody_and_would_be_winner_leads():
    game = game_in_play({1: [num(SEA, 5), num(OLIVE, 1)], 2: [BOMB, num(OLIVE, 2)],
                         3: [num(SEA, 9), num(OLIVE, 3)], 0: [num(SEA, 2), num(OLIVE, 4)]}, ALL_ZERO)
    for pid, cid in [('b', 'sea-5'), ('c', 'bomb'), ('d', 'sea-9'), ('a', 'sea-2')]:
        game.play_card(pid, cid)
    assert all(p.tricks_won == 0 for p in game.players)
    assert game.last_trick_winner is None and game.last_trick_bombed
    assert game.current == 3                   # Dani would have won and leads


def test_bomb_in_last_trick_scores_correctly():
    game = game_in_play({1: [num(SEA, 5)], 2: [BOMB], 3: [num(SEA, 9)], 0: [num(SEA, 2)]},
                        {0: 0, 1: 0, 2: 0, 3: 1}, round_number=1)
    for pid, cid in [('b', 'sea-5'), ('c', 'bomb'), ('d', 'sea-9'), ('a', 'sea-2')]:
        game.play_card(pid, cid)
    assert game.phase == Phase.ROUND_OVER
    assert [p.round_scores[-1] for p in game.players] == [20, 20, 20, -10]


# ---------------------------------------------------------------- Juggler: passing cards

def juggler_game():
    return game_in_play({1: [JUGGLER, num(SEA, 2)], 2: [num(SEA, 9), num(OLIVE, 1)],
                         3: [num(SEA, 3), num(SUN, 5)], 0: [num(SEA, 4), num(SUN, 6)]}, ALL_ZERO)


def test_juggler_trick_leads_to_passing_cards_left():
    game = juggler_game()
    game.play_card('b', 'juggler', suit=SEA)
    for pid, cid in [('c', 'sea-9'), ('d', 'sea-3'), ('a', 'sea-4')]:
        game.play_card(pid, cid)
    assert game.players[2].tricks_won == 1     # Sea 9 beats the Juggler (7½)
    assert game.phase == Phase.PASSING
    with pytest.raises(GameError):
        game.play_card('c', 'olive-1')         # pass first
    game.pass_card('b', 'sea-2')
    assert not game.must_pass('b') and game.must_pass('c')
    assert game.view_for('a')['players'][1]['has_passed']
    with pytest.raises(GameError):
        game.pass_card('b', 'sea-2')           # only once
    with pytest.raises(GameError):
        game.pass_card('c', 'sea-2')           # a card you do not hold
    game.pass_card('c', 'olive-1')
    game.pass_card('d', 'sun-5')
    game.pass_card('a', 'sun-6')
    # Everyone gets the card of their right neighbour (cards are passed to the left).
    assert game.players[1].hand == [num(SUN, 6)]
    assert game.players[2].hand == [num(SEA, 2)]
    assert game.players[3].hand == [num(OLIVE, 1)]
    assert game.players[0].hand == [num(SUN, 5)]
    assert game.received == {2: num(SEA, 2), 3: num(OLIVE, 1), 0: num(SUN, 5), 1: num(SUN, 6)}
    assert game.phase == Phase.PLAYING and game.current == 2


def test_no_passing_after_the_last_trick():
    game = game_in_play({1: [JUGGLER], 2: [num(SEA, 9)], 3: [num(SEA, 3)], 0: [num(SEA, 4)]}, ALL_ZERO,
                        round_number=1)
    game.play_card('b', 'juggler', suit=SEA)
    for pid, cid in [('c', 'sea-9'), ('d', 'sea-3'), ('a', 'sea-4')]:
        game.play_card(pid, cid)
    assert game.phase == Phase.ROUND_OVER


def test_juggler_with_bomb_still_passes():
    game = game_in_play({1: [JUGGLER, num(SEA, 2)], 2: [BOMB, num(OLIVE, 1)],
                         3: [num(SEA, 3), num(SUN, 5)], 0: [num(SEA, 8), num(SUN, 6)]}, ALL_ZERO)
    game.play_card('b', 'juggler', suit=SEA)
    for pid, cid in [('c', 'bomb'), ('d', 'sea-3'), ('a', 'sea-8')]:
        game.play_card(pid, cid)
    assert game.phase == Phase.PASSING
    assert all(p.tricks_won == 0 for p in game.players)
    for pid, cid in [('a', 'sun-6'), ('b', 'sea-2'), ('c', 'olive-1'), ('d', 'sun-5')]:
        game.pass_card(pid, cid)
    assert game.current == 0                   # Sea 8 would have won


# ---------------------------------------------------------------- Cloud: changing the bid

def test_cloud_owner_must_change_bid():
    game = game_in_play({1: [CLOUD], 2: [num(SEA, 3)], 3: [num(SEA, 2)], 0: [num(SEA, 1)]},
                        {0: 0, 1: 1, 2: 0, 3: 0}, round_number=1)
    game.play_card('b', 'cloud', suit=SEA)
    for pid, cid in [('c', 'sea-3'), ('d', 'sea-2'), ('a', 'sea-1')]:
        game.play_card(pid, cid)
    assert game.phase == Phase.ADJUSTING and game.current == 1
    assert game.adjust_options() == [-1, 1]
    assert game.view_for('b')['adjust_options'] == [-1, 1]
    with pytest.raises(GameError):
        game.adjust_bid('c', 1)
    with pytest.raises(GameError):
        game.adjust_bid('b', 0)
    game.adjust_bid('b', -1)
    assert game.players[1].final_bid == 0
    assert game.players[1].round_scores[-1] == round_score(0, 1) == -10
    assert game.phase == Phase.ROUND_OVER


def test_cloud_bid_change_happens_right_after_its_trick():
    game = game_in_play({1: [CLOUD, num(OLIVE, 1)], 2: [num(SEA, 3), num(OLIVE, 2)],
                         3: [num(SEA, 2), num(OLIVE, 3)], 0: [num(SEA, 1), num(OLIVE, 4)]},
                        {0: 0, 1: 2, 2: 0, 3: 0})
    game.play_card('b', 'cloud', suit=SEA)
    for pid, cid in [('c', 'sea-3'), ('d', 'sea-2'), ('a', 'sea-1')]:
        game.play_card(pid, cid)
    assert game.phase == Phase.ADJUSTING and game.current == 1   # right away, not at the end of the round
    game.adjust_bid('b', -1)
    assert game.players[1].final_bid == 1
    assert game.phase == Phase.PLAYING and game.current == 1      # Ben leads the next trick
    for pid, cid in [('b', 'olive-1'), ('c', 'olive-2'), ('d', 'olive-3'), ('a', 'olive-4')]:
        game.play_card(pid, cid)
    assert game.phase == Phase.ROUND_OVER
    assert game.players[1].round_scores[-1] == round_score(1, 1) == 30


def test_cloud_and_juggler_in_one_trick_adjust_then_pass():
    game = game_in_play({1: [CLOUD, num(OLIVE, 1)], 2: [JUGGLER, num(OLIVE, 2)],
                         3: [num(SEA, 2), num(OLIVE, 3)], 0: [num(SEA, 1), num(OLIVE, 4)]},
                        {0: 0, 1: 1, 2: 0, 3: 0})
    game.play_card('b', 'cloud', suit=SEA)
    game.play_card('c', 'juggler', suit=SEA)
    game.play_card('d', 'sea-2')
    game.play_card('a', 'sea-1')
    assert game.phase == Phase.ADJUSTING
    game.adjust_bid('b', 1)
    assert game.phase == Phase.PASSING


def test_cloud_owner_with_bid_zero_goes_up_automatically():
    game = game_in_play({1: [CLOUD], 2: [num(SEA, 3)], 3: [num(SEA, 2)], 0: [num(SEA, 1)]},
                        ALL_ZERO, round_number=1)
    game.play_card('b', 'cloud', suit=SEA)
    for pid, cid in [('c', 'sea-3'), ('d', 'sea-2'), ('a', 'sea-1')]:
        game.play_card(pid, cid)
    assert game.phase == Phase.ROUND_OVER
    assert game.players[1].bid_change == 1
    assert game.players[1].round_scores[-1] == 30   # bid is now 1, 1 trick taken


def test_cloud_and_bomb_in_one_trick_change_nothing():
    game = game_in_play({1: [CLOUD], 2: [BOMB], 3: [num(SEA, 2)], 0: [num(SEA, 1)]},
                        {0: 0, 1: 1, 2: 0, 3: 0}, round_number=1)
    game.play_card('b', 'cloud', suit=SEA)
    for pid, cid in [('c', 'bomb'), ('d', 'sea-2'), ('a', 'sea-1')]:
        game.play_card(pid, cid)
    assert game.phase == Phase.ROUND_OVER
    assert all(p.bid_change == 0 for p in game.players)


def test_cloud_goes_to_whoever_wins_its_trick():
    game = game_in_play({1: [CLOUD], 2: [num(SEA, 13)], 3: [num(SEA, 2)], 0: [num(SEA, 1)]},
                        {0: 0, 1: 0, 2: 1, 3: 0}, round_number=1)
    game.play_card('b', 'cloud', suit=SEA)
    for pid, cid in [('c', 'sea-13'), ('d', 'sea-2'), ('a', 'sea-1')]:
        game.play_card(pid, cid)
    assert game.phase == Phase.ADJUSTING and game.current == 2
