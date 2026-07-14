"""Duplicate primary key validation (section 10.2)."""

from __future__ import annotations

import json

from dva.engine.context import DatasetContext
from dva.normalization.sql_builder import build_duplicate_keys_sql
from dva.reporting.models import DuplicateKey
from dva.validations.base import now_iso, record_issue, record_rule_result


def _find_duplicates(ctx: DatasetContext, side: str) -> int:
    connector = ctx.source if side == "source" else ctx.target
    dialect = ctx.source_dialect if side == "source" else ctx.target_dialect
    base_sql = ctx.source_base_sql if side == "source" else ctx.target_base_sql

    sql = build_duplicate_keys_sql(base_sql, ctx.dataset.primary_key, dialect)
    ctx.run.write_generated_sql(ctx.dataset.name, f"duplicate_keys_{side}", sql)

    table = connector.fetch_arrow(sql)
    rows = table.to_pylist()
    for row in rows:
        duplicate_count = row.pop("duplicate_count")
        ctx.run.report.duplicate_keys.append(
            DuplicateKey(
                run_id=ctx.run.run_id,
                dataset_name=ctx.dataset.name,
                side=side,  # type: ignore[arg-type]
                primary_key=json.dumps(row, default=str),
                duplicate_count=duplicate_count,
            )
        )
    return len(rows)


def run_duplicate_keys(ctx: DatasetContext) -> None:
    config = ctx.dataset.validations.duplicate_keys
    if not config.enabled:
        return

    start = now_iso()
    source_dupes = _find_duplicates(ctx, "source")
    target_dupes = _find_duplicates(ctx, "target")

    status = "FAIL" if (source_dupes or target_dupes) else "PASS"
    record_rule_result(
        ctx, rule_name="duplicate_keys", rule_type="duplicate_keys", status=status,
        details=f"source_duplicate_keys={source_dupes} target_duplicate_keys={target_dupes}",
        start_iso=start,
    )
    if status == "FAIL":
        record_issue(
            ctx, rule_name="duplicate_keys", rule_type="duplicate_keys",
            issue_type="duplicate_primary_key", severity="HIGH",
            failed_count=source_dupes + target_dupes,
        )
