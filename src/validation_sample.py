"""Draw the validation sample and fill what can be filled automatically.

The sample is 30 values drawn with a fixed seed: 10 from each source that has
a defined primary source (Global Findex, IMF FAS, ITU). Each value is then
compared with that primary source, not with data.worldbank.org, which serves
the same data we already load. Private credit and GDP per capita are context
indicators without a defined primary source, so they are not sampled.

The CSV is drawn once and then kept: re-running the script never redraws it,
so values filled by hand are not lost.

Usage:
    python src/validation_sample.py                     # draw the sample if it does not exist
    python src/validation_sample.py path/to/GlobalFindexDatabase2025.csv
                                                        # also fill the Findex rows from the official file
"""

import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "monitor.duckdb"
SAMPLE_PATH = ROOT / "data" / "validation_sample.csv"

SEED = 42
ROWS_PER_SOURCE = 10

# Indicator code prefix -> primary source to compare against.
PRIMARY_SOURCES = {
    "FX.": "Global Findex 2025 official file (GlobalFindexDatabase2025.csv)",
    "FB.": "IMF Financial Access Survey (data.imf.org)",
    "IT.": "ITU DataHub (datahub.itu.int)",
}

# (group, group2) of each Findex indicator in the official file, where values are shares (0-1).
OFFICIAL_FINDEX_GROUPS = {
    "FX.OWN.TOTL.ZS": ("all", "all"),
    "FX.OWN.TOTL.FE.ZS": ("gender", "women"),
    "FX.OWN.TOTL.40.ZS": ("income", "poorest 40%"),
}


def draw_sample(db_path=DB_PATH):
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT country_iso3, indicator, year, value AS our_value
            FROM observations
            ORDER BY country_iso3, indicator, year
            """
        ).df()
    finally:
        con.close()

    rows["prefix"] = rows["indicator"].str[:3]
    rows = rows[rows["prefix"].isin(PRIMARY_SOURCES)]
    sample = rows.groupby("prefix", group_keys=False).sample(n=ROWS_PER_SOURCE, random_state=SEED)
    sample["primary_source"] = sample["prefix"].map(PRIMARY_SOURCES)
    for column in ("primary_value", "checked_on", "notes"):
        sample[column] = pd.NA
    return sample.drop(columns="prefix").sort_values(["indicator", "country_iso3", "year"])


def fill_findex(sample, official_path):
    """Fill the Findex rows from the official country-level file."""
    official = pd.read_csv(
        official_path, usecols=["codewb", "year", "group", "group2", "account_t_d"], low_memory=False
    )
    for i, row in sample[sample["indicator"].isin(OFFICIAL_FINDEX_GROUPS)].iterrows():
        group, group2 = OFFICIAL_FINDEX_GROUPS[row["indicator"]]
        match = official[
            (official["codewb"] == row["country_iso3"])
            & (official["year"] == row["year"])
            & (official["group"] == group)
            & (official["group2"] == group2)
        ]
        if len(match) == 1:
            sample.loc[i, "primary_value"] = round(float(match["account_t_d"].iloc[0]) * 100, 4)
            sample.loc[i, "checked_on"] = date.today().isoformat()
        else:
            sample.loc[i, "notes"] = f"{len(match)} matching rows in the official file"
    return sample


def main():
    if SAMPLE_PATH.exists():
        sample = pd.read_csv(SAMPLE_PATH)
    else:
        sample = draw_sample()
        print(f"Drew {len(sample)} values with seed {SEED}.")

    if len(sys.argv) > 1:
        sample = fill_findex(sample, sys.argv[1])

    sample.to_csv(SAMPLE_PATH, index=False)
    filled = sample["primary_value"].notna().sum()
    print(f"{SAMPLE_PATH.relative_to(ROOT)}: {filled} of {len(sample)} values checked against a primary source.")


if __name__ == "__main__":
    main()
