"""Tests for the rules on the start page and in the game.

On the start page the rules are one collapsible block "Rules" (HTML <details>), closed at first;
when opened, all topics are shown. The bonus card CR7 has its own short section after the special cards.
"""
from views.rules import RULES, rules_content, rules_toggle


def test_the_start_page_has_one_rules_block_that_starts_closed():
    html = rules_toggle()
    assert html.count('<details class="rules-toggle"') == 1
    assert '<summary' in html and 'Rules' in html
    assert ' open' not in html.split('>')[0]


def test_inside_the_block_every_topic_is_shown_at_once():
    html = rules_toggle()
    for title, text in RULES:
        assert f'<h3>{title}</h3>' in html and text in html


def test_the_rules_during_a_game_are_the_same_topics_without_the_block():
    html = rules_content()
    assert 'rules-toggle' not in html
    assert all(text in html for _, text in RULES)


def test_the_extra_special_card_hides_in_its_own_closed_section_after_the_special_cards():
    html = rules_content()
    special = html.index('<h3>Special cards (optional)</h3>')
    extra = html.index('<details class="rule extra">')
    assert special < extra
    assert 'CR7' not in html[special:extra]            # not listed among the special cards
    section = html[extra:]
    assert section.startswith('<details class="rule extra"><summary><h3>(Extra special card)</h3></summary>')
    assert '<b>CR7</b> · Always wins.' in section
    assert section.count('<details') == 1 and ' open' not in section.split('>')[0]


def test_the_extra_special_card_sits_inside_the_special_cards_block():
    # So it stays in the same column, right under the special cards (not alone in the other column).
    html = rules_content()
    assert html.endswith('</details></div>')
    block = html[html.index('<h3>Special cards (optional)</h3>'):]
    assert block.index('<details class="rule extra">') < block.index('</details></div>')


def test_the_rules_say_how_to_see_what_a_special_card_does_during_a_game():
    html = rules_content()
    block = html[html.index('<h3>Special cards (optional)</h3>'):]
    assert 'Click a special card' in block and '?' in block
