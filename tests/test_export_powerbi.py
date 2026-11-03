"""Power BI export: the star schema must have no orphan or duplicated rows.

An orphan fact row (a country or indicator missing from its dimension) shows up
in Power BI as "(Blank)" without any error.

Requires running first:  python src/load_indicator.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from export_powerbi import export  # noqa: E402


def read(con, folder, table):
    return con.execute(f"SELECT * FROM '{(folder / f'{table}.parquet').as_posix()}'").df()


def test_star_schema(con, tmp_path):
    export(con, tmp_path)
    fact = read(con, tmp_path, "fact_observations")
    countries = read(con, tmp_path, "dim_country")
    indicators = read(con, tmp_path, "dim_indicator")
    years = read(con, tmp_path, "dim_year")

    # Same rows as the database: the margin join must not duplicate or drop any.
    assert len(fact) == con.execute("SELECT count(*) FROM observations").fetchone()[0]
    assert not fact.duplicated(["country_iso3", "indicator", "year"]).any()

    # Every key in the fact table exists in its dimension, once.
    assert set(fact["country_iso3"]) <= set(countries["country_iso3"])
    assert set(fact["indicator"]) <= set(indicators["indicator"])
    assert set(fact["year"]) <= set(years["year"])
    assert countries["country_iso3"].is_unique and indicators["indicator"].is_unique

    # The margin arrives for total account ownership (example country, 2024: about 3.6).
    margin = fact.query("country_iso3 == 'PER' and indicator == 'FX.OWN.TOTL.ZS' and year == 2024")
    assert abs(margin["margin"].iloc[0] - 3.6) < 0.05
