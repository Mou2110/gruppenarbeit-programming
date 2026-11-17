"""Big stress test: many complete random games with 3–6 players and all special cards.

After EVERY move the game state is checked (no card lost or duplicated,
nobody sees anyone else's cards ...). The trick winner is additionally compared
with a second, independently written calculation.
"""
import itertools
import random

import pytest

from game.cards import SPECIAL_KINDS, Kind, Suit
from game.engine import Game, GameError, Phase
from game.rules import legal_cards
from game.scoring import round_score


# ------------------------------------------------- independent reference calculation (oracle)

def oracle_winner(plays, trump):
    """Trick winner, calculated differently from rules.py: every card gets a rank."""
    kinds = []
    for p in plays:
        if p.card.kind == Kind.SHAPESHIFTER:
            kinds.append('wizard' if p.as_wizard else 'jester')
        else:
            kinds.append(p.card.kind.value)

    lead = None
    for p, k in zip(plays, kinds):
        if k in ('jester', 'fairy', 'bomb'):
            continue
        if k in ('wizard', 'dragon'):
            break
        lead = p.card.suit if k == 'number' else p.suit
        break

    def value(p, k):
        return {'number': p.card.value if p.card.value else 0, 'juggler': 7.5, 'cloud': 9.75}[k]

    dragon_and_fairy = 'dragon' in kinds and 'fairy' in kinds
    best_rank, best_pos = None, None
    for pos, (p, k) in enumerate(zip(plays, kinds)):
        suit = p.card.suit if k == 'number' else p.suit
        if k == 'fairy':
            rank = (9,) if dragon_and_fairy else (-1,)
        elif k == 'dragon':
            rank = (8,)
        elif k == 'wizard':
            rank = (7, -pos)
        elif k in ('number', 'juggler', 'cloud'):
            if trump is not None and suit == trump:
                rank = (6, value(p, k))
            elif suit == lead:
                rank = (5, value(p, k))
            else:
                rank = (1, value(p, k))
        elif k == 'jester':
            rank = (0, -pos)
        else:  # the bomb has no value
            rank = (-2,)
        if best_rank is None or rank > best_rank:
            best_rank, best_pos = rank, pos
    return best_pos


# ------------------------------------------------------------------- Checks

def all_card_ids(game):
    ids = [c.id for p in game.players for c in p.hand]
    ids += [pl.card.id for pl in game.trick]
    ids += [pl.card.id for trick in game.tricks_played for pl in trick]
    if game.trump_card is not None:
        ids.append(game.trump_card.id)
    return ids


def check_state(game, round_cards):
    ids = all_card_ids(game)
    assert len(ids) == len(set(ids)), 'a card is in the game twice'
    assert set(ids) == round_cards, 'a card has disappeared or appeared'
    if game.phase in (Phase.PLAYING, Phase.PASSING, Phase.BIDDING, Phase.ADJUSTING):
        assert not any(c.kind == Kind.WEREWOLF for p in game.players for c in p.hand), 'Werewolf still in a hand'
    if game.phase in (Phase.PLAYING, Phase.PASSING):
        sizes = {len(p.hand) + (1 if any(pl.player == i for pl in game.trick) else 0)
                 for i, p in enumerate(game.players)}
        assert len(sizes) == 1, 'hands have different sizes'
    for i, p in enumerate(game.players):
        view = game.view_for(p.id)
        assert view['my_index'] == i
        if not view['clairvoyance']:
            assert [c.id for c in view['my_hand']] == [c.id for c in p.hand]
            assert all(o['visible_hand'] is None for o in view['players']), 'other players\' cards visible!'
        else:
            assert view['my_hand'] is None
            assert all((o['visible_hand'] is None) == (j == i) for j, o in enumerate(view['players']))


def snapshot(game):
    return (game.phase, game.current, [tuple(c.id for c in p.hand) for p in game.players],
            len(game.trick), [p.bid for p in game.players], game.trump)


