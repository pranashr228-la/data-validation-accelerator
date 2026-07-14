"""Run-level and dataset-level execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from dva.config.models import DatasetConfig, HashDefaults, RootConfig
from dva.connectors.base import Connector
from dva.dialects.base import SQLDialect
from dva.reporting.jsonl_logger import JsonlLogger
from dva.reporting.writer import ReportCollector


@dataclass
class RunContext:
    run_id: str
    config: RootConfig
    run_dir: Path
    report: ReportCollector = field(default_factory=ReportCollector)
    logger: JsonlLogger | None = None
    scratch_duckdb: duckdb.DuckDBPyConnection = field(
        default_factory=lambda: duckdb.connect(":memory:")
    )

    @property
    def hash_defaults(self) -> HashDefaults:
        return self.config.defaults.hash

    def generated_sql_dir(self) -> Path:
        path = self.run_dir / "generated_sql"
        if self.config.execution.write_generated_sql:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def write_generated_sql(self, dataset_name: str, label: str, sql: str) -> None:
        if not self.config.execution.write_generated_sql:
            return
        path = self.generated_sql_dir() / f"{dataset_name}__{label}.sql"
        path.write_text(sql)


@dataclass
class DatasetContext:
    run: RunContext
    dataset: DatasetConfig
    source: Connector
    target: Connector
    source_dialect: SQLDialect
    target_dialect: SQLDialect
    source_base_sql: str
    target_base_sql: str
