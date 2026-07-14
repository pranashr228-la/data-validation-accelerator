from __future__ import annotations

from dva.dialects.base import SQLDialect


class SnowflakeDialect(SQLDialect):
    name = "snowflake"

    def format_timestamp(self, expr: str) -> str:
        return f"TO_CHAR({expr}, 'YYYY-MM-DD HH24:MI:SS')"

    def hash_function(self, expr: str, algorithm: str) -> str:
        bits = {"sha256": 256, "md5": 128}.get(algorithm, 256)
        if algorithm == "md5":
            return f"MD5({expr})"
        return f"SHA2({expr}, {bits})"

    def not_regex_predicate(self, expr: str, pattern: str) -> str:
        escaped = pattern.replace("'", "''")
        return f"NOT REGEXP_LIKE({expr}, '{escaped}')"
