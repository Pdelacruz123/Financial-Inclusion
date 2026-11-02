"""Control values for the example country, from primary sources.

- Total: Findex 2025 book, Table B.1 (published rounded).
- Women and poorest 40%: official GlobalFindexDatabase2025.csv (Table B.1 does not include them).

Requires running first:  python src/load_indicator.py
"""

import pytest

COUNTRY = "PER"  # example country


def value(con, indicator, year):
    row = con.execute(
        """
        SELECT value FROM observations
        WHERE country_iso3 = ? AND indicator = ? AND year = ?
        """,
        [COUNTRY, indicator, year],
    ).fetchone()
    assert row is not None, f"No data for {COUNTRY} {indicator} in {year}"
    return row[0]


@pytest.mark.parametrize(
    "indicator, year, expected",
    [
        ("FX.OWN.TOTL.ZS", 2024, 59),       # Table B.1
        ("FX.OWN.TOTL.ZS", 2021, 57),       # Table B.1 (2021 edition)
        ("FX.OWN.TOTL.FE.ZS", 2024, 56.18),  # official file
        ("FX.OWN.TOTL.40.ZS", 2024, 44.62),  # official file
    ],
)
def test_control_value(con, indicator, year, expected):
    # Accept +-0.5: Table B.1 rounds to whole numbers.
    assert value(con, indicator, year) == pytest.approx(expected, abs=0.5)
