"""Download one World Bank indicator for one country and store it in DuckDB.

Steps:
1. Call the World Bank API v2 (with pauses and retries).
2. Save the raw JSON to data/raw/ (keeps a history of series revisions).
3. Turn the response into a pandas table.
4. Replace this country + indicator's rows in the DuckDB `observations` table.
5. (Re)create the SQL views defined in sql/.

For now the country and indicator are fixed below; an example country
(e.g. Peru) is used until the YAML config exists.

Usage:  python src/load_indicator.py
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests

COUNTRY = "PER"  # ISO3 code of the example country
INDICATOR = "FX.OWN.TOTL.ZS"  # account ownership, % of adults 15+ (Findex)
YEAR_RANGE = "2011:2024"

API_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "monitor.duckdb"
SQL_DIR = ROOT / "sql"


def fetch(country, indicator, attempts=3, pause_sec=2):
    """Request the data from the API and return the parsed JSON.

    On failure (network down, 5xx error...) wait and retry. The wait grows
    with each attempt: 2 s, 4 s, 6 s.
    """
    url = API_URL.format(country=country, indicator=indicator)
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
        raise ValueError(f"The API returned no data for {country}/{indicator}: {data}")
    if data[0]["pages"] > 1:
        raise ValueError("The response has more than one page; pagination is missing.")

    return data


def save_raw(data, country, indicator, extracted_at):
    """Save the JSON exactly as received. The file name carries the UTC date and time."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = extracted_at.strftime("%Y-%m-%dT%H%M%SZ")  # no ":" because Windows rejects it
    path = RAW_DIR / f"{indicator}_{country}_{stamp}.json"
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
        year = int(record["date"])
        rows.append(
            {
                "country_iso3": record["countryiso3code"],
                "indicator": record["indicator"]["id"],
                "year": year,
                "edition": year,  # Findex edition = year reported by the API
                "survey_year": None,  # not in the API; to be filled from the official Findex file
                "value": float(record["value"]),
                "extracted_at": extracted_at.replace(tzinfo=None),  # stored in UTC
            }
        )
    table = pd.DataFrame(rows)
    table["survey_year"] = table["survey_year"].astype("Int64")  # integer that allows nulls
    return table


def save_to_duckdb(table, country, indicator, db_path=DB_PATH):
    """Replace this country + indicator's rows so re-running does not duplicate them."""
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
            "DELETE FROM observations WHERE country_iso3 = ? AND indicator = ?",
            [country, indicator],
        )
        con.register("new_rows", table)  # lets DuckDB read the DataFrame by name
        con.execute(
            """
            INSERT INTO observations
            SELECT country_iso3, indicator, year, edition, survey_year, value, extracted_at
            FROM new_rows
            """
        )
        con.execute("COMMIT")
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
    extracted_at = datetime.now(timezone.utc)

    data = fetch(COUNTRY, INDICATOR)
    raw_path = save_raw(data, COUNTRY, INDICATOR, extracted_at)
    table = to_table(data, extracted_at)
    save_to_duckdb(table, COUNTRY, INDICATOR)
    create_views()

    print(f"Raw JSON saved to: {raw_path.relative_to(ROOT)}")
    print(f"Rows loaded into {DB_PATH.relative_to(ROOT)}: {len(table)}")
    print(table[["country_iso3", "year", "value"]].to_string(index=False))


if __name__ == "__main__":
    main()
