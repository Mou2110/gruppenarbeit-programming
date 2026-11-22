"""Bonus: the Wizard cards show a team member as a wizard (AI-generated portrait, with his consent)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / 'static' / 'card-art' / 'wizard-moritz.jpg'
CSS = (ROOT / 'static' / 'styles.css').read_text()


def test_the_wizard_portrait_is_a_small_jpeg():
    data = ART.read_bytes()
    assert data[:3] == b'\xff\xd8\xff'                 # JPEG
    assert len(data) < 300_000                          # loads quickly on phones


def test_wizard_cards_use_the_portrait():
    rule = re.search(r'\.art-wizard \.special-art\s*\{([^}]*)\}', CSS)
    assert rule is not None
    assert 'card-art/wizard-moritz.jpg' in rule.group(1)


def test_the_readme_names_the_source_of_the_portrait():
    readme = (ROOT / 'README.md').read_text()
    assert 'Wizard' in readme and 'wizard-moritz.jpg' in readme
