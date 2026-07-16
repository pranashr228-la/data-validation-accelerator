"""Postgres connection helpers for validation results storage."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

DEFAULT_DATABASE_URL = "postgresql://dva:dva@localhost:5433/dva"
SCHEMA_FILES = ("001_schema.sql", "002_views.sql")


def get_database_url(explicit: str | None = None) -> str:
    """Resolve the results database URL from config, env, or default."""
    if explicit:
        return explicit
    return os.environ.get("DVA_DATABASE_URL", DEFAULT_DATABASE_URL)


def connect(database_url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(get_database_url(database_url))


def schema_sql_paths() -> list[Path]:
    root = Path(__file__).resolve().parents[3]
    return [root / "sql" / "postgres" / name for name in SCHEMA_FILES]


def apply_schema(conn: psycopg.Connection) -> None:
    """Apply all bundled Postgres schema and view migrations."""
    for path in schema_sql_paths():
        sql = path.read_text()
        conn.execute(sql)
    conn.commit()


def truncate_results(conn: psycopg.Connection) -> None:
    """Remove all validation results (for tests)."""
    conn.execute(
        """
        TRUNCATE TABLE
            dva.execution_logs,
            dva.validation_issues,
            dva.dq_results,
            dva.duplicate_keys,
            dva.extra_records,
            dva.missing_records,
            dva.hash_mismatches,
            dva.hash_summary,
            dva.statistical_results,
            dva.aggregate_results,
            dva.count_results,
            dva.schema_results,
            dva.rule_results,
            dva.dataset_summary,
            dva.run_summary
        CASCADE
        """
    )
    conn.commit()
