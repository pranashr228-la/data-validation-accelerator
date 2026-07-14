"""Parquet connector.

Queries Parquet files through an in-memory DuckDB engine. Dataset
``object`` values should be DuckDB table functions, e.g.
``read_parquet('sample_data/parquet/customer.parquet')``.
"""

from __future__ import annotations

import duckdb
import pyarrow as pa

from dva.config.models import ParquetConnectionConfig
from dva.connectors.base import Connector


class ParquetConnector(Connector):
    dialect_name = "duckdb"

    def __init__(self, config: ParquetConnectionConfig) -> None:
        self._config = config
        self._conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> None:
        self._conn = duckdb.connect(":memory:")

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def fetch_arrow(self, sql: str) -> pa.Table:
        assert self._conn is not None, "Connector must be connected before use"
        return self._conn.execute(sql).to_arrow_table()
