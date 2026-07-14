"""Row-level hash comparison (section 10.3).

Row values are fetched once per side, normalized and hashed in Python
(``dva.normalization.rules``) so results don't depend on vendor-specific
hash functions being installed, then the two hash extracts are written to
Parquet and compared with DuckDB using the exact missing/extra/mismatch
join patterns from the MVP plan. Composite primary keys are supported.
"""

from __future__ import annotations

import json
import shutil
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from dva.engine.context import DatasetContext
from dva.normalization.rules import hash_row
from dva.normalization.sql_builder import build_key_and_columns_sql
from dva.reporting.models import ExtraRecord, HashMismatch, HashSummary, MissingRecord
from dva.validations.base import now_iso, record_issue, record_rule_result


def _fetch_rows(ctx: DatasetContext, side: str) -> list[dict[str, Any]]:
    connector = ctx.source if side == "source" else ctx.target
    dialect = ctx.source_dialect if side == "source" else ctx.target_dialect
    base_sql = ctx.source_base_sql if side == "source" else ctx.target_base_sql

    pk = ctx.dataset.primary_key
    compare_cols = ctx.dataset.compare_columns
    all_cols = pk + [c for c in compare_cols if c not in pk]

    sql = build_key_and_columns_sql(base_sql, all_cols, dialect)
    ctx.run.write_generated_sql(ctx.dataset.name, f"row_hash_{side}", sql)
    return connector.fetch_arrow(sql).to_pylist()


def _build_extract(
    rows: list[dict[str, Any]], primary_key: list[str], compare_columns: list[str], hash_defaults
) -> list[dict[str, Any]]:
    extract = []
    for row in rows:
        row_hash = hash_row([row[c] for c in compare_columns], hash_defaults)
        entry = {c: row[c] for c in primary_key}
        entry["row_hash"] = row_hash
        extract.append(entry)
    return extract


def _join_condition(primary_key: list[str]) -> str:
    return " AND ".join(f's."{c}" = t."{c}"' for c in primary_key)


