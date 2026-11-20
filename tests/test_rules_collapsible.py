"""Tests for the collapsible rules on the start page.

Each rule section can be opened and closed on its own (HTML <details>), so the start page stays short.
The rules dialog during a game keeps showing everything at once.
"""
from views.rules import RULES, rules_content


def test_on_the_start_page_every_section_can_be_opened_and_closed():
    html = rules_content(collapsible=True)
    # the cards, every rule, and the special cards
    assert html.count('<details') == html.count('</details>') == len(RULES) + 2
    for title, _ in RULES:
        assert f'<summary><h3>{title}</h3></summary>' in html


def test_all_sections_start_closed():
    assert ' open' not in rules_content(collapsible=True)


def test_nothing_is_lost_when_collapsible():
    html = rules_content(collapsible=True)
    for title, text in RULES:
        assert text in html
    assert 'Special cards (optional)' in html and 'Bomb' in html


def test_the_rules_during_a_game_stay_fully_open():
    assert '<details' not in rules_content()
