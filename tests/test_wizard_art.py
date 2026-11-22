"""Bonus: the Wizard cards show Moritz, the Shapeshifter shows Keno and the Jester cards show Erik
(AI-generated portraits, with their consent)."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / 'static' / 'styles.css').read_text()
PORTRAITS = pytest.mark.parametrize('kind, image', [('wizard', 'wizard-moritz.jpg'),
                                                    ('shapeshifter', 'shapeshifter-keno.jpg'),
                                                    ('jester', 'jester-erik.jpg')])


@PORTRAITS
def test_the_portrait_is_a_small_jpeg(kind, image):
    data = (ROOT / 'static' / 'card-art' / image).read_bytes()
    assert data[:3] == b'\xff\xd8\xff'                 # JPEG
    assert len(data) < 300_000                          # loads quickly on phones


@PORTRAITS
def test_the_cards_use_the_portrait(kind, image):
    rule = re.search(rf'\.art-{kind} \.special-art\s*\{{([^}}]*)\}}', CSS)
    assert rule is not None
    assert f'card-art/{image}' in rule.group(1)


@PORTRAITS
def test_the_readme_names_the_source_of_the_portrait(kind, image):
    readme = (ROOT / 'README.md').read_text()
    assert kind.capitalize() in readme and image in readme
