"""Appends execution log entries to the report collector and optional JSONL file."""

from __future__ import annotations

from pathlib import Path

from dva.reporting.models import ExecutionLog
from dva.reporting.writer import ReportCollector


class JsonlLogger:
    def __init__(self, run_dir: Path, report: ReportCollector) -> None:
        self._path = run_dir / "execution_logs.jsonl"
        self._report = report
        run_dir.mkdir(parents=True, exist_ok=True)

    def log(self, entry: ExecutionLog) -> None:
        self._report.execution_logs.append(entry)
        with self._path.open("a") as fh:
            fh.write(entry.model_dump_json() + "\n")
