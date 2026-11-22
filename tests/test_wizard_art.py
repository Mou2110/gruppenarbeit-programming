"""Bonus: the Wizard and Jester cards show team members (AI-generated portraits, made with their consent)."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'static' / 'styles.css').read_text()

# (card kind, portrait file)
PORTRAITS = [('wizard', 'wizard-moritz.jpg'), ('jester', 'jester-erik.jpg')]


@pytest.mark.parametrize('kind, file', PORTRAITS)
def test_the_portrait_is_a_small_jpeg(kind, file):
    data = (ROOT / 'static' / 'card-art' / file).read_bytes()
    assert data[:3] == b'\xff\xd8\xff'                 # JPEG
    assert len(data) < 300_000                          # loads quickly on phones


@pytest.mark.parametrize('kind, file', PORTRAITS)
def test_the_cards_use_the_portrait(kind, file):
    rule = re.search(rf'\.art-{kind} \.special-art\s*\{{([^}}]*)\}}', CSS)
    assert rule is not None
    assert f'card-art/{file}' in rule.group(1)


@pytest.mark.parametrize('kind, file', PORTRAITS)
def test_the_readme_names_the_source_of_the_portrait(kind, file):
    readme = (ROOT / 'README.md').read_text()
    assert kind.capitalize() in readme and file in readme
