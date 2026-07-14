"""Connector base class.

A connector's job is narrow: open a connection to a system and run SQL
against it, returning results as an Arrow table. Everything else (dialect
specific SQL generation, hashing, comparisons) lives elsewhere so new
systems only need a thin adapter here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pyarrow as pa


class Connector(ABC):
    """Abstract base for all source/target connectors."""

    #: dialect key used to look up the matching `dva.dialects` implementation
    dialect_name: str

    def __enter__(self) -> "Connector":
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    @abstractmethod
    def connect(self) -> None:
        """Open the underlying connection."""

    @abstractmethod
    def close(self) -> None:
        """Close the underlying connection."""

    @abstractmethod
    def fetch_arrow(self, sql: str) -> pa.Table:
        """Execute ``sql`` and return the full result set as an Arrow table."""

    def get_schema(self, base_sql: str) -> dict[str, str]:
        """Infer the output schema of ``base_sql`` without fetching rows.

        Uses a ``LIMIT 0``-style wrapper so it works generically across
        dialects without needing catalog-specific introspection queries.
        """
        probe_sql = f"SELECT * FROM (\n{base_sql}\n) dva_schema_probe WHERE 1 = 0"
        table = self.fetch_arrow(probe_sql)
        return {field.name: str(field.type) for field in table.schema}

    def fetch_scalar(self, sql: str) -> object:
        table = self.fetch_arrow(sql)
        if table.num_rows == 0:
            return None
        return table.column(0)[0].as_py()
