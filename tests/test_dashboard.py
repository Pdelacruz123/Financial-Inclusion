"""Data gaps view and a headless run of the Streamlit dashboard.

Requires running first:  python src/load_indicator.py
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

DASHBOARD = Path(__file__).resolve().parent.parent / "src" / "dashboard.py"


def gap(con, country, indicator):
    return con.execute(
        "SELECT gap, latest_period FROM v_data_gaps WHERE country_iso3 = ? AND indicator = ?",
        [country, indicator],
    ).fetchone()


def test_country_without_findex_is_flagged(con):
    assert gap(con, "CUB", "FX.OWN.TOTL.ZS") == ("no data", None)


def test_outdated_findex_is_flagged(con):
    assert gap(con, "HTI", "FX.OWN.TOTL.ZS") == ("outdated", 2017)


def test_up_to_date_country_is_not_flagged(con):
    assert gap(con, "PER", "FX.OWN.TOTL.ZS") is None


def test_dashboard_runs_for_every_group(con):
    app = AppTest.from_file(str(DASHBOARD), default_timeout=30).run()
    assert not app.exception
    # set_value takes the radio's value (indicator code), not its displayed label.
    for indicator in ["FX.OWN.TOTL.ZS", "FX.OWN.TOTL.FE.ZS", "FX.OWN.TOTL.40.ZS"]:
        app.radio[0].set_value(indicator).run()
        assert not app.exception, indicator
