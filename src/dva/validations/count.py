"""Row count comparison (section 10.1)."""

from __future__ import annotations

from dva.config.models import ToleranceConfig
from dva.engine.context import DatasetContext
from dva.normalization.sql_builder import build_count_sql
from dva.reporting.models import CountResult
from dva.validations.base import now_iso, record_issue, record_rule_result

_DEFAULT_TOLERANCE = ToleranceConfig(type="percentage", warning=0.0, failure=0.0)


def _status_for(pct_diff: float, tolerance: ToleranceConfig) -> str:
    if tolerance.type == "absolute":
        magnitude = abs(pct_diff)
    else:
        magnitude = abs(pct_diff)
    if magnitude > tolerance.failure:
        return "FAIL"
    if magnitude > tolerance.warning:
        return "WARN"
    return "PASS"


def run_count(ctx: DatasetContext) -> None:
    config = ctx.dataset.validations.count
    if not config.enabled:
        return

    start = now_iso()
    tolerance = config.tolerance or _DEFAULT_TOLERANCE

    source_sql = build_count_sql(ctx.source_base_sql, ctx.source_dialect)
    target_sql = build_count_sql(ctx.target_base_sql, ctx.target_dialect)
    ctx.run.write_generated_sql(ctx.dataset.name, "count_source", source_sql)
    ctx.run.write_generated_sql(ctx.dataset.name, "count_target", target_sql)

    source_count = int(ctx.source.fetch_scalar(source_sql) or 0)
    target_count = int(ctx.target.fetch_scalar(target_sql) or 0)
    difference = source_count - target_count

    if tolerance.type == "percentage":
        pct_diff = (abs(difference) / source_count * 100.0) if source_count else (
            100.0 if target_count else 0.0
        )
    else:
        pct_diff = float(abs(difference))

    status = _status_for(pct_diff, tolerance)

    ctx.run.report.count_results.append(
        CountResult(
            run_id=ctx.run.run_id,
            dataset_name=ctx.dataset.name,
            source_count=source_count,
            target_count=target_count,
            difference=difference,
            pct_difference=pct_diff,
            status=status,
        )
    )
    record_rule_result(
        ctx, rule_name="count", rule_type="count", status=status,
        details=f"source={source_count} target={target_count} diff={difference}",
        start_iso=start,
    )
    if status in ("FAIL", "WARN"):
        record_issue(
            ctx, rule_name="count", rule_type="count", issue_type="count_mismatch",
            severity="HIGH" if status == "FAIL" else "MEDIUM", failed_count=abs(difference),
            sample_values=[{"source_count": source_count, "target_count": target_count}],
        )
