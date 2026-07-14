"""Basic statistical comparison, dataset-level (section 10.6)."""

from __future__ import annotations

from dva.engine.context import DatasetContext
from dva.normalization.sql_builder import build_statistical_sql
from dva.reporting.models import StatisticalResult
from dva.validations.base import DEFAULT_TOLERANCE, compare_values, now_iso, record_issue, record_rule_result


def run_statistical(ctx: DatasetContext) -> None:
    config = ctx.dataset.validations.statistical
    if not config.enabled:
        return

    start = now_iso()
    source_sql = build_statistical_sql(ctx.source_base_sql, config.metrics, ctx.source_dialect)
    target_sql = build_statistical_sql(ctx.target_base_sql, config.metrics, ctx.target_dialect)
    ctx.run.write_generated_sql(ctx.dataset.name, "statistical_source", source_sql)
    ctx.run.write_generated_sql(ctx.dataset.name, "statistical_target", target_sql)

    source_rows = ctx.source.fetch_arrow(source_sql).to_pylist()
    target_rows = ctx.target.fetch_arrow(target_sql).to_pylist()
    s_row = source_rows[0] if source_rows else {}
    t_row = target_rows[0] if target_rows else {}

    overall_status = "PASS"
    failing = 0
    for metric in config.metrics:
        tolerance = metric.tolerance or DEFAULT_TOLERANCE
        for check in metric.checks:
            alias = f"{metric.column}__{check}"
            s_val = s_row.get(alias)
            t_val = t_row.get(alias)
            difference, pct_difference, status = compare_values(s_val, t_val, tolerance)
            if status != "PASS":
                if status == "FAIL":
                    overall_status = "FAIL"
                elif overall_status == "PASS":
                    overall_status = "WARN"
                failing += 1
            ctx.run.report.statistical_results.append(
                StatisticalResult(
                    run_id=ctx.run.run_id,
                    dataset_name=ctx.dataset.name,
                    column=metric.column,
                    metric=check,
                    source_value=s_val,
                    target_value=t_val,
                    difference=difference,
                    pct_difference=pct_difference,
                    status=status,
                )
            )

    record_rule_result(
        ctx, rule_name="statistical", rule_type="statistical", status=overall_status,
        details=f"{failing} metric comparisons out of tolerance", start_iso=start,
    )
    if overall_status != "PASS":
        record_issue(
            ctx, rule_name="statistical", rule_type="statistical",
            issue_type="statistical_mismatch",
            severity="HIGH" if overall_status == "FAIL" else "MEDIUM", failed_count=failing,
        )
