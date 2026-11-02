"""Shared pytest fixtures. pytest loads this file automatically."""

from pathlib import Path

import duckdb
import pytest

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "monitor.duckdb"


@pytest.fixture
def con():
    """Open the database read-only and close it when the test ends."""
    if not DB_PATH.exists():
        pytest.fail(f"{DB_PATH} does not exist. Run first: python src/load_indicator.py")
    connection = duckdb.connect(str(DB_PATH), read_only=True)
    yield connection
    connection.close()
