"""Canonical validation execution order for a dataset."""

from __future__ import annotations

from collections.abc import Callable

from dva.engine.context import DatasetContext
from dva.validations import (
    run_aggregate,
    run_count,
    run_data_quality,
    run_duplicate_keys,
    run_row_hash,
    run_schema_contract,
    run_statistical,
)

VALIDATION_PLAN: list[tuple[str, Callable[[DatasetContext], None]]] = [
    ("schema_contract", run_schema_contract),
    ("count", run_count),
    ("duplicate_keys", run_duplicate_keys),
    ("row_hash", run_row_hash),
    ("aggregate", run_aggregate),
    ("statistical", run_statistical),
    ("data_quality", run_data_quality),
]
