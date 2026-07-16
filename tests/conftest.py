"""Shared Postgres fixtures for tests."""

from __future__ import annotations

import os

import psycopg
import pytest

from dva.reporting.database import apply_schema, get_database_url, truncate_results


def _postgres_available(url: str) -> bool:
    try:
        with psycopg.connect(url) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.environ.get("DVA_TEST_DATABASE_URL", get_database_url(None))


@pytest.fixture
def postgres_db(database_url: str, monkeypatch):
    """Apply schema and truncate results before a Postgres-backed test."""
    if not _postgres_available(database_url):
        pytest.skip("Postgres not available — start with: docker compose up postgres -d")
    monkeypatch.setenv("DVA_DATABASE_URL", database_url)
    with psycopg.connect(database_url) as conn:
        apply_schema(conn)
        truncate_results(conn)
    yield
