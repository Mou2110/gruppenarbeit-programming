"""Tests for the rules on the start page and in the game.

On the start page the rules are one collapsible block "Rules" (HTML <details>), closed at first;
when opened, all topics are shown. The bonus card CR7 has its own short section after the special cards.
"""
from views.rules import RULES, rules_content, rules_toggle


def test_the_start_page_has_one_rules_block_that_starts_closed():
    html = rules_toggle()
    assert html.count('<details') == 1
    assert '<summary' in html and 'Rules' in html
    assert ' open' not in html.split('>')[0]


def test_inside_the_block_every_topic_is_shown_at_once():
    html = rules_toggle()
    for title, text in RULES:
        assert f'<h3>{title}</h3>' in html and text in html


def test_the_rules_during_a_game_are_the_same_topics_without_the_block():
    html = rules_content()
    assert '<details' not in html
    assert all(text in html for _, text in RULES)


def test_the_bonus_card_has_its_own_section_after_the_special_cards():
    html = rules_content()
    special, bonus = html.index('<h3>Special cards (optional)</h3>'), html.index('<h3>Bonus card</h3>')
    assert special < bonus
    assert 'CR7' not in html[special:bonus]            # not listed among the special cards
    assert '<b>CR7</b> · Always wins.' in html[bonus:]
