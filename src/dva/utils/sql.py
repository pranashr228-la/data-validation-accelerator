"""Small SQL text helpers shared across dialects and validations."""

from __future__ import annotations


def wrap_as_subquery(base_sql: str, alias: str = "q") -> str:
    """Wrap arbitrary SQL text as a subquery: ``(base_sql) alias``."""
    return f"(\n{base_sql}\n) {alias}"


def base_select_sql(*, object_name: str | None, sql: str | None, filter_expr: str | None) -> str:
    """Build the base SELECT for a dataset side (source or target).

    Exactly one of ``object_name`` (table_to_table) or ``sql``
    (query_to_query) must be provided.
    """
    if sql is not None:
        return sql.strip().rstrip(";")
    if object_name is None:
        raise ValueError("Either 'object' or 'sql' must be provided for a dataset side")
    query = f"SELECT * FROM {object_name}"
    if filter_expr:
        query += f" WHERE {filter_expr}"
    return query


def indent(sql: str, spaces: int = 4) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in sql.splitlines())
