"""Databricks connector.

Not exercised by the MVP's AdventureWorks Postgres->Snowflake scenario, so
``databricks-sql-connector`` is intentionally not a hard project dependency.
It is imported lazily here; install it (``uv add databricks-sql-connector``)
only if a dataset actually targets Databricks.
"""

from __future__ import annotations

import pyarrow as pa

from dva.config.models import DatabricksConnectionConfig
from dva.connectors.base import Connector


class DatabricksConnector(Connector):
    dialect_name = "databricks"

    def __init__(self, config: DatabricksConnectionConfig) -> None:
        self._config = config
        self._conn = None

    def connect(self) -> None:
        try:
            from databricks import sql as databricks_sql
        except ImportError as exc:
            raise ImportError(
                "databricks-sql-connector is required for Databricks connections: "
                "uv add databricks-sql-connector"
            ) from exc

        cfg = self._config
        self._conn = databricks_sql.connect(
            server_hostname=cfg.server_hostname,
            http_path=cfg.http_path,
            access_token=cfg.access_token,
            catalog=cfg.catalog,
            schema=cfg.schema_name,
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
            return cur.fetchall_arrow()
        finally:
            cur.close()
