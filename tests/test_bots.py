"""Complete games with bots only must run without errors – with and without special cards."""
import random

import pytest

from game import bots
from game.cards import SPECIAL_KINDS
from game.engine import Game, Phase


def play_bot_game(game: Game) -> None:
    """Lets only bots play until the game is over."""
    while game.phase != Phase.GAME_OVER:
        if game.phase == Phase.ROUND_OVER:
            game.next_round()
            continue
        if game.phase == Phase.PASSING:
            for player in game.players:
                if game.must_pass(player.id):
                    game.pass_card(player.id, bots.choose_pass(game.view_for(player.id)))
            continue
        player = game.players[game.current]
        view = game.view_for(player.id)
        if game.phase in (Phase.WEREWOLF, Phase.CHOOSING_TRUMP):
            game.choose_trump(player.id, bots.choose_trump(view))
        elif game.phase == Phase.BIDDING:
            game.place_bid(player.id, bots.choose_bid(view))
        elif game.phase == Phase.ADJUSTING:
            game.adjust_bid(player.id, bots.choose_adjustment(view))
        elif game.awaiting_choice is not None:
            suit, as_wizard = bots.declare_played_card(view)
            game.declare(player.id, suit=suit, as_wizard=as_wizard)
        else:
            card_id, suit, as_wizard = bots.choose_card(view)
            game.play_card(player.id, card_id, suit=suit, as_wizard=as_wizard)


@pytest.mark.parametrize('num_players', [3, 4, 5, 6])
@pytest.mark.parametrize('specials', [(), SPECIAL_KINDS])
def test_bots_finish_a_game(num_players, specials):
    for seed in range(5):
        players = [(f'p{i}', f'P{i}') for i in range(num_players)]
        game = Game(players, special_cards=specials, rng=random.Random(seed))
        play_bot_game(game)
        assert game.round_number == 60 // num_players
        assert all(len(p.round_scores) == game.num_rounds for p in game.players)


@pytest.mark.parametrize('specials', [(), SPECIAL_KINDS])
def test_bots_with_clairvoyance(specials):
    for seed in range(5):
        game = Game([(f'p{i}', f'P{i}') for i in range(4)], special_cards=specials, clairvoyance=True,
                    rng=random.Random(seed))
        play_bot_game(game)
        assert game.phase == Phase.GAME_OVER
