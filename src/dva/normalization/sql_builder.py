"""Builds the SQL text used by each validation engine.

Standard SQL (SELECT, GROUP BY, aggregate functions, PERCENTILE_CONT) is
generated directly here since it is identical across Postgres, Snowflake,
and DuckDB. Only identifier quoting is delegated to the active
``SQLDialect``.
"""

from __future__ import annotations

from dva.config.models import AggregateMetric, DatasetSide, StatisticalMetric
from dva.dialects.base import SQLDialect
from dva.utils.sql import base_select_sql

_AGG_SQL = {
    "count": "COUNT({col})",
    "count_distinct": "COUNT(DISTINCT {col})",
    "sum": "SUM({col})",
    "avg": "AVG({col})",
    "min": "MIN({col})",
    "max": "MAX({col})",
    "null_count": "SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)",
}

_STAT_SQL = {
    "mean": "AVG({col})",
    "stddev": "STDDEV({col})",
    "min": "MIN({col})",
    "max": "MAX({col})",
    "null_rate": "AVG(CASE WHEN {col} IS NULL THEN 1.0 ELSE 0.0 END)",
    "distinct_count": "COUNT(DISTINCT {col})",
    "p50": "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {col})",
    "p95": "PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {col})",
    "p99": "PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY {col})",
}


def build_base_sql(side: DatasetSide) -> str:
    return base_select_sql(object_name=side.object, sql=side.sql, filter_expr=side.filter)


def build_count_sql(base_sql: str, dialect: SQLDialect) -> str:
    return dialect.count_all_sql(base_sql)


def build_duplicate_keys_sql(
    base_sql: str, primary_key: list[str], dialect: SQLDialect
) -> str:
    return dialect.group_by_duplicate_keys_sql(base_sql, primary_key)


def build_key_and_columns_sql(
    base_sql: str, columns: list[str], dialect: SQLDialect
) -> str:
    cols = ", ".join(f"{dialect.quote_ident(c)} AS {c}" for c in columns)
    return f"SELECT {cols}\nFROM (\n{base_sql}\n) q"


def build_aggregate_sql(
    base_sql: str,
    group_by: list[str],
    metrics: list[AggregateMetric],
    dialect: SQLDialect,
) -> str:
    select_parts: list[str] = [f"{dialect.quote_ident(c)} AS {c}" for c in group_by]
    for metric in metrics:
        col = dialect.quote_ident(metric.column)
        for check in metric.checks:
            alias = f"{metric.column}__{check}"
            select_parts.append(f"{_AGG_SQL[check].format(col=col)} AS {alias}")
    select_clause = ",\n    ".join(select_parts)
    sql = f"SELECT\n    {select_clause}\nFROM (\n{base_sql}\n) q"
    if group_by:
        group_clause = ", ".join(dialect.quote_ident(c) for c in group_by)
        sql += f"\nGROUP BY {group_clause}"
    return sql


def build_statistical_sql(
    base_sql: str, metrics: list[StatisticalMetric], dialect: SQLDialect
) -> str:
    select_parts: list[str] = []
    for metric in metrics:
        col = dialect.quote_ident(metric.column)
        for check in metric.checks:
            alias = f"{metric.column}__{check}"
            select_parts.append(f"{_STAT_SQL[check].format(col=col)} AS {alias}")
    select_clause = ",\n    ".join(select_parts)
    return f"SELECT\n    {select_clause}\nFROM (\n{base_sql}\n) q"
