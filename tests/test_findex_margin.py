"""Margins of error for Findex (data/findex_sample.csv and v_findex_change).

Requires running first:  python src/load_indicator.py
"""

import pytest

COUNTRY = "PER"  # example country


def test_formula_matches_published_margins(con):
    # The only mismatch is a typo in the 2021 methodology (Brazil: 1.5 printed, 4.8 by formula).
    mismatches = con.execute(
        """
        SELECT country_iso3, edition FROM findex_sample
        WHERE round(100 * 1.96 * sqrt(0.25 / interviews) * sqrt(design_effect), 1)
              <> published_margin
        """
    ).fetchall()
    assert mismatches == [("BRA", 2021)]


def change_row(con, indicator, edition):
    return con.execute(
        """
        SELECT margin, change, change_margin, significant FROM v_findex_change
        WHERE country_iso3 = ? AND indicator = ? AND edition = ?
        """,
        [COUNTRY, indicator, edition],
    ).fetchone()


def test_margin_2024(con):
    margin, _, _, _ = change_row(con, "FX.OWN.TOTL.ZS", 2024)
    assert margin == pytest.approx(3.6, abs=0.05)  # published in Table A.1


def test_change_2021_to_2024_is_not_significant(con):
    _, change, change_margin, significant = change_row(con, "FX.OWN.TOTL.ZS", 2024)
    assert change == pytest.approx(1.8, abs=0.1)
    assert change_margin == pytest.approx(5.1, abs=0.1)
    assert significant is False


def test_editions_without_sample_have_no_margin(con):
    margin, _, change_margin, significant = change_row(con, "FX.OWN.TOTL.ZS", 2017)
    assert (margin, change_margin, significant) == (None, None, None)


def test_subgroups_have_no_margin(con):
    margin, _, _, significant = change_row(con, "FX.OWN.TOTL.FE.ZS", 2024)
    assert (margin, significant) == (None, None)
