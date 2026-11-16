"""Check that every country code in config.yaml is a real country, not an aggregate.

Needs internet access. One request lists all World Bank countries and
aggregates; if the API is down after several retries the tests are skipped.
"""

import time
from pathlib import Path

import pytest
import requests
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
COUNTRIES = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["countries"]

API_URL = "https://api.worldbank.org/v2/country/all"
ATTEMPTS = 4


@pytest.fixture(scope="module")
def api_countries():
    """All countries and aggregates by code, fetched once with retries."""
    last_error = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = requests.get(
                API_URL,
                params={"format": "json", "per_page": 1000},
                timeout=(10, 60),
            )
            response.raise_for_status()
            data = response.json()
            if len(data) < 2 or not data[1]:
                raise ValueError(f"Unexpected response: {data}")
            if data[0]["pages"] > 1:
                raise ValueError("The response has more than one page; pagination is missing.")
            return {row["id"]: row for row in data[1]}
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt < ATTEMPTS:
                time.sleep(3 * 2 ** (attempt - 1))  # 3 s, 6 s, 12 s
    pytest.skip(f"World Bank API unavailable: {last_error}")


@pytest.mark.parametrize("code", COUNTRIES)
def test_country_code_is_a_country(code, api_countries):
    assert code in api_countries, f"{code} not found in the World Bank country list"
    # Aggregates such as WLD or LCN are listed under the "Aggregates" region.
    region = api_countries[code]["region"]["value"]
    assert region != "Aggregates", f"{code} is an aggregate, not a country"
