from __future__ import annotations

from dva.dialects.base import SQLDialect


class PostgresDialect(SQLDialect):
    name = "postgres"

    def format_timestamp(self, expr: str) -> str:
        return f"TO_CHAR({expr}, 'YYYY-MM-DD HH24:MI:SS')"

    def hash_function(self, expr: str, algorithm: str) -> str:
        # requires the pgcrypto extension: CREATE EXTENSION IF NOT EXISTS pgcrypto;
        return f"ENCODE(DIGEST({expr}, '{algorithm}'), 'hex')"

    def not_regex_predicate(self, expr: str, pattern: str) -> str:
        escaped = pattern.replace("'", "''")
        return f"{expr} !~ '{escaped}'"
