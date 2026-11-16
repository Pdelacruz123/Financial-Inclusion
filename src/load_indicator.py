"""Download the World Bank indicators listed in config.yaml and store them in DuckDB.

Steps, once per indicator (all countries in one request):
1. Call the World Bank API v2 (with pauses and retries).
2. Save the raw JSON to data/raw/ (keeps a history of series revisions).
3. Turn the response into a pandas table.
4. Replace this indicator's rows for those countries in the DuckDB `observations` table.
Then save the country and indicator names, load the Findex sample sizes
(data/findex_sample.csv) and (re)create the SQL views defined in sql/.

If an indicator fails after all retries, its previous rows in the database are
kept and the script exits with an error at the end only if the failure leaves
the lookup tables incomplete or no indicator could be loaded.

Usage:  python src/load_indicator.py
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests
import yaml

YEAR_RANGE = "2011:2024"
PAUSE_BETWEEN_REQUESTS_SEC = 1  # usage limits are not documented, so be gentle
CONNECT_TIMEOUT_SEC = 10
READ_TIMEOUT_SEC = 90  # the World Bank API is sometimes slow, 30 s was not enough

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

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "financial-inclusion-pipeline/1.0"})


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


def fetch(countries, indicator, attempts=5, pause_sec=3):
    """Request one indicator for several countries and return the parsed JSON.

    On failure (timeout, network down, 429/5xx error...) wait and retry. The
    wait doubles with each attempt: 3 s, 6 s, 12 s, 24 s.
    """
    url = API_URL.format(countries=";".join(countries), indicator=indicator)
    params = {"format": "json", "date": YEAR_RANGE, "per_page": 1000}

    for attempt in range(1, attempts + 1):
        try:
            response = SESSION.get(
                url, params=params, timeout=(CONNECT_TIMEOUT_SEC, READ_TIMEOUT_SEC)
            )
            response.raise_for_status()  # raises if the HTTP status is not 200
            data = response.json()
            break
        except (requests.RequestException, ValueError) as error:  # ValueError: invalid JSON
            if attempt == attempts:
                raise
            wait = pause_sec * 2 ** (attempt - 1)
            print(f"Attempt {attempt}/{attempts} failed ({error}). Retrying in {wait} s...")
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


def save_lookup(table, rows, columns, db_path=DB_PATH):
    """Replace a small lookup table (country names, indicator names and labels)."""
    frame = pd.DataFrame(rows, columns=columns)
    con = duckdb.connect(str(db_path))
    try:
        con.register("lookup_df", frame)
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM lookup_df")
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


def existing_lookup_names(db_path=DB_PATH):
    """Names already stored from earlier runs, used to fill gaps when an indicator fails."""
    if not db_path.exists():
        return {}, {}
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        countries = (
            dict(con.execute("SELECT country_iso3, name FROM countries").fetchall())
            if "countries" in tables
            else {}
        )
        indicators = (
            dict(con.execute("SELECT indicator, name FROM indicators").fetchall())
            if "indicators" in tables
            else {}
        )
        return countries, indicators
    finally:
        con.close()


def main():
    config = load_config()
    countries = config["countries"]
    extracted_at = datetime.now(timezone.utc)
    previous_countries, previous_indicators = existing_lookup_names()
    country_names = dict(previous_countries)
    indicator_names = dict(previous_indicators)
    failed = []
    loaded = 0

    for i, indicator in enumerate(config["indicators"]):
        if i > 0:
            time.sleep(PAUSE_BETWEEN_REQUESTS_SEC)
        try:
            data = fetch(countries, indicator)
        except (requests.RequestException, ValueError) as error:
            # Keep the rows from the last good run; do not touch the database.
            print(f"{indicator:18} FAILED, keeping previous data: {error}")
            failed.append(indicator)
            continue
        country_names.update({r["countryiso3code"]: r["country"]["value"] for r in data[1]})
        indicator_names.update({r["indicator"]["id"]: r["indicator"]["value"] for r in data[1]})
        save_raw(data, indicator, extracted_at)
        table = to_table(data, extracted_at)
        save_to_duckdb(table, countries, indicator)
        loaded += 1
        print(f"{indicator:18} {len(table):4} rows")

    if loaded == 0:
        print("No indicator could be loaded.")
        sys.exit(1)

    save_lookup("countries", sorted(country_names.items()), ["country_iso3", "name"])
    save_lookup(
        "indicators",
        [(code, indicator_names.get(code), label) for code, label in config["indicators"].items()],
        ["indicator", "name", "label"],
    )
    load_findex_sample()
    create_views()
    print(f"Done. Database: {DB_PATH.relative_to(ROOT)}")

    if failed:
        # Visible in the Actions summary, but the data and views are already updated.
        print(f"::warning::Indicators not refreshed this run: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
