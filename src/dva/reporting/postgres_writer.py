"""Bulk-insert report models into Postgres."""

from __future__ import annotations

from typing import Any

import psycopg
from pydantic import BaseModel

# Maps Pydantic model field names to Postgres column names where they differ.
_COLUMN_ALIASES: dict[str, dict[str, str]] = {
    "aggregate_results": {"column": "column_name"},
    "statistical_results": {"column": "column_name"},
}


def _row(model: BaseModel, table: str) -> dict[str, Any]:
    data = model.model_dump()
    aliases = _COLUMN_ALIASES.get(table, {})
    return {aliases.get(k, k): v for k, v in data.items()}


def bulk_insert(
    conn: psycopg.Connection,
    schema_table: str,
    models: list[BaseModel],
) -> None:
    """Insert pydantic models into ``dva.<table>`` using executemany."""
    if not models:
        return
    table = schema_table.split(".")[-1]
    rows = [_row(m, table) for m in models]
    columns = list(rows[0].keys())
    col_list = ", ".join(columns)
    placeholders = ", ".join(f"%({c})s" for c in columns)
    sql = f"INSERT INTO {schema_table} ({col_list}) VALUES ({placeholders})"
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
