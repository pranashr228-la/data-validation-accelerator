"""Tests for default validation enablement and auto-configuration."""

from dva.config.defaults import apply_dataset_defaults, apply_defaults
from dva.config.loader import load_config
from dva.config.models import (
    AggregateConfig,
    CountConfig,
    DataQualityConfig,
    DatasetConfig,
    DatasetSide,
    DuplicateKeysConfig,
    RootConfig,
    RowHashConfig,
    StatisticalConfig,
    ValidationsConfig,
)
from dva.config.validator import validate_config


def _minimal_dataset(**overrides) -> DatasetConfig:
    base = {
        "name": "test_ds",
        "mapping_mode": "table_to_table",
        "source": DatasetSide(connection="src", object="t"),
        "target": DatasetSide(connection="src", object="t"),
        "primary_key": ["id"],
        "compare_columns": ["amount", "status", "CustomerKey"],
    }
    base.update(overrides)
    return DatasetConfig(**base)


def test_validation_defaults_enabled():
    validations = ValidationsConfig()
    assert validations.count.enabled is True
    assert validations.duplicate_keys.enabled is True
    assert validations.row_hash.enabled is True
    assert validations.aggregate.enabled is True
    assert validations.statistical.enabled is True
    assert validations.data_quality.enabled is True
    assert validations.schema_contract.enabled is False


def test_auto_aggregate_and_statistical_metrics():
    dataset = _minimal_dataset()
    apply_dataset_defaults(dataset, ValidationsConfig())
    assert dataset.validations.aggregate.metrics
    assert dataset.validations.statistical.metrics
    amount_agg = next(m for m in dataset.validations.aggregate.metrics if m.column == "amount")
    assert "sum" in amount_agg.checks
    status_stat = next(m for m in dataset.validations.statistical.metrics if m.column == "status")
    assert "distinct_count" in status_stat.checks


def test_auto_dq_rules_for_pk_and_key_columns():
    dataset = _minimal_dataset()
    apply_dataset_defaults(dataset, ValidationsConfig())
    rule_names = {rule.name for rule in dataset.validations.data_quality.rules}
    assert "id_pk_not_null" in rule_names
    assert "CustomerKey_not_null" in rule_names


def test_row_hash_disabled_without_compare_columns():
    dataset = _minimal_dataset(compare_columns=[])
    apply_dataset_defaults(dataset, ValidationsConfig())
    assert dataset.validations.row_hash.enabled is False


def test_project_row_hash_defaults_applied():
    dataset = _minimal_dataset()
    project_defaults = ValidationsConfig(
        row_hash=RowHashConfig(max_mismatch_samples=50, write_full_mismatches=False)
    )
    apply_dataset_defaults(dataset, project_defaults)
    assert dataset.validations.row_hash.max_mismatch_samples == 50


def test_example_config_still_validates():
    config = load_config("configs/examples/postgres_to_snowflake_table.yaml")
    validate_config(config)
    dataset = config.datasets[0]
    assert dataset.validations.aggregate.enabled is True
    assert dataset.validations.statistical.enabled is True


def test_adventureworks_config_applies_defaults(monkeypatch):
    monkeypatch.setenv("SRC_PG_HOST", "localhost")
    monkeypatch.setenv("SRC_PG_DATABASE", "aw")
    monkeypatch.setenv("SRC_PG_USER", "user")
    monkeypatch.setenv("SRC_PG_PASSWORD", "pass")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct")
    monkeypatch.setenv("SNOWFLAKE_USER", "user")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "pass")
    monkeypatch.setenv("SNOWFLAKE_ROLE", "role")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "wh")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "db")

    config = load_config(
        "configs/adventureworks_oltp_to_snowflake_dwh_validation_config_public.yml"
    )
    validate_config(config)
    fact = next(d for d in config.datasets if d.name == "fact_internet_sales_validation")
    assert fact.validations.row_hash.max_mismatch_samples == 100
    assert fact.validations.aggregate.group_by == ["OrderDateKey"]
    assert fact.validations.aggregate.metrics
