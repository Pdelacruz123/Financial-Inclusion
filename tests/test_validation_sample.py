"""Validation sample: 30 values compared with primary sources (data/validation_sample.csv).

Rows without a primary value yet are skipped; checked rows must match the
current database. A failure after a weekly load can also mean the World Bank
revised the series since the check.
"""

from pathlib import Path

import pandas as pd

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "validation_sample.csv"
KEY = ["country_iso3", "indicator", "year"]


def test_sample_has_10_values_per_source():
    sample = pd.read_csv(SAMPLE_PATH)
    assert len(sample) == 30
    assert set(sample["primary_source"].value_counts()) == {10}
    assert not sample.duplicated(KEY).any()


def test_checked_values_match_primary_source(con):
    checked = pd.read_csv(SAMPLE_PATH).dropna(subset=["primary_value"])
    current = con.execute(f"SELECT {', '.join(KEY)}, value FROM observations").df()
    merged = checked.merge(current, on=KEY, how="left")
    assert merged["value"].notna().all(), "a sampled value is no longer in the database"

    # Primary sources often publish rounded figures: allow 0.05 or 0.5%, whichever is larger.
    tolerance = (0.005 * merged["primary_value"].abs()).clip(lower=0.05)
    different = merged[(merged["value"] - merged["primary_value"]).abs() > tolerance]
    assert different.empty, different[KEY + ["value", "primary_value"]].to_string()
