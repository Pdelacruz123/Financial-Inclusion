"""Control values for the example country (Findex 2025 book, Table B.1).

Requires running first:  python src/load_indicator.py
"""

COUNTRY = "PER"  # example country


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
