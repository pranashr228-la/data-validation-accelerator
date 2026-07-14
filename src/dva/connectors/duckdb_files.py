"""DuckDB connector.

Used for DuckDB-native databases/files and, in the MVP, as a local
stand-in for warehouse targets (e.g. Snowflake) when no live instance is
available — the generated SQL is dialect-neutral enough to run unmodified.
"""

from __future__ import annotations

import duckdb
import pyarrow as pa

from dva.config.models import DuckDBConnectionConfig
from dva.connectors.base import Connector


class DuckDBConnector(Connector):
    dialect_name = "duckdb"

    def __init__(self, config: DuckDBConnectionConfig) -> None:
        self._config = config
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        self._conn = duckdb.connect(self._config.path)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def fetch_arrow(self, sql: str) -> pa.Table:
        assert self._conn is not None, "Connector must be connected before use"
        return self._conn.execute(sql).to_arrow_table()

    def execute(self, sql: str) -> None:
        assert self._conn is not None, "Connector must be connected before use"
        self._conn.execute(sql)