def try_illegal_moves(game, rng):
    """Illegal moves must be rejected and must not change anything."""
    before = snapshot(game)
    current = game.players[game.current]
    others = [p for i, p in enumerate(game.players) if i != game.current]
    if game.phase == Phase.PLAYING:
        illegal = [c for c in current.hand if c not in legal_cards(current.hand, game.trick)]
        if illegal:
            with pytest.raises(GameError):
                game.play_card(current.id, illegal[0].id, suit=Suit.SEA, as_wizard=True)
        other = rng.choice(others)
        if other.hand:
            with pytest.raises(GameError):
                game.play_card(other.id, other.hand[0].id, suit=Suit.SEA, as_wizard=True)
    elif game.phase == Phase.BIDDING:
        with pytest.raises(GameError):
            game.place_bid(rng.choice(others).id, 0)
        with pytest.raises(GameError):
            game.place_bid(current.id, game.round_number + 1)
        forbidden = game.forbidden_bid()
        if forbidden is not None:
            with pytest.raises(GameError):
                game.place_bid(current.id, forbidden)
    assert snapshot(game) == before


def play_random_game(num_players, specials, seed, clairvoyance=False):
    rng = random.Random(seed)
    players = [(f'p{i}', f'P{i}') for i in range(num_players)]
    game = Game(players, special_cards=specials, clairvoyance=clairvoyance, rng=random.Random(seed + 1000))
    stats = {'werewolf': 0, 'passing': 0, 'adjusting': 0, 'bombs': 0, 'dragon_fairy': 0}
    expected_dealer = 0

    while True:
        # ---------- Start of round
        assert game.dealer == expected_dealer
        round_cards = set(all_card_ids(game))
        assert len(round_cards) == game.round_number * num_players + (1 if game.trump_card else 0)
        if specials:
            assert game.trump_card is not None, 'with special cards there is always a trump card'
        dealt_wolf = any(c.kind == Kind.WEREWOLF for p in game.players for c in p.hand)
        assert (game.phase == Phase.WEREWOLF) == dealt_wolf
        bidders = []
        leader = (game.dealer + 1) % num_players

        while game.phase not in (Phase.ROUND_OVER, Phase.GAME_OVER):
            check_state(game, round_cards)
            phase = game.phase
            if phase == Phase.WEREWOLF:
                stats['werewolf'] += 1
                holder = game.current
                old_trump_card = game.trump_card
                choice = rng.choice(list(Suit) + [None])
                game.choose_trump(game.players[holder].id, choice)
                assert game.trump_card.kind == Kind.WEREWOLF and game.trump == choice
                assert old_trump_card in game.players[holder].hand
            elif phase == Phase.CHOOSING_TRUMP:
                assert game.current == game.dealer
                choice = rng.choice(list(Suit))
                game.choose_trump(game.players[game.current].id, choice)
                assert game.trump == choice
            elif phase == Phase.BIDDING:
                try_illegal_moves(game, rng)
                bidders.append(game.current)
                game.place_bid(game.players[game.current].id, rng.choice(game.allowed_bids()))
            elif phase == Phase.PLAYING:
                if not game.trick:
                    assert game.current == leader, 'wrong player leads'
                try_illegal_moves(game, rng)
                player = game.players[game.current]
                card = rng.choice(legal_cards(player.hand, game.trick))
                suit, as_wizard = rng.choice(list(Suit)), rng.choice([True, False])
                if game.is_clairvoyance_round():
                    suit = as_wizard = None   # own card hidden: the game chooses automatically
                tricks_before = len(game.tricks_played)
                won_before = [p.tricks_won for p in game.players]
                game.play_card(player.id, card.id, suit=suit, as_wizard=as_wizard)
                if game.awaiting_choice is not None:
                    # Clairvoyance: the card lies face up, now the choice is made.
                    assert game.current == game.awaiting_choice
                    before = snapshot(game)
                    other = game.players[(game.current + 1) % num_players]
                    if other.hand:
                        with pytest.raises(GameError):
                            game.play_card(other.id, other.hand[0].id)
                    assert snapshot(game) == before
                    game.declare(player.id, suit=rng.choice(list(Suit)), as_wizard=rng.choice([True, False]))
                    stats['declared'] = stats.get('declared', 0) + 1
                if len(game.tricks_played) > tricks_before:
                    plays = game.last_trick
                    expected = plays[oracle_winner(plays, game.trump)].player
                    assert game.last_trick_leader == expected, f'wrong trick winner: {plays}'
                    kinds = {pl.card.kind for pl in plays}
                    bombed = Kind.BOMB in kinds
                    stats['bombs'] += bombed
                    stats['dragon_fairy'] += {Kind.DRAGON, Kind.FAIRY} <= kinds
                    diff = [p.tricks_won - b for p, b in zip(game.players, won_before)]
                    assert sum(diff) == (0 if bombed else 1)
                    if not bombed:
                        assert diff[expected] == 1
                    leader = expected
            elif phase == Phase.PASSING:
                stats['passing'] += 1
                hands_before = [list(p.hand) for p in game.players]
                chosen = {}
                for i in rng.sample(range(num_players), num_players):
                    p = game.players[i]
                    chosen[i] = rng.choice(p.hand)
                    game.pass_card(p.id, chosen[i].id)
                for i, p in enumerate(game.players):
                    giver = (i - 1) % num_players
                    expected_hand = [c for c in hands_before[i] if c != chosen[i]] + [chosen[giver]]
                    assert sorted(c.id for c in p.hand) == sorted(c.id for c in expected_hand)
                assert game.phase == Phase.PLAYING and game.current == leader
            elif phase == Phase.ADJUSTING:
                stats['adjusting'] += 1
                assert game.current == game.cloud_owner
                game.adjust_bid(game.players[game.current].id, rng.choice(game.adjust_options()))

        # ---------- End of round
        assert bidders == [(game.dealer + 1 + k) % num_players for k in range(num_players)]
        bombed_tricks = sum(1 for t in game.tricks_played if any(pl.card.kind == Kind.BOMB for pl in t))
        assert bombed_tricks <= 1
        assert len(game.tricks_played) == game.round_number
        assert sum(p.tricks_won for p in game.players) == game.round_number - bombed_tricks
        if game.no_matching_bids:
            assert sum(p.bid for p in game.players) != game.round_number
        for i, p in enumerate(game.players):
            if i == game.cloud_owner:
                assert p.bid_change in (-1, 1) and p.final_bid >= 0
            else:
                assert p.bid_change == 0
            assert p.round_scores[-1] == round_score(p.final_bid, p.tricks_won)
            assert p.score == sum(p.round_scores)
        if game.phase == Phase.GAME_OVER:
            break
        game.next_round()
        expected_dealer = (expected_dealer + 1) % num_players

    assert game.round_number == 60 // num_players
    return stats


SPECIAL_SETS = [
    (),
    SPECIAL_KINDS,
    (Kind.SHAPESHIFTER,),
    (Kind.DRAGON, Kind.FAIRY),
    (Kind.BOMB, Kind.CLOUD),
    (Kind.WEREWOLF, Kind.JUGGLER),
]


@pytest.mark.parametrize('num_players', [3, 4, 5, 6])
@pytest.mark.parametrize('specials', SPECIAL_SETS)
def test_random_games_follow_all_rules(num_players, specials):
    for seed in range(12):
        play_random_game(num_players, specials, seed)


@pytest.mark.parametrize('num_players', [3, 4, 5, 6])
@pytest.mark.parametrize('specials', [(), SPECIAL_KINDS])
def test_random_games_with_clairvoyance(num_players, specials):
    for seed in range(8):
        play_random_game(num_players, specials, seed, clairvoyance=True)


def test_every_special_situation_actually_happens():
    """Make sure the stress test really reaches the rare cases."""
    totals = {}
    for num_players, seed in itertools.product([3, 4, 5, 6], range(15)):
        for key, count in play_random_game(num_players, SPECIAL_KINDS, seed).items():
            totals[key] = totals.get(key, 0) + count
    assert all(count > 0 for count in totals.values()), totals
