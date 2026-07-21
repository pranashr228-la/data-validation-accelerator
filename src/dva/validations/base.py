"""Shared helpers for validation engines: rule results and issue recording."""

from __future__ import annotations

import json
from typing import Any

from dva.config.models import ToleranceConfig
from dva.engine.context import DatasetContext
from dva.issues.fingerprint import compute_fingerprint
from dva.issues.model import ValidationIssue
from dva.reporting.models import RuleResult, Status
from dva.utils.time import to_iso, utcnow

DEFAULT_TOLERANCE = ToleranceConfig(type="percentage", warning=0.0, failure=0.0)


def compare_values(
    source_value: float | None, target_value: float | None, tolerance: ToleranceConfig
) -> tuple[float | None, float | None, Status]:
    """Diff two numeric values against a tolerance, returning (diff, pct_diff, status)."""
    if source_value is None or target_value is None:
        status: Status = "PASS" if source_value == target_value else "FAIL"
        return None, None, status

    source_value = float(source_value)
    target_value = float(target_value)
    difference = source_value - target_value
    if tolerance.type == "absolute":
        magnitude = abs(difference)
        pct_difference = (abs(difference) / source_value * 100.0) if source_value else None
    else:
        pct_difference = (abs(difference) / source_value * 100.0) if source_value else (
            100.0 if target_value else 0.0
        )
        magnitude = pct_difference

    if magnitude > tolerance.failure:
        status = "FAIL"
    elif magnitude > tolerance.warning:
        status = "WARN"
    else:
        status = "PASS"
    return difference, pct_difference, status


def record_rule_result(
    ctx: DatasetContext,
    *,
    rule_name: str,
    rule_type: str,
    status: Status,
    details: str = "",
    start_iso: str,
) -> None:
    ctx.run.report.rule_results.append(
        RuleResult(
            run_id=ctx.run.run_id,
            dataset_name=ctx.dataset.name,
            rule_name=rule_name,
            rule_type=rule_type,
            status=status,
            details=details,
            start_time=start_iso,
            end_time=to_iso(utcnow()),
        )
    )


def record_issue(
    ctx: DatasetContext,
    *,
    rule_name: str,
    rule_type: str,
    issue_type: str,
    severity: str,
    failed_count: int,
    sample_values: list[Any] | None = None,
) -> None:
    fingerprint = compute_fingerprint(
        dataset_name=ctx.dataset.name,
        rule_name=rule_name,
        rule_type=rule_type,
        issue_type=issue_type,
    )
    ctx.run.report.validation_issues.append(
        ValidationIssue(
            issue_fingerprint=fingerprint,
            run_id=ctx.run.run_id,
            dataset_name=ctx.dataset.name,
            rule_name=rule_name,
            rule_type=rule_type,
            issue_type=issue_type,
            severity=severity,
            failed_count=failed_count,
            sample_values=json.dumps(sample_values or []),
            first_seen_run_id=ctx.run.run_id,
            last_seen_run_id=ctx.run.run_id,
        )
    )


def now_iso() -> str:
    return to_iso(utcnow())
