"""Accumulates report rows across a run and flushes them to Parquet."""

from __future__ import annotations

from pathlib import Path

from dva.issues.model import ValidationIssue
from dva.reporting.models import (
    AggregateResult,
    CountResult,
    DataQualityResult,
    DatasetSummary,
    DuplicateKey,
    ExtraRecord,
    HashMismatch,
    HashSummary,
    MissingRecord,
    RuleResult,
    RunSummary,
    SchemaResult,
    StatisticalResult,
)
from dva.reporting.parquet_writer import write_models_to_parquet


class ReportCollector:
    """In-memory accumulator for all report entities produced during a run."""

    def __init__(self) -> None:
        self.run_summaries: list[RunSummary] = []
        self.dataset_summaries: list[DatasetSummary] = []
        self.rule_results: list[RuleResult] = []
        self.schema_results: list[SchemaResult] = []
        self.count_results: list[CountResult] = []
        self.aggregate_results: list[AggregateResult] = []
        self.statistical_results: list[StatisticalResult] = []
        self.hash_summaries: list[HashSummary] = []
        self.hash_mismatches: list[HashMismatch] = []
        self.missing_records: list[MissingRecord] = []
        self.extra_records: list[ExtraRecord] = []
        self.duplicate_keys: list[DuplicateKey] = []
        self.dq_results: list[DataQualityResult] = []
        self.validation_issues: list[ValidationIssue] = []

    def write_all(self, run_dir: Path) -> None:
        write_models_to_parquet(run_dir / "run_summary.parquet", list(self.run_summaries))
        write_models_to_parquet(run_dir / "dataset_summary.parquet", list(self.dataset_summaries))
        write_models_to_parquet(run_dir / "rule_results.parquet", list(self.rule_results))
        write_models_to_parquet(run_dir / "schema_results.parquet", list(self.schema_results))
        write_models_to_parquet(run_dir / "count_results.parquet", list(self.count_results))
        write_models_to_parquet(
            run_dir / "aggregate_results.parquet", list(self.aggregate_results)
        )
        write_models_to_parquet(
            run_dir / "statistical_results.parquet", list(self.statistical_results)
        )
        write_models_to_parquet(run_dir / "hash_summary.parquet", list(self.hash_summaries))
        write_models_to_parquet(run_dir / "hash_mismatches.parquet", list(self.hash_mismatches))
        write_models_to_parquet(run_dir / "missing_records.parquet", list(self.missing_records))
        write_models_to_parquet(run_dir / "extra_records.parquet", list(self.extra_records))
        write_models_to_parquet(run_dir / "duplicate_keys.parquet", list(self.duplicate_keys))
        write_models_to_parquet(run_dir / "dq_results.parquet", list(self.dq_results))
        write_models_to_parquet(
            run_dir / "validation_issues.parquet", list(self.validation_issues)
        )
