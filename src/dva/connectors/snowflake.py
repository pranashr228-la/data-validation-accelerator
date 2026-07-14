"""Snowflake connector, built on snowflake-connector-python's native Arrow fetch."""

from __future__ import annotations

import pyarrow as pa
import snowflake.connector

from dva.config.models import SnowflakeConnectionConfig
from dva.connectors.base import Connector


class SnowflakeConnector(Connector):
    dialect_name = "snowflake"

    def __init__(self, config: SnowflakeConnectionConfig) -> None:
        self._config = config
        self._conn: snowflake.connector.SnowflakeConnection | None = None

    def connect(self) -> None:
        cfg = self._config
        self._conn = snowflake.connector.connect(
            account=cfg.account,
            user=cfg.username,
            password=cfg.password,
            warehouse=cfg.warehouse,
            database=cfg.database,
            schema=cfg.schema_name,
            role=cfg.role,
        )

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def fetch_arrow(self, sql: str) -> pa.Table:
        assert self._conn is not None, "Connector must be connected before use"
        cur = self._conn.cursor()
        try:
            cur.execute(sql)
            return cur.fetch_arrow_all() or pa.table({})
        finally:
            cur.close()
