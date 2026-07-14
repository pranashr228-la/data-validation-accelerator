"""Aggregate comparison, dataset-level or grouped (section 10.5)."""

from __future__ import annotations

import json

from dva.engine.context import DatasetContext
from dva.normalization.sql_builder import build_aggregate_sql
from dva.reporting.models import AggregateResult
from dva.validations.base import DEFAULT_TOLERANCE, compare_values, now_iso, record_issue, record_rule_result


def _group_key(row: dict, group_by: list[str]) -> tuple:
    return tuple(row[c] for c in group_by) if group_by else ("ALL",)


def run_aggregate(ctx: DatasetContext) -> None:
    config = ctx.dataset.validations.aggregate
    if not config.enabled:
        return

    start = now_iso()
    source_sql = build_aggregate_sql(
        ctx.source_base_sql, config.group_by, config.metrics, ctx.source_dialect
    )
    target_sql = build_aggregate_sql(
        ctx.target_base_sql, config.group_by, config.metrics, ctx.target_dialect
    )
    ctx.run.write_generated_sql(ctx.dataset.name, "aggregate_source", source_sql)
    ctx.run.write_generated_sql(ctx.dataset.name, "aggregate_target", target_sql)

    source_rows = ctx.source.fetch_arrow(source_sql).to_pylist()
    target_rows = ctx.target.fetch_arrow(target_sql).to_pylist()

    source_by_key = {_group_key(r, config.group_by): r for r in source_rows}
    target_by_key = {_group_key(r, config.group_by): r for r in target_rows}
    all_keys = sorted(set(source_by_key) | set(target_by_key), key=str)

    overall_status = "PASS"
    failing = 0
    for key in all_keys:
        s_row = source_by_key.get(key, {})
        t_row = target_by_key.get(key, {})
        group_key_str = json.dumps(
            dict(zip(config.group_by, key)) if config.group_by else {"group": "ALL"}
        )
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
                ctx.run.report.aggregate_results.append(
                    AggregateResult(
                        run_id=ctx.run.run_id,
                        dataset_name=ctx.dataset.name,
                        group_key=group_key_str,
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
        ctx, rule_name="aggregate", rule_type="aggregate", status=overall_status,
        details=f"{failing} of {len(all_keys) * sum(len(m.checks) for m in config.metrics)} "
        "metric comparisons out of tolerance",
        start_iso=start,
    )
    if overall_status != "PASS":
        record_issue(
            ctx, rule_name="aggregate", rule_type="aggregate", issue_type="aggregate_mismatch",
            severity="HIGH" if overall_status == "FAIL" else "MEDIUM", failed_count=failing,
        )
