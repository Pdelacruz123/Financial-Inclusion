"""Control values for the example country (Findex 2025 book, Table B.1).

Requires running first:  python src/load_indicator.py
"""

from pathlib import Path

import duckdb
import pytest

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "monitor.duckdb"

COUNTRY = "PER"  # example country


@pytest.fixture
def con():
    """Open the database read-only and close it when the test ends."""
    if not DB_PATH.exists():
        pytest.fail(f"{DB_PATH} does not exist. Run first: python src/load_indicator.py")
    connection = duckdb.connect(str(DB_PATH), read_only=True)
    yield connection
    connection.close()


def account_ownership(con, year):
    row = con.execute(
        """
        SELECT value FROM observations
        WHERE country_iso3 = ? AND indicator = 'FX.OWN.TOTL.ZS' AND year = ?
        """,
        [COUNTRY, year],
    ).fetchone()
    assert row is not None, f"No data for {COUNTRY} in {year}"
    return row[0]


def test_account_ownership_2024_is_59(con):
    # Table B.1 publishes 59 (rounded); accept +-0.5.
    assert 58.5 <= account_ownership(con, 2024) <= 59.5


def test_account_ownership_2021_is_57(con):
    assert 56.5 <= account_ownership(con, 2021) <= 57.5
