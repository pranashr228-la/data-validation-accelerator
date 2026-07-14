from __future__ import annotations

from dva.dialects.base import SQLDialect
from dva.dialects.databricks import DatabricksDialect
from dva.dialects.duckdb import DuckDBDialect
from dva.dialects.postgres import PostgresDialect
from dva.dialects.snowflake import SnowflakeDialect

_REGISTRY: dict[str, SQLDialect] = {
    "postgres": PostgresDialect(),
    "snowflake": SnowflakeDialect(),
    "duckdb": DuckDBDialect(),
    "databricks": DatabricksDialect(),
}


def get_dialect(name: str) -> SQLDialect:
    dialect = _REGISTRY.get(name)
    if dialect is None:
        raise ValueError(f"No SQL dialect registered for '{name}'")
    return dialect
