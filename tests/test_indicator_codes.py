"""Check that every indicator code in config.yaml exists in the World Bank API.

Needs internet access. The World Bank API sometimes times out, so requests are
retried with exponential backoff before the test is allowed to fail.
"""

from pathlib import Path

import pytest
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
CODES = list(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["indicators"])


def _session_with_retries() -> requests.Session:
    """Session that retries timeouts, connection errors and 429/5xx (3 retries, 2s/4s/8s backoff)."""
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


@pytest.fixture(scope="module")
def session():
    with _session_with_retries() as s:
        yield s


@pytest.mark.parametrize("code", CODES)
def test_indicator_code_resolves(session, code):
    response = session.get(
        f"https://api.worldbank.org/v2/indicator/{code}", params={"format": "json"}, timeout=30
    )
    response.raise_for_status()
    data = response.json()
    # An unknown code still returns 200, but as [{"message": [...]}] instead of [metadata, [rows]].
    assert len(data) == 2 and data[1], f"{code} not found: {data}"
    assert data[1][0]["id"] == code
