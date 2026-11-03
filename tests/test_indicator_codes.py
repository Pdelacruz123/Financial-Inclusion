"""Check that every indicator code in config.yaml exists in the World Bank API.

Needs internet access.
"""

from pathlib import Path

import pytest
import requests
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
CODES = list(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["indicators"])


@pytest.mark.parametrize("code", CODES)
def test_indicator_code_resolves(code):
    response = requests.get(
        f"https://api.worldbank.org/v2/indicator/{code}", params={"format": "json"}, timeout=30
    )
    response.raise_for_status()
    data = response.json()
    # An unknown code still returns 200, but as [{"message": [...]}] instead of [metadata, [rows]].
    assert len(data) == 2 and data[1], f"{code} not found: {data}"
    assert data[1][0]["id"] == code
