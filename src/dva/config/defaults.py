"""Apply default validation metrics and data-quality rules after config load."""

from __future__ import annotations

import re

from dva.config.models import (
    AggregateMetric,
    DataQualityRule,
    DatasetConfig,
    RootConfig,
    RowHashConfig,
    StatisticalMetric,
    ValidationsConfig,
)

_NUMERIC_HINTS = (
    "amount",
    "price",
    "cost",
    "quantity",
    "pct",
    "income",
    "weight",
    "count",
    "number",
    "qty",
    "rate",
    "total",
    "sum",
    "avg",
    "balance",
    "freight",
    "tax",
    "discount",
    "standardcost",
    "listprice",
)

_KEY_COLUMN_RE = re.compile(r"(key|id|alternatekey)$", re.IGNORECASE)


def _is_numeric_column(column: str) -> bool:
    lower = column.lower()
    return any(hint in lower for hint in _NUMERIC_HINTS)


def _is_key_column(column: str) -> bool:
    return bool(_KEY_COLUMN_RE.search(column))


def _all_columns(dataset: DatasetConfig) -> list[str]:
    seen: set[str] = set()
    columns: list[str] = []
    for col in dataset.primary_key + dataset.compare_columns:
        if col not in seen:
            seen.add(col)
            columns.append(col)
    return columns


def _auto_aggregate_metrics(dataset: DatasetConfig) -> list[AggregateMetric]:
    metrics: list[AggregateMetric] = []
    for column in _all_columns(dataset):
        if _is_numeric_column(column):
            metrics.append(
                AggregateMetric(column=column, checks=["sum", "avg", "count"])
            )
        metrics.append(
            AggregateMetric(column=column, checks=["count_distinct", "null_count"])
        )
    return metrics


def _auto_statistical_metrics(dataset: DatasetConfig) -> list[StatisticalMetric]:
    metrics: list[StatisticalMetric] = []
    for column in _all_columns(dataset):
        if _is_numeric_column(column):
            metrics.append(
                StatisticalMetric(column=column, checks=["mean", "stddev", "null_rate"])
            )
        else:
            metrics.append(
                StatisticalMetric(column=column, checks=["distinct_count", "null_rate"])
            )
    return metrics


def _auto_dq_rules(dataset: DatasetConfig) -> list[DataQualityRule]:
    rules: list[DataQualityRule] = []
    seen_names: set[str] = set()

    for column in dataset.primary_key:
        name = f"{column}_pk_not_null"
        if name not in seen_names:
            seen_names.add(name)
            rules.append(
                DataQualityRule(
                    name=name,
                    type="not_null",
                    column=column,
                    severity="CRITICAL",
                )
            )

    for column in dataset.compare_columns:
        if column in dataset.primary_key:
            continue
        if _is_key_column(column):
            name = f"{column}_not_null"
            if name not in seen_names:
                seen_names.add(name)
                rules.append(
                    DataQualityRule(
                        name=name,
                        type="not_null",
                        column=column,
                        severity="HIGH",
                    )
                )
    return rules


def _merge_validation_defaults(
    dataset: DatasetConfig, project_defaults: ValidationsConfig
) -> None:
    """Apply project-level row_hash triage settings when dataset uses factory defaults."""
    factory_rh = RowHashConfig()
    dataset_rh = dataset.validations.row_hash
    project_rh = project_defaults.row_hash
    if (
        dataset_rh.max_mismatch_samples == factory_rh.max_mismatch_samples
        and dataset_rh.write_full_mismatches == factory_rh.write_full_mismatches
    ):
        dataset_rh.max_mismatch_samples = project_rh.max_mismatch_samples
        dataset_rh.write_full_mismatches = project_rh.write_full_mismatches
    if project_defaults.aggregate.group_by and not dataset.validations.aggregate.group_by:
        dataset.validations.aggregate.group_by = list(project_defaults.aggregate.group_by)


def apply_dataset_defaults(dataset: DatasetConfig, project_defaults: ValidationsConfig) -> None:
    """Fill in auto-generated metrics and rules for enabled validations."""
    _merge_validation_defaults(dataset, project_defaults)
    validations = dataset.validations

    if validations.row_hash.enabled and not dataset.compare_columns:
        validations.row_hash.enabled = False

    if validations.aggregate.enabled and not validations.aggregate.metrics:
        validations.aggregate.metrics = _auto_aggregate_metrics(dataset)

    if validations.statistical.enabled and not validations.statistical.metrics:
        validations.statistical.metrics = _auto_statistical_metrics(dataset)

    if validations.data_quality.enabled and not validations.data_quality.rules:
        validations.data_quality.rules = _auto_dq_rules(dataset)
        if not validations.data_quality.rules:
            validations.data_quality.enabled = False


def apply_defaults(config: RootConfig) -> RootConfig:
    """Apply per-dataset default resolution to a loaded config."""
    project_defaults = config.defaults.validations
    for dataset in config.datasets:
        apply_dataset_defaults(dataset, project_defaults)
    return config
