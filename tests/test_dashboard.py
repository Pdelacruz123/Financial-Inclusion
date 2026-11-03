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


def test_evolution_verdicts(con):
    app = AppTest.from_file(str(DASHBOARD), default_timeout=30).run()
    assert not app.exception
    table = next(df.value for df in app.dataframe if "verdict" in df.value.columns)
    verdicts = dict(zip(table["country"], table["verdict"]))
    assert verdicts["Peru"] == "● No significant change"  # +1.8 vs ±5.1
    assert verdicts["Panama"] == "▲ Increase"
    assert verdicts["Bolivia"] == "▼ Decrease"


def test_gaps_for_women(con):
    app = AppTest.from_file(str(DASHBOARD), default_timeout=30).run()
    table = next(df.value for df in app.dataframe if "gap" in df.value.columns)
    gap = dict(zip(table["name"], table["gap"]))
    assert abs(gap["Peru"] - 3.1) < 0.1  # all adults 59.3, women 56.2 (2024)


def test_infrastructure_pairs(con):
    app = AppTest.from_file(str(DASHBOARD), default_timeout=30).run()
    pairs = next(df.value for df in app.dataframe if "supply_year" in df.value.columns)
    assert "Brazil" in set(pairs["name"])
    # Venezuela's latest ATM figure is from 2015, too old to pair with a 2024 survey.
    assert "Venezuela, RB" not in set(pairs["name"])
    assert (pairs["survey_year"] - pairs["supply_year"]).between(0, 2).all()


def test_context_runs_for_every_indicator(con):
    app = AppTest.from_file(str(DASHBOARD), default_timeout=30).run()
    for indicator in ["IT.NET.USER.ZS", "IT.CEL.SETS.P2", "FS.AST.PRVT.GD.ZS", "NY.GDP.PCAP.CD"]:
        app.radio(key="context_indicator").set_value(indicator).run()
        assert not app.exception, indicator
    # Credit must always carry its warning: it measures depth, not inclusion.
    app.radio(key="context_indicator").set_value("FS.AST.PRVT.GD.ZS").run()
    assert any("Financial depth, not inclusion" in m.value for m in app.markdown)


def test_dashboard_runs_for_every_group(con):
    app = AppTest.from_file(str(DASHBOARD), default_timeout=30).run()
    assert not app.exception
    # set_value takes the radio's value (indicator code), not its displayed label.
    for indicator in ["FX.OWN.TOTL.ZS", "FX.OWN.TOTL.FE.ZS", "FX.OWN.TOTL.40.ZS"]:
        app.radio[0].set_value(indicator).run()
        assert not app.exception, indicator