def run_row_hash(ctx: DatasetContext) -> None:
    config = ctx.dataset.validations.row_hash
    if not config.enabled:
        return

    start = now_iso()
    pk = ctx.dataset.primary_key
    hash_defaults = ctx.run.hash_defaults

    source_rows = _fetch_rows(ctx, "source")
    target_rows = _fetch_rows(ctx, "target")

    source_by_pk = {tuple(row[c] for c in pk): row for row in source_rows}
    target_by_pk = {tuple(row[c] for c in pk): row for row in target_rows}

    source_extract = _build_extract(source_rows, pk, ctx.dataset.compare_columns, hash_defaults)
    target_extract = _build_extract(target_rows, pk, ctx.dataset.compare_columns, hash_defaults)

    tmp_dir = ctx.run.run_dir / "_hash_extracts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    source_path = tmp_dir / f"{ctx.dataset.name}_source.parquet"
    target_path = tmp_dir / f"{ctx.dataset.name}_target.parquet"
    pq.write_table(pa.Table.from_pylist(source_extract or [{}]), source_path)
    pq.write_table(pa.Table.from_pylist(target_extract or [{}]), target_path)

    conn = ctx.run.scratch_duckdb
    join_cond = _join_condition(pk)
    pk_select = ", ".join(f's."{c}"' for c in pk)

    missing_sql = f"""
        SELECT {pk_select}
        FROM read_parquet('{source_path.as_posix()}') s
        LEFT JOIN read_parquet('{target_path.as_posix()}') t ON {join_cond}
        WHERE t."{pk[0]}" IS NULL
    """
    extra_pk_select = ", ".join(f't."{c}"' for c in pk)
    extra_sql = f"""
        SELECT {extra_pk_select}
        FROM read_parquet('{target_path.as_posix()}') t
        LEFT JOIN read_parquet('{source_path.as_posix()}') s ON {join_cond}
        WHERE s."{pk[0]}" IS NULL
    """
    mismatch_sql = f"""
        SELECT {pk_select}, s.row_hash AS source_hash, t.row_hash AS target_hash
        FROM read_parquet('{source_path.as_posix()}') s
        JOIN read_parquet('{target_path.as_posix()}') t ON {join_cond}
        WHERE s.row_hash <> t.row_hash
    """

    missing_rows = conn.execute(missing_sql).to_arrow_table().to_pylist() if source_rows else []
    extra_rows = conn.execute(extra_sql).to_arrow_table().to_pylist() if target_rows else []
    mismatch_rows = (
        conn.execute(mismatch_sql).to_arrow_table().to_pylist() if (source_rows and target_rows) else []
    )
    shutil.rmtree(tmp_dir, ignore_errors=True)

    limit = config.max_mismatch_samples
    for row in missing_rows[:limit]:
        key = tuple(row[c] for c in pk)
        ctx.run.report.missing_records.append(
            MissingRecord(
                run_id=ctx.run.run_id,
                dataset_name=ctx.dataset.name,
                primary_key=json.dumps(row, default=str),
                record=json.dumps(source_by_pk.get(key, {}), default=str),
            )
        )
    for row in extra_rows[:limit]:
        key = tuple(row[c] for c in pk)
        ctx.run.report.extra_records.append(
            ExtraRecord(
                run_id=ctx.run.run_id,
                dataset_name=ctx.dataset.name,
                primary_key=json.dumps(row, default=str),
                record=json.dumps(target_by_pk.get(key, {}), default=str),
            )
        )
    for row in mismatch_rows[:limit]:
        key = tuple(row[c] for c in pk)
        pk_json = json.dumps({c: row[c] for c in pk}, default=str)
        source_record = target_record = None
        if config.write_full_mismatches:
            source_record = json.dumps(source_by_pk.get(key, {}), default=str)
            target_record = json.dumps(target_by_pk.get(key, {}), default=str)
        ctx.run.report.hash_mismatches.append(
            HashMismatch(
                run_id=ctx.run.run_id,
                dataset_name=ctx.dataset.name,
                primary_key=pk_json,
                source_hash=row["source_hash"],
                target_hash=row["target_hash"],
                source_record=source_record,
                target_record=target_record,
            )
        )

    matched_count = len(source_rows) - len(missing_rows) - len(mismatch_rows)
    status = "PASS" if not (missing_rows or extra_rows or mismatch_rows) else "FAIL"

    ctx.run.report.hash_summaries.append(
        HashSummary(
            run_id=ctx.run.run_id,
            dataset_name=ctx.dataset.name,
            source_row_count=len(source_rows),
            target_row_count=len(target_rows),
            matched_count=max(matched_count, 0),
            missing_count=len(missing_rows),
            extra_count=len(extra_rows),
            mismatch_count=len(mismatch_rows),
            status=status,
        )
    )
    record_rule_result(
        ctx, rule_name="row_hash", rule_type="row_hash", status=status,
        details=(
            f"missing={len(missing_rows)} extra={len(extra_rows)} "
            f"mismatches={len(mismatch_rows)}"
        ),
        start_iso=start,
    )
    if missing_rows:
        record_issue(
            ctx, rule_name="row_hash", rule_type="row_hash", issue_type="missing_records",
            severity="HIGH", failed_count=len(missing_rows),
            sample_values=missing_rows[:10],
        )
    if extra_rows:
        record_issue(
            ctx, rule_name="row_hash", rule_type="row_hash", issue_type="extra_records",
            severity="HIGH", failed_count=len(extra_rows),
            sample_values=extra_rows[:10],
        )
    if mismatch_rows:
        record_issue(
            ctx, rule_name="row_hash", rule_type="row_hash", issue_type="hash_mismatch",
            severity="HIGH", failed_count=len(mismatch_rows),
            sample_values=[{c: row[c] for c in pk} for row in mismatch_rows[:10]],
        )
