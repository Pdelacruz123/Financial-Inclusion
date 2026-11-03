"""download_database: falls back to the previous download when GitHub fails.

No network: requests.get is replaced by a fake that succeeds or fails.
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import dashboard  # noqa: E402


class FakeResponse:
    content = b"new database"

    def raise_for_status(self):
        pass


def github_down(*args, **kwargs):
    raise requests.ConnectionError("GitHub is down")


def test_downloads_a_new_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.requests, "get", lambda *a, **k: FakeResponse())
    path = dashboard.download_database(tmp_path)
    assert path.read_bytes() == b"new database"


def test_reuses_newest_previous_download_when_github_fails(tmp_path, monkeypatch):
    (tmp_path / "financial-inclusion-monitor-1700000000.duckdb").write_bytes(b"older")
    (tmp_path / "financial-inclusion-monitor-1800000000.duckdb").write_bytes(b"newest")
    monkeypatch.setattr(dashboard.requests, "get", github_down)
    assert dashboard.download_database(tmp_path).read_bytes() == b"newest"


def test_fails_when_github_fails_and_nothing_was_downloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.requests, "get", github_down)
    with pytest.raises(requests.ConnectionError):
        dashboard.download_database(tmp_path)
