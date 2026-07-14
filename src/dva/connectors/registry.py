"""Maps connection config types to connector implementations."""

from __future__ import annotations

from dva.config.models import ConnectionConfig
from dva.connectors.base import Connector
from dva.connectors.databricks import DatabricksConnector
from dva.connectors.duckdb_files import DuckDBConnector
from dva.connectors.parquet import ParquetConnector
from dva.connectors.postgres import PostgresConnector
from dva.connectors.snowflake import SnowflakeConnector

_REGISTRY = {
    "postgres": PostgresConnector,
    "snowflake": SnowflakeConnector,
    "duckdb": DuckDBConnector,
    "parquet": ParquetConnector,
    "databricks": DatabricksConnector,
}


def create_connector(config: ConnectionConfig) -> Connector:
    connector_cls = _REGISTRY.get(config.type)
    if connector_cls is None:
        raise ValueError(f"No connector registered for connection type '{config.type}'")
    return connector_cls(config)
