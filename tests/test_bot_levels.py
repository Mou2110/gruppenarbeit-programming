"""Bot levels: Normal (as before), Spiteful and Ruthless.

1. Whole games with every level (mixed at one table) finish without errors and without illegal moves.
2. Spiteful: once its own bid can no longer be made, it works against the leader.
3. Ruthless: also uses the Bomb, the Cloud, the Juggler pass and its bid against the leader.
4. The lobby remembers the level of every bot, also in lobbies saved before levels existed.
"""
import pickle
import random

import pytest

from game import bots
from game.cards import SPECIAL_KINDS, Card, Kind, Suit
from game.engine import Game, Phase
from game.lobby import LobbyError, LobbyRegistry, Member
from game.rules import Play
from views.start import start_practice


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


# ------------------------------------------------------------- 1. whole games never break

def play_game(game: Game, levels: list[str]) -> None:
    """Every seat is a bot with its own level. The engine raises GameError for any illegal move."""
    level = {p.id: levels[i % len(levels)] for i, p in enumerate(game.players)}
    while game.phase != Phase.GAME_OVER:
        if game.phase == Phase.ROUND_OVER:
            game.next_round()
            continue
        if game.phase == Phase.PASSING:
            for player in game.players:
                if game.must_pass(player.id):
                    game.pass_card(player.id, bots.choose_pass(game.view_for(player.id), level[player.id]))
            continue
        player = game.players[game.current]
        view = game.view_for(player.id)
        if game.phase in (Phase.WEREWOLF, Phase.CHOOSING_TRUMP):
            game.choose_trump(player.id, bots.choose_trump(view))
        elif game.phase == Phase.BIDDING:
            game.place_bid(player.id, bots.choose_bid(view, level[player.id]))
        elif game.phase == Phase.ADJUSTING:
            game.adjust_bid(player.id, bots.choose_adjustment(view))
        elif game.awaiting_choice is not None:
            suit, as_wizard = bots.declare_played_card(view)
            game.declare(player.id, suit=suit, as_wizard=as_wizard)
        else:
            card_id, suit, as_wizard = bots.choose_card(view, level[player.id])
            game.play_card(player.id, card_id, suit=suit, as_wizard=as_wizard)


def test_there_are_three_levels():
    assert bots.LEVELS == ('normal', 'spiteful', 'ruthless')


@pytest.mark.parametrize('levels', [['spiteful'], ['ruthless'], ['normal', 'spiteful', 'ruthless']])
@pytest.mark.parametrize('num_players', [3, 4, 5, 6])
@pytest.mark.parametrize('specials', [(), SPECIAL_KINDS, SPECIAL_KINDS + (Kind.CR7,)])
def test_games_with_every_level_finish(levels, num_players, specials):
    for seed in range(4):
        game = Game([(f'p{i}', f'P{i}') for i in range(num_players)], special_cards=specials,
                    clairvoyance=seed % 2 == 0, rng=random.Random(seed))
        play_game(game, levels)
        assert all(len(p.round_scores) == game.num_rounds for p in game.players)


# ------------------------------------------------------------- helpers for hand-made situations

def card(text: str) -> Card:
    """'sea-5', 'wizard-1', 'bomb', 'cloud' ... -> the card."""
    if '-' in text and text.split('-')[0] in [s.value for s in Suit]:
        suit, value = text.split('-')
        return Card(id=text, kind=Kind.NUMBER, suit=Suit(suit), value=int(value))
    return Card(id=text, kind=Kind(text.split('-')[0]))


def make_view(hand, players, me=0, trick=(), trump=None, round_number=5, **extra):
    """A view as game.view_for returns it, with only the keys the bots read.

    players: list of (bid, tricks_won, score) per seat.
    trick: list of (seat, card text) already played in this trick.
    """
    hand = [card(c) for c in hand]
    view = {
        'round': round_number,
        'my_index': me,
        'my_hand': hand,
        'my_hand_size': len(hand),
        'playable': [c.id for c in hand],
        'allowed_bids': [],
        'trump': trump,
        'trick': [Play(player=seat, card=card(c)) for seat, c in trick],
        'pass_target': (me + 1) % len(players),
        'players': [{'bid': bid, 'bid_change': 0, 'tricks_won': won, 'score': score, 'cards_left': len(hand)}
                    for bid, won, score in players],
    }
    view.update(extra)
    return view


