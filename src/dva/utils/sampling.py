"""Helpers for extracting small sample payloads for validation issues."""

from __future__ import annotations

from typing import Any


def sample_rows(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """Return up to ``limit`` rows, preserving order, for issue sampling."""
    return rows[:limit]
