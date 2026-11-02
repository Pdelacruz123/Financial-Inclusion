"""Download the World Bank indicators listed in config.yaml and store them in DuckDB.

Steps, once per indicator (all countries in one request):
1. Call the World Bank API v2 (with pauses and retries).
2. Save the raw JSON to data/raw/ (keeps a history of series revisions).
3. Turn the response into a pandas table.
4. Replace this indicator's rows for those countries in the DuckDB `observations` table.
Then save the country names, load the Findex sample sizes
(data/findex_sample.csv) and (re)create the SQL views defined in sql/.

Usage:  python src/load_indicator.py
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests
import yaml

YEAR_RANGE = "2011:2024"
PAUSE_BETWEEN_REQUESTS_SEC = 1  # usage limits are not documented, so be gentle

API_URL = "https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}"

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "monitor.duckdb"
SQL_DIR = ROOT / "sql"
FINDEX_SAMPLE_PATH = ROOT / "data" / "findex_sample.csv"

COLUMNS = ["country_iso3", "indicator", "year", "edition", "survey_year", "value", "extracted_at"]

# shortcut: hardcoded list, add the next Findex edition here when it is published.
FINDEX_EDITIONS = (2011, 2014, 2017, 2021, 2024)


def findex_edition(survey_year):
    """Some countries of an edition were surveyed a year later (e.g. 2021 edition, surveyed in 2022)."""
    edition = max(edition for edition in FINDEX_EDITIONS if edition <= survey_year)
    # Fail loudly instead of silently filing a new edition under the previous one.
    if survey_year - edition > 1:
        raise ValueError(
            f"Survey year {survey_year} matches no known Findex edition; "
            "add the new edition to FINDEX_EDITIONS."
        )
    return edition


def load_config(path=CONFIG_PATH):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def fetch(countries, indicator, attempts=3, pause_sec=2):
    """Request one indicator for several countries and return the parsed JSON.

    On failure (network down, 5xx error...) wait and retry. The wait grows
    with each attempt: 2 s, 4 s, 6 s.
    """
    url = API_URL.format(countries=";".join(countries), indicator=indicator)
    params = {"format": "json", "date": YEAR_RANGE, "per_page": 1000}

    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()  # raises if the HTTP status is not 200
            data = response.json()
            break
        except requests.RequestException as error:
            if attempt == attempts:
                raise
            wait = pause_sec * attempt
            print(f"Attempt {attempt} failed ({error}). Retrying in {wait} s...")
            time.sleep(wait)

    # Normal response: [metadata, [rows]]. With an invalid code the API still
    # answers 200 but with [{"message": [...]}], so we check it here.
    if len(data) < 2 or data[1] is None:
        raise ValueError(f"The API returned no data for {indicator}: {data}")
    if data[0]["pages"] > 1:
        raise ValueError("The response has more than one page; pagination is missing.")

    return data


def save_raw(data, indicator, extracted_at):
    """Save the JSON exactly as received. The file name carries the UTC date and time."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = extracted_at.strftime("%Y-%m-%dT%H%M%SZ")  # no ":" because Windows rejects it
    path = RAW_DIR / f"{indicator}_{stamp}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def to_table(data, extracted_at):
    """Turn the API rows into a DataFrame with our columns.

    Years with no value (null) are dropped: Findex is triennial and is not interpolated.
    """
    rows = []
    for record in data[1]:
        if record["value"] is None:
            continue
        indicator = record["indicator"]["id"]
        year = int(record["date"])
        is_findex = indicator.startswith("FX.")  # only Findex has survey editions
        rows.append(
            {
                "country_iso3": record["countryiso3code"],
                "indicator": indicator,
                "year": year,
                "edition": findex_edition(year) if is_findex else None,
                "survey_year": year if is_findex else None,  # for Findex the API date is the survey year
                "value": float(record["value"]),
                "extracted_at": extracted_at.replace(tzinfo=None),  # stored in UTC
            }
        )
    table = pd.DataFrame(rows, columns=COLUMNS)
    for column in ("edition", "survey_year"):
        table[column] = table[column].astype("Int64")  # integer that allows nulls
    return table


def save_to_duckdb(table, countries, indicator, db_path=DB_PATH):
    """Replace this indicator's rows for these countries so re-running does not duplicate them."""
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS observations (
                country_iso3  VARCHAR   NOT NULL,
                indicator     VARCHAR   NOT NULL,
                year          INTEGER   NOT NULL,
                edition       INTEGER,
                survey_year   INTEGER,
                value         DOUBLE    NOT NULL,
                extracted_at  TIMESTAMP NOT NULL,  -- UTC time of the download
                PRIMARY KEY (country_iso3, indicator, year)
            )
            """
        )
        # One transaction: either the whole delete + insert happens, or nothing.
        con.execute("BEGIN TRANSACTION")
        con.execute(
            "DELETE FROM observations WHERE indicator = ? AND list_contains(?, country_iso3)",
            [indicator, countries],
        )
        con.register("new_rows", table)  # lets DuckDB read the DataFrame by name
        con.execute(f"INSERT INTO observations SELECT {', '.join(COLUMNS)} FROM new_rows")
        con.execute("COMMIT")
    finally:
        con.close()


def save_countries(names, db_path=DB_PATH):
    """Save ISO3 code -> country name, as returned by the API (used by the dashboard)."""
    countries = pd.DataFrame(sorted(names.items()), columns=["country_iso3", "name"])
    con = duckdb.connect(str(db_path))
    try:
        con.register("countries_df", countries)
        con.execute("CREATE OR REPLACE TABLE countries AS SELECT * FROM countries_df")
    finally:
        con.close()


def load_findex_sample(db_path=DB_PATH):
    """Load interviews and design effect per country and Findex edition (needed for margins of error)."""
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            "CREATE OR REPLACE TABLE findex_sample AS SELECT * FROM read_csv(?, header = true)",
            [str(FINDEX_SAMPLE_PATH)],
        )
    finally:
        con.close()


def create_views(db_path=DB_PATH):
    """Run every .sql file in sql/ (each one is a CREATE OR REPLACE VIEW)."""
    con = duckdb.connect(str(db_path))
    try:
        for sql_file in sorted(SQL_DIR.glob("*.sql")):
            con.execute(sql_file.read_text(encoding="utf-8"))
    finally:
        con.close()


def main():
    config = load_config()
    countries = config["countries"]
    extracted_at = datetime.now(timezone.utc)
    names = {}

    for i, indicator in enumerate(config["indicators"]):
        if i > 0:
            time.sleep(PAUSE_BETWEEN_REQUESTS_SEC)
        data = fetch(countries, indicator)
        names.update({r["countryiso3code"]: r["country"]["value"] for r in data[1]})
        save_raw(data, indicator, extracted_at)
        table = to_table(data, extracted_at)
        save_to_duckdb(table, countries, indicator)
        print(f"{indicator:18} {len(table):4} rows")

    save_countries(names)
    load_findex_sample()
    create_views()
    print(f"Done. Database: {DB_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