# ------------------------------------------------------------- 2. Spiteful

def test_normal_is_the_default_level():
    view = make_view(['sea-12', 'sea-2'], [(0, 1, 0), (2, 0, 100), (1, 0, 50)], trick=[(1, 'sea-5')])
    assert bots.choose_card(view) == bots.choose_card(view, 'normal')


def test_spiteful_takes_a_trick_from_the_leader_once_its_own_bid_is_lost():
    # I bid 0 but already won a trick: my bid is lost. The leader (seat 1) still needs tricks.
    view = make_view(['sea-12', 'sea-2'], [(0, 1, 0), (2, 0, 100), (1, 0, 50)], trick=[(1, 'sea-5')])
    assert bots.choose_card(view, 'normal')[0] == 'sea-2'      # normal avoids another trick
    assert bots.choose_card(view, 'spiteful')[0] == 'sea-12'   # spiteful takes it from the leader


def test_spiteful_plays_normally_while_its_own_bid_can_still_be_made():
    view = make_view(['sea-12', 'sea-2'], [(0, 0, 0), (2, 0, 100), (1, 0, 50)], trick=[(1, 'sea-5')])
    assert bots.choose_card(view, 'spiteful')[0] == 'sea-2'


def test_spiteful_leaves_the_trick_to_a_leader_who_has_enough_already():
    # My bid (3) can no longer be made with 2 cards. The leader has exactly made their bid:
    # one more trick would cost them, so I do not take it.
    view = make_view(['sea-12', 'sea-2'], [(3, 0, 0), (1, 1, 100), (1, 0, 50)], trick=[(1, 'sea-5')])
    assert bots.choose_card(view, 'normal')[0] == 'sea-12'
    assert bots.choose_card(view, 'spiteful')[0] == 'sea-2'


def test_when_spiteful_leads_the_score_it_targets_the_closest_chaser():
    view = make_view(['sea-12', 'sea-2'], [(0, 1, 200), (1, 0, 10), (2, 0, 150)], trick=[(2, 'sea-5')])
    assert bots.choose_card(view, 'spiteful')[0] == 'sea-12'


# ------------------------------------------------------------- 3. Ruthless

def test_ruthless_bombs_a_trick_the_leader_needs():
    # Leader (seat 1) wins with Sea 13 and needs tricks. I cannot beat it, so I blow the trick up.
    view = make_view(['bomb', 'sea-2'], [(1, 0, 0), (2, 0, 100), (1, 0, 50)], trick=[(1, 'sea-13')])
    assert bots.choose_card(view, 'normal')[0] == 'sea-2'
    assert bots.choose_card(view, 'ruthless')[0] == 'bomb'


def test_ruthless_does_not_bomb_a_trick_the_leader_does_not_want():
    view = make_view(['bomb', 'sea-2'], [(1, 0, 0), (1, 1, 100), (1, 0, 50)], trick=[(1, 'sea-13')])
    assert bots.choose_card(view, 'ruthless')[0] == 'sea-2'


def test_ruthless_gives_the_cloud_to_a_leader_who_needs_one_more_trick():
    # The leader wins with a Wizard and needs exactly one more trick. With the Cloud in it they reach
    # their bid but then have to change it by one, so they miss it again.
    view = make_view(['cloud', 'sea-2'], [(0, 0, 0), (2, 1, 100), (1, 0, 50)], trick=[(1, 'wizard-1')])
    card_id, suit, _ = bots.choose_card(view, 'ruthless')
    assert card_id == 'cloud' and suit is not None


def test_ruthless_wins_cheaply_when_it_plays_last():
    view = make_view(['sea-13', 'sea-9', 'sea-1'], [(1, 0, 0), (0, 0, 100), (0, 0, 50)],
                     trick=[(1, 'sea-5'), (2, 'sea-8')])
    assert bots.choose_card(view, 'normal')[0] == 'sea-13'
    assert bots.choose_card(view, 'ruthless')[0] == 'sea-9'   # Sea 9 is enough, the 13 is kept


