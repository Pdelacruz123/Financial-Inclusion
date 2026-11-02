"""Range checks per indicator: each one has its own valid range.

Only shares of population are 0-100. The other limits are loose on purpose
(about 2x the world maximum seen in 2011-2024) to catch unit or loading
errors, not unusual but real values.

Requires running first:  python src/load_indicator.py
"""

from pathlib import Path

import pytest
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
INDICATORS = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["indicators"]

# (min, max). World max 2011-2024 in the comment.
VALID_RANGES = {
    "FX.OWN.TOTL.ZS": (0, 100),
    "FX.OWN.TOTL.FE.ZS": (0, 100),
    "FX.OWN.TOTL.40.ZS": (0, 100),
    "FB.CBK.BRCH.P5": (0, 500),  # 249.7, San Marino 2011
    "FB.ATM.TOTL.P5": (0, 1000),  # 317.8, Uruguay 2023
    "IT.CEL.SETS.P2": (0, 1000),  # 574.2, Fiji 2024: one person can hold several lines
    "IT.NET.USER.ZS": (0, 100),
    "FS.AST.PRVT.GD.ZS": (0, 500),  # 287.4, Macao 2022
    "NY.GDP.PCAP.CD": (0, 1_000_000),  # 288,001.6, Monaco 2024
}


@pytest.mark.parametrize("indicator", INDICATORS)
def test_values_in_range(con, indicator):
    assert indicator in VALID_RANGES, f"Add a valid range for {indicator} in VALID_RANGES"
    low, high = VALID_RANGES[indicator]
    out_of_range = con.execute(
        """
        SELECT country_iso3, year, value FROM observations
        WHERE indicator = ? AND (value < ? OR value > ?)
        """,
        [indicator, low, high],
    ).fetchall()
    assert out_of_range == [], f"{indicator} outside [{low}, {high}]: {out_of_range}"
