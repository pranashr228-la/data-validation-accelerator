"""Accumulates report rows across a run and flushes them to Postgres."""

from __future__ import annotations

import psycopg

from dva.issues.model import ValidationIssue
from dva.reporting.models import (
    AggregateResult,
    CountResult,
    DataQualityResult,
    DatasetSummary,
    DuplicateKey,
    ExecutionLog,
    ExtraRecord,
    HashMismatch,
    HashSummary,
    MissingRecord,
    RuleResult,
    RunSummary,
    SchemaResult,
    StatisticalResult,
)
from dva.reporting.postgres_writer import bulk_insert


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
        self.execution_logs: list[ExecutionLog] = []

    def write_all(self, conn: psycopg.Connection) -> None:
        """Flush all accumulated report rows to Postgres."""
        bulk_insert(conn, "dva.run_summary", list(self.run_summaries))
        bulk_insert(conn, "dva.dataset_summary", list(self.dataset_summaries))
        bulk_insert(conn, "dva.rule_results", list(self.rule_results))
        bulk_insert(conn, "dva.schema_results", list(self.schema_results))
        bulk_insert(conn, "dva.count_results", list(self.count_results))
        bulk_insert(conn, "dva.aggregate_results", list(self.aggregate_results))
        bulk_insert(conn, "dva.statistical_results", list(self.statistical_results))
        bulk_insert(conn, "dva.hash_summary", list(self.hash_summaries))
        bulk_insert(conn, "dva.hash_mismatches", list(self.hash_mismatches))
        bulk_insert(conn, "dva.missing_records", list(self.missing_records))
        bulk_insert(conn, "dva.extra_records", list(self.extra_records))
        bulk_insert(conn, "dva.duplicate_keys", list(self.duplicate_keys))
        bulk_insert(conn, "dva.dq_results", list(self.dq_results))
        bulk_insert(conn, "dva.validation_issues", list(self.validation_issues))
        bulk_insert(conn, "dva.execution_logs", list(self.execution_logs))
