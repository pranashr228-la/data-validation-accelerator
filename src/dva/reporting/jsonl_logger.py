"""Appends execution log entries as JSON lines during a run."""

from __future__ import annotations

from pathlib import Path

from dva.reporting.models import ExecutionLog


class JsonlLogger:
    def __init__(self, run_dir: Path) -> None:
        self._path = run_dir / "execution_logs.jsonl"
        run_dir.mkdir(parents=True, exist_ok=True)

    def log(self, entry: ExecutionLog) -> None:
        with self._path.open("a") as fh:
            fh.write(entry.model_dump_json() + "\n")
