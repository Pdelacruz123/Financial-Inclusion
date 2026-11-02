"""Checks for the SQL views in sql/.

Requires running first:  python src/load_indicator.py
"""

COUNTRY = "PER"  # example country
INDICATOR = "FX.OWN.TOTL.ZS"


def change_rows(con):
    return con.execute(
        """
        SELECT year, previous_year, change
        FROM v_indicator_change
        WHERE country_iso3 = ? AND indicator = ?
        ORDER BY year
        """,
        [COUNTRY, INDICATOR],
    ).fetchall()


def test_one_row_per_findex_edition(con):
    years = [year for year, _, _ in change_rows(con)]
    assert years == [2011, 2014, 2017, 2021, 2024]


def test_first_edition_has_no_previous(con):
    _, previous_year, change = change_rows(con)[0]
    assert previous_year is None and change is None


def test_change_2021_to_2024(con):
    year, previous_year, change = change_rows(con)[-1]
    assert (year, previous_year) == (2024, 2021)
    assert 1 <= change <= 3  # 59.3 - 57.5 = 1.8 points


def test_coverage_counts_every_loaded_row(con):
    with_data, possible = con.execute(
        "SELECT sum(cells_with_data), sum(possible_cells) FROM v_coverage"
    ).fetchone()
    assert with_data == con.execute("SELECT count(*) FROM observations").fetchone()[0]
    assert with_data <= possible
