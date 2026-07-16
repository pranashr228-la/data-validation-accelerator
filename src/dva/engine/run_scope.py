"""Run-time scoping for datasets and validation types."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field

ALL_VALIDATION_TYPES = frozenset(
    {
        "schema_contract",
        "count",
        "duplicate_keys",
        "row_hash",
        "aggregate",
        "statistical",
        "data_quality",
    }
)

DEFAULT_VALIDATION_TYPES = frozenset(
    {
        "count",
        "duplicate_keys",
        "row_hash",
        "aggregate",
        "statistical",
        "data_quality",
    }
)

_VALIDATION_ALIASES: dict[str, str] = {
    "hash": "row_hash",
    "stats": "statistical",
    "stat": "statistical",
    "agg": "aggregate",
    "dq": "data_quality",
    "duplicates": "duplicate_keys",
    "duplicate": "duplicate_keys",
    "schema": "schema_contract",
}


def normalize_validation_type(name: str) -> str:
    lowered = name.strip().lower()
    return _VALIDATION_ALIASES.get(lowered, lowered)


def parse_validation_types(values: str | None, *, skip: str | None = None) -> frozenset[str]:
    if values:
        parsed = {normalize_validation_type(part) for part in values.split(",") if part.strip()}
        unknown = parsed - ALL_VALIDATION_TYPES
        if unknown:
            raise ValueError(
                f"Unknown validation type(s): {', '.join(sorted(unknown))}. "
                f"Valid types: {', '.join(sorted(ALL_VALIDATION_TYPES))}"
            )
        return frozenset(parsed)

    enabled = set(DEFAULT_VALIDATION_TYPES)
    if skip:
        skipped = {normalize_validation_type(part) for part in skip.split(",") if part.strip()}
        unknown = skipped - ALL_VALIDATION_TYPES
        if unknown:
            raise ValueError(
                f"Unknown validation type(s) in --skip-validations: {', '.join(sorted(unknown))}"
            )
        enabled -= skipped
    return frozenset(enabled)


def parse_dataset_names(values: str | None, available: list[str]) -> list[str] | None:
    if not values:
        return None
    patterns = [part.strip() for part in values.split(",") if part.strip()]
    selected: list[str] = []
    for name in available:
        if any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
            selected.append(name)
    if not selected:
        raise ValueError(f"No datasets matched --datasets filter: {values}")
    return selected


@dataclass(frozen=True)
class RunScope:
    dataset_names: tuple[str, ...] | None = None
    validation_types: frozenset[str] = field(default_factory=lambda: DEFAULT_VALIDATION_TYPES)

    def includes_dataset(self, name: str) -> bool:
        if self.dataset_names is None:
            return True
        return name in self.dataset_names

    def includes_validation(self, validation_type: str) -> bool:
        return validation_type in self.validation_types
