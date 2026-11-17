"""Tests for the game flow (game/engine.py)."""
import random

import pytest

from game.cards import Card, Kind, Suit
from game.engine import Game, GameError, Phase
from game.rules import legal_cards
from game.scoring import round_score

PLAYERS = [('a', 'Ana'), ('b', 'Ben'), ('c', 'Caro'), ('d', 'Dani')]


def num(suit: Suit, value: int) -> Card:
    return Card(id=f'{suit.value}-{value}', kind=Kind.NUMBER, suit=suit, value=value)


def new_game(seed: int = 1, clairvoyance: bool = True) -> Game:
    return Game(PLAYERS, clairvoyance=clairvoyance, rng=random.Random(seed))


def finish_trump_choice(game: Game) -> None:
    if game.phase == Phase.CHOOSING_TRUMP:
        game.choose_trump(game.players[game.current].id, Suit.SEA)


def test_first_round_deals_one_card_each():
    game = new_game()
    assert game.round_number == 1
    assert all(len(p.hand) == 1 for p in game.players)
    assert game.num_rounds == 15


def test_bidding_out_of_turn_is_rejected():
    game = new_game()
    finish_trump_choice(game)
    not_current = game.players[(game.current + 1) % 4].id
    with pytest.raises(GameError):
        game.place_bid(not_current, 0)


def test_bid_must_be_in_range():
    game = new_game()
    finish_trump_choice(game)
    with pytest.raises(GameError):
        game.place_bid(game.players[game.current].id, 2)  # round 1: only 0 or 1


def test_last_bidder_cannot_make_bids_add_up():
    game = new_game()
    finish_trump_choice(game)
    # Round 1: the first three bid 0 -> the last one must not bid 1.
    for _ in range(3):
        game.place_bid(game.players[game.current].id, 0)
    assert game.forbidden_bid() == 1
    assert game.allowed_bids() == [0]
    with pytest.raises(GameError):
        game.place_bid(game.players[game.current].id, 1)
    game.place_bid(game.players[game.current].id, 0)
    assert game.phase == Phase.PLAYING


def test_only_last_bidder_is_restricted():
    game = new_game()
    finish_trump_choice(game)
    assert game.forbidden_bid() is None
    assert game.allowed_bids() == [0, 1]


def test_rule_can_be_switched_off():
    game = Game(PLAYERS, no_matching_bids=False, rng=random.Random(1))
    finish_trump_choice(game)
    for _ in range(3):
        game.place_bid(game.players[game.current].id, 0)
    assert game.forbidden_bid() is None
    game.place_bid(game.players[game.current].id, 1)


def test_must_follow_suit_in_engine():
    game = new_game(clairvoyance=False)
    finish_trump_choice(game)
    # Set the hands on purpose so the test is unambiguous.
    game.players[1].hand = [num(Suit.SEA, 9)]
    game.players[2].hand = [num(Suit.SEA, 2)]
    game.players[2].hand.append(num(Suit.OLIVE, 13))
    game.players[3].hand = [num(Suit.SUN, 1)]
    game.players[0].hand = [num(Suit.SUN, 2)]
    game.phase, game.current = Phase.PLAYING, 1
    game.play_card('b', 'sea-9')
    with pytest.raises(GameError):
        game.play_card('c', 'olive-13')  # holds Sea, must follow suit
    game.play_card('c', 'sea-2')


def test_trick_winner_leads_next_trick():
    game = new_game(clairvoyance=False)
    game.trump = None
    game.players[1].hand = [num(Suit.SEA, 5), num(Suit.SUN, 1)]
    game.players[2].hand = [num(Suit.SEA, 13), num(Suit.SUN, 2)]
    game.players[3].hand = [num(Suit.SEA, 1), num(Suit.SUN, 3)]
    game.players[0].hand = [num(Suit.SEA, 2), num(Suit.SUN, 4)]
    for p in game.players:
        p.bid = 0
    game.phase, game.current = Phase.PLAYING, 1
    for pid, cid in [('b', 'sea-5'), ('c', 'sea-13'), ('d', 'sea-1'), ('a', 'sea-2')]:
        game.play_card(pid, cid)
    assert game.last_trick_winner == 2
    assert game.current == 2
    assert game.players[2].tricks_won == 1


def test_clairvoyance_hides_own_card_in_round_one_only():
    game = new_game(clairvoyance=True)
    view = game.view_for('a')
    assert view['my_hand'] is None
    others = [p for p in view['players'] if p['id'] != 'a']
    assert all(p['visible_hand'] is not None for p in others)
    me = next(p for p in view['players'] if p['id'] == 'a')
    assert me['visible_hand'] is None


def test_normal_round_never_shows_other_hands():
    game = new_game(clairvoyance=False)
    view = game.view_for('a')
    assert view['my_hand'] is not None
    assert all(p['visible_hand'] is None for p in view['players'])


def test_full_game_with_random_legal_moves():
    """Plays a whole game with random but legal moves."""
    rng = random.Random(42)
    game = Game(PLAYERS, rng=random.Random(7))
    while True:
        finish_trump_choice(game)
        while game.phase == Phase.BIDDING:
            game.place_bid(game.players[game.current].id, rng.choice(game.allowed_bids()))
        while game.phase == Phase.PLAYING:
            p = game.players[game.current]
            options = legal_cards(p.hand, game.trick)
            game.play_card(p.id, rng.choice(options).id)
        # Every round: sum of tricks = round number, points added up correctly.
        assert sum(p.tricks_won for p in game.players) == game.round_number
        for p in game.players:
            assert p.round_scores[-1] == round_score(p.bid, p.tricks_won)
        if game.phase == Phase.GAME_OVER:
            break
        game.next_round()
    assert game.round_number == 15
    assert all(len(p.round_scores) == 15 for p in game.players)
    assert all(p.score == sum(p.round_scores) for p in game.players)
