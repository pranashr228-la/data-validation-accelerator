from __future__ import annotations

from dva.dialects.base import SQLDialect


class DatabricksDialect(SQLDialect):
    name = "databricks"

    def format_timestamp(self, expr: str) -> str:
        return f"DATE_FORMAT({expr}, 'yyyy-MM-dd HH:mm:ss')"

    def hash_function(self, expr: str, algorithm: str) -> str:
        if algorithm == "md5":
            return f"MD5({expr})"
        return f"SHA2({expr}, 256)"

    def not_regex_predicate(self, expr: str, pattern: str) -> str:
        escaped = pattern.replace("'", "''")
        return f"NOT {expr} RLIKE '{escaped}'"