def test_ruthless_dumps_its_highest_safe_card_when_it_wants_to_lose():
    view = make_view(['sea-13', 'sea-9', 'sea-1'], [(0, 0, 0), (0, 0, 100), (0, 0, 50)],
                     trick=[(1, 'sea-10')])
    assert bots.choose_card(view, 'normal')[0] == 'sea-1'
    assert bots.choose_card(view, 'ruthless')[0] == 'sea-9'   # loses as well, and gets rid of the 9


def test_ruthless_passes_a_winner_to_a_left_neighbour_who_has_enough():
    view = make_view(['dragon', 'sea-2', 'jester-1'], [(3, 0, 0), (1, 1, 100), (1, 0, 50)], must_pass=True)
    assert bots.choose_pass(view, 'normal') == 'jester-1'      # normal keeps its Dragon, it needs tricks
    assert bots.choose_pass(view, 'ruthless') == 'dragon'      # forces an extra trick on the leader


def test_ruthless_passes_rubbish_to_a_left_neighbour_who_needs_tricks():
    view = make_view(['dragon', 'sea-2', 'jester-1'], [(0, 0, 0), (2, 0, 100), (1, 0, 50)], must_pass=True)
    assert bots.choose_pass(view, 'normal') == 'dragon'
    assert bots.choose_pass(view, 'ruthless') == 'jester-1'


def test_ruthless_as_last_bidder_makes_the_round_tight_for_the_leader():
    # Round 3, the others bid 1 + 1. My estimate is 1, but 1 is not allowed (the bids would add up to 3).
    # Normal takes the lower neighbour 0. Ruthless takes 2: the leader bid 1, and now more tricks
    # are wanted than exist, so the leader has to fight for theirs.
    view = make_view(['sea-13', 'sun-3', 'olive-4'], [(None, 0, 0), (1, 0, 100), (1, 0, 50)],
                     round_number=3, allowed_bids=[0, 2, 3])
    assert bots.choose_bid(view, 'normal') == 0
    assert bots.choose_bid(view, 'ruthless') == 2


# ------------------------------------------------------------- 4. lobby

def test_the_host_picks_a_level_when_adding_a_bot():
    lobby = LobbyRegistry(clock=FakeClock()).create('host', 'Keno')
    lobby.add_bot('host')
    lobby.add_bot('host', 'spiteful')
    lobby.add_bot('host', 'ruthless')
    assert [m.level for m in lobby.members if m.is_bot] == ['normal', 'spiteful', 'ruthless']


def test_an_unknown_level_is_rejected():
    lobby = LobbyRegistry(clock=FakeClock()).create('host', 'Keno')
    with pytest.raises(LobbyError):
        lobby.add_bot('host', 'evil')
    assert len(lobby.members) == 1


def test_bots_saved_before_levels_existed_play_normal():
    member = Member('bot-1', 'Marta', ready=True, is_bot=True)
    del member.__dict__['level']                      # how an old saved bot looks
    assert pickle.loads(pickle.dumps(member)).level == 'normal'


def test_the_lobby_lets_each_bot_play_with_its_own_level(monkeypatch):
    seen = []
    original = bots.choose_bid

    def spy(view, level='normal'):
        seen.append(level)
        return original(view, level)

    monkeypatch.setattr(bots, 'choose_bid', spy)
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = registry.create('host', 'Keno')
    lobby.connect('host')
    lobby.add_bot('host', 'ruthless')
    lobby.add_bot('host', 'ruthless')
    lobby.set_ready('host', True)
    for _ in range(50):
        clock.now += 2.0
        registry.tick_all()
    assert seen and set(seen) == {'ruthless'}


def test_practice_against_bots_of_one_level():
    lobby = start_practice(LobbyRegistry(clock=FakeClock()), 'me', 'Keno', 4, 'spiteful')
    assert lobby.game is not None
    assert [m.level for m in lobby.members if m.is_bot] == ['spiteful'] * 3
