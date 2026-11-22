"""Feedback from the rehearsal (21.11.):
1. Against bots only, there is no time limit: you may think or take a break as long as you like.
2. If a special card is turned up as the trump card, there is simply no trump (only a Wizard lets the dealer choose)."""
import pytest

from game.cards import Card, Kind, Suit
from game.engine import Phase
from game.lobby import TURN_LIMIT, LobbyRegistry
from game.rules import dealer_chooses_trump, trump_from_card
from views.start import start_practice


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def run(registry, clock, seconds):
    for _ in range(int(seconds / 0.5)):
        clock.now += 0.5
        registry.tick_all()


# ---------------------------------------------------------------- 1. No time limit against bots

def practice(players=4):
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = start_practice(registry, 'me', 'Me', players)
    lobby.connect('me')
    run(registry, clock, 30)                     # the bots make their first moves
    return registry, clock, lobby


def test_no_countdown_when_playing_only_against_bots():
    registry, clock, lobby = practice()
    assert lobby.waiting_on() == ['me']
    assert lobby.seconds_left() is None
    assert lobby.turn_timer() is None


def test_against_bots_you_can_think_as_long_as_you_like():
    registry, clock, lobby = practice()
    phase, hand = lobby.game.phase, len(lobby.game.players[0].hand)
    run(registry, clock, TURN_LIMIT * 5)         # 10 minutes, still at the table
    assert lobby.waiting_on() == ['me']
    assert (lobby.game.phase, len(lobby.game.players[0].hand)) == (phase, hand)   # nothing was played for me


def test_against_bots_a_long_break_keeps_the_game_and_your_move():
    registry, clock, lobby = practice()
    phase = lobby.game.phase
    lobby.disconnect('me')                       # e.g. "Back to start" or the phone goes to sleep
    run(registry, clock, 10 * 60)
    assert registry.get(lobby.code) is lobby     # the game still exists
    lobby.connect('me')
    run(registry, clock, 5)
    assert lobby.game.phase == phase and lobby.waiting_on() == ['me']   # and it is still my move


def test_with_two_humans_the_time_limit_still_applies():
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = registry.create('a', 'Ana')
    lobby.join('b', 'Ben')
    lobby.add_bot('a')
    for member in ('a', 'b'):
        lobby.connect(member)
        lobby.set_ready(member, True)
    run(registry, clock, 5)
    assert lobby.seconds_left() is not None


def test_when_the_other_human_leaves_for_good_the_time_limit_stops():
    clock = FakeClock()
    registry = LobbyRegistry(clock=clock)
    lobby = registry.create('a', 'Ana')
    lobby.join('b', 'Ben')
    lobby.add_bot('a')
    for member in ('a', 'b'):
        lobby.connect(member)
        lobby.set_ready(member, True)
    lobby.leave('b')                             # Ben's seat goes to a bot: Ana now plays only against bots
    run(registry, clock, 5)
    assert lobby.seconds_left() is None


# ---------------------------------------------------------------- 2. Special card as trump card

SPECIALS = [Kind.SHAPESHIFTER, Kind.DRAGON, Kind.FAIRY, Kind.BOMB, Kind.WEREWOLF, Kind.JUGGLER, Kind.CLOUD, Kind.CR7]


@pytest.mark.parametrize('kind', SPECIALS)
def test_special_card_turned_up_means_no_trump(kind):
    card = Card(99, kind)
    assert trump_from_card(card) is None
    assert not dealer_chooses_trump(card)


def test_a_wizard_turned_up_still_lets_the_dealer_choose():
    assert dealer_chooses_trump(Card(99, Kind.WIZARD))


def test_a_jester_turned_up_still_means_no_trump():
    assert not dealer_chooses_trump(Card(99, Kind.JESTER))
    assert trump_from_card(Card(99, Kind.JESTER)) is None


def test_the_rules_page_says_a_special_card_means_no_trump():
    from views.rules import rules_content
    assert 'A Jester or a special card means no trump' in rules_content()
