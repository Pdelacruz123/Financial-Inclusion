"""findex_edition: maps a survey year to its Findex edition."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from load_indicator import findex_edition  # noqa: E402


@pytest.mark.parametrize("survey_year, edition", [(2021, 2021), (2022, 2021), (2024, 2024), (2025, 2024)])
def test_known_editions(survey_year, edition):
    assert findex_edition(survey_year) == edition


def test_unknown_edition_fails_loudly():
    # A future edition must not be filed under 2024 without anyone noticing.
    with pytest.raises(ValueError, match="FINDEX_EDITIONS"):
        findex_edition(2027)
