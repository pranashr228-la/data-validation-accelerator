from __future__ import annotations

from dva.dialects.base import SQLDialect


class DuckDBDialect(SQLDialect):
    name = "duckdb"

    def format_timestamp(self, expr: str) -> str:
        return f"STRFTIME({expr}, '%Y-%m-%d %H:%M:%S')"

    def hash_function(self, expr: str, algorithm: str) -> str:
        if algorithm == "md5":
            return f"MD5({expr})"
        return f"SHA256({expr})"

    def not_regex_predicate(self, expr: str, pattern: str) -> str:
        escaped = pattern.replace("'", "''")
        return f"NOT regexp_matches({expr}, '{escaped}')"
