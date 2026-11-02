"""Check that every country code in config.yaml is a real country, not an aggregate.

Needs internet access.
"""

from pathlib import Path

import pytest
import requests
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
COUNTRIES = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["countries"]


@pytest.mark.parametrize("code", COUNTRIES)
def test_country_code_is_a_country(code):
    response = requests.get(
        f"https://api.worldbank.org/v2/country/{code}", params={"format": "json"}, timeout=30
    )
    response.raise_for_status()
    data = response.json()
    assert len(data) == 2 and data[1], f"{code} not found: {data}"
    # Aggregates such as WLD or LCN are listed under the "Aggregates" region.
    assert data[1][0]["region"]["value"] != "Aggregates", f"{code} is an aggregate, not a country"
