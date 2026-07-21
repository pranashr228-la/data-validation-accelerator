"""PostgreSQL connector, built directly on psycopg (no ORM layer)."""

from __future__ import annotations

import psycopg
import pyarrow as pa

from dva.config.models import PostgresConnectionConfig
from dva.connectors.base import Connector


class PostgresConnector(Connector):
    dialect_name = "postgres"

    def __init__(self, config: PostgresConnectionConfig) -> None:
        self._config = config
        self._conn: psycopg.Connection | None = None

    def connect(self) -> None:
        cfg = self._config
        self._conn = psycopg.connect(
            host=cfg.host,
            port=cfg.port,
            dbname=cfg.database,
            user=cfg.username,
            password=cfg.password,
            options=f"-c search_path={cfg.schema_name}",
        )

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def fetch_arrow(self, sql: str) -> pa.Table:
        assert self._conn is not None, "Connector must be connected before use"
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql)
                columns = [desc.name for desc in cur.description or []]
                rows = cur.fetchall()
            arrays = [pa.array([row[i] for row in rows]) for i in range(len(columns))]
            return pa.Table.from_arrays(arrays, names=columns) if columns else pa.table({})
        except Exception:
            self._conn.rollback()
            raise
