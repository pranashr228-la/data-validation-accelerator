from dva.dialects.registry import get_dialect
from dva.normalization.sql_builder import (
    build_aggregate_sql,
    build_key_and_columns_sql,
    build_statistical_sql,
)


def test_key_and_columns_sql_quotes_aliases_for_snowflake():
    dialect = get_dialect("snowflake")
    sql = build_key_and_columns_sql("SELECT 1", ["email", "customer_id"], dialect)
    assert 'AS "email"' in sql
    assert 'AS "customer_id"' in sql


def test_aggregate_sql_quotes_metric_aliases_for_snowflake():
    from dva.config.models import AggregateMetric

    dialect = get_dialect("snowflake")
    metrics = [AggregateMetric(column="balance", checks=["sum"])]
    sql = build_aggregate_sql("SELECT 1", ["customer_id"], metrics, dialect)
    assert 'AS "customer_id"' in sql
    assert 'AS "balance__sum"' in sql


def test_statistical_sql_quotes_metric_aliases_for_snowflake():
    from dva.config.models import StatisticalMetric

    dialect = get_dialect("snowflake")
    metrics = [StatisticalMetric(column="balance", checks=["mean"])]
    sql = build_statistical_sql("SELECT 1", metrics, dialect)
    assert 'AS "balance__mean"' in sql
