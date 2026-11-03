"""Export a star schema for Power BI as Parquet files in powerbi/.

Power BI has no DuckDB connector, but it reads Parquet, which also keeps
column types (no decimal comma vs point problems on Spanish Windows).

    fact_observations   one row per country, indicator and year
    dim_country         one row per country
    dim_indicator       one row per indicator, with its group
    dim_year            one row per year

Usage:  python src/export_powerbi.py   (run src/load_indicator.py first)
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "monitor.duckdb"
OUT_DIR = ROOT / "powerbi"

TABLES = {
    # margin: Findex margin of error, only for total account ownership in 2021 and 2024.
    "fact_observations": """
        SELECT o.country_iso3, o.indicator, o.year, o.value, o.edition, o.survey_year, f.margin
        FROM observations AS o
        LEFT JOIN v_findex_change AS f
            ON f.country_iso3 = o.country_iso3
            AND f.indicator = o.indicator
            AND f.survey_year = o.year
    """,
    "dim_country": "SELECT country_iso3, name FROM countries",
    "dim_indicator": """
        SELECT
            indicator,
            name,
            CASE
                WHEN indicator LIKE 'FX.%' THEN 'Demand (Findex)'
                WHEN indicator LIKE 'FB.%' THEN 'Supply (IMF FAS)'
                WHEN indicator LIKE 'IT.%' THEN 'Connectivity (ITU)'
                ELSE 'Context'
            END AS indicator_group
        FROM indicators
    """,
    "dim_year": """
        SELECT range AS year
        FROM range((SELECT min(year) FROM observations), (SELECT max(year) FROM observations) + 1)
    """,
}


def export(con, out_dir=OUT_DIR):
    out_dir.mkdir(exist_ok=True)
    for name, sql in TABLES.items():
        con.execute(f"COPY ({sql}) TO '{(out_dir / f'{name}.parquet').as_posix()}' (FORMAT parquet)")


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        export(con)
    finally:
        con.close()
    for name in TABLES:
        print(f"powerbi/{name}.parquet")


if __name__ == "__main__":
    main()
