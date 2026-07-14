"""Filesystem path helpers for validation run output."""

from __future__ import annotations

from pathlib import Path


def run_dir(output_path: str, project_name: str, run_id: str) -> Path:
    return Path(output_path) / project_name / f"run_id={run_id}"


def generated_sql_dir(run_directory: Path) -> Path:
    return run_directory / "generated_sql"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
