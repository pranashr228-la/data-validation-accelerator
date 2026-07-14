"""SQL dialect base class.

Dialects capture the small set of SQL differences that matter for
building normalized row-hash expressions across engines: identifier
quoting, numeric/timestamp text formatting, and hash functions. Standard
SQL (TRIM, UPPER, CONCAT_WS, ROUND, COALESCE) is assumed to work
identically across Postgres, Snowflake, and DuckDB and is generated
directly in ``dva.normalization.sql_builder``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SQLDialect(ABC):
    name: str

    def quote_ident(self, identifier: str) -> str:
        return f'"{identifier}"'

    def cast_to_text(self, expr: str) -> str:
        return f"CAST({expr} AS VARCHAR)"

    def round_numeric(self, expr: str, decimal_scale: int) -> str:
        return f"ROUND(CAST({expr} AS DOUBLE PRECISION), {decimal_scale})"

    @abstractmethod
    def format_timestamp(self, expr: str) -> str:
        """Render a timestamp/date expression as ``YYYY-MM-DD HH:MI:SS`` text."""

    @abstractmethod
    def hash_function(self, expr: str, algorithm: str) -> str:
        """Wrap ``expr`` (already text) with a hex-digest hash function call."""

    @abstractmethod
    def not_regex_predicate(self, expr: str, pattern: str) -> str:
        """Predicate that is true when ``expr`` does NOT match ``pattern``."""

    def count_all_sql(self, base_sql: str) -> str:
        return f"SELECT COUNT(*) AS row_count FROM (\n{base_sql}\n) q"

    def group_by_duplicate_keys_sql(self, base_sql: str, key_columns: list[str]) -> str:
        group_keys = ", ".join(self.quote_ident(c) for c in key_columns)
        select_keys = ", ".join(
            f"{self.quote_ident(c)} AS {self.quote_ident(c)}" for c in key_columns
        )
        return (
            f"SELECT {select_keys}, COUNT(*) AS {self.quote_ident('duplicate_count')}\n"
            f"FROM (\n{base_sql}\n) q\n"
            f"GROUP BY {group_keys}\n"
            f"HAVING COUNT(*) > 1"
        )
