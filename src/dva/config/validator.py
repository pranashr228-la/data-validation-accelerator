"""Semantic validation beyond what pydantic field types already enforce."""

from __future__ import annotations

from dva.config.models import RootConfig


class ConfigValidationError(ValueError):
    """Raised when a loaded config is structurally valid but semantically wrong."""


def validate_config(config: RootConfig) -> None:
    """Validate cross-field rules that pydantic field validators cannot express.

    Checks connection references, primary keys, and mapping-mode-specific
    requirements. Raises ``ConfigValidationError`` with all problems found.
    """
    errors: list[str] = []

    if not config.datasets:
        errors.append("At least one dataset must be defined under 'datasets'")

    for dataset in config.datasets:
        prefix = f"dataset '{dataset.name}'"

        if not dataset.primary_key:
            errors.append(f"{prefix}: 'primary_key' must contain at least one column")

        for side_name, side in (("source", dataset.source), ("target", dataset.target)):
            if side.connection not in config.connections:
                errors.append(
                    f"{prefix}: {side_name}.connection '{side.connection}' is not defined "
                    "under 'connections'"
                )
            if dataset.mapping_mode == "table_to_table" and side.object is None:
                errors.append(
                    f"{prefix}: mapping_mode 'table_to_table' requires {side_name}.object"
                )
            if dataset.mapping_mode == "query_to_query" and side.sql is None:
                errors.append(
                    f"{prefix}: mapping_mode 'query_to_query' requires {side_name}.sql"
                )

        if dataset.validations.row_hash.enabled and not dataset.compare_columns:
            errors.append(f"{prefix}: row_hash validation requires 'compare_columns'")

        if dataset.validations.aggregate.enabled and not dataset.validations.aggregate.metrics:
            errors.append(f"{prefix}: aggregate validation enabled but no 'metrics' configured")

        if (
            dataset.validations.statistical.enabled
            and not dataset.validations.statistical.metrics
        ):
            errors.append(f"{prefix}: statistical validation enabled but no 'metrics' configured")

        if dataset.validations.data_quality.enabled and not dataset.validations.data_quality.rules:
            errors.append(f"{prefix}: data_quality validation enabled but no 'rules' configured")

    if errors:
        raise ConfigValidationError("; ".join(errors))
