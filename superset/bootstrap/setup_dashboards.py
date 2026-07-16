#!/usr/bin/env python3
"""Create or refresh DVA Superset database connection, datasets, and dashboards."""

from __future__ import annotations

import json
import os
import time
import uuid

from sqlalchemy import create_engine, text


def wait_for_db(url: str, retries: int = 30, delay: float = 2.0) -> None:
    engine = create_engine(url)
    for attempt in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def _col_metric(column: str, aggregate: str = "SUM", label: str | None = None) -> dict:
    return {
        "expressionType": "SIMPLE",
        "column": {"column_name": column},
        "aggregate": aggregate,
        "label": label or f"{aggregate}({column})",
    }


def _get_or_create_database(db_session, sqlalchemy_uri: str, database_name: str):
    from superset.models.core import Database

    existing = db_session.query(Database).filter_by(database_name=database_name).one_or_none()
    if existing:
        existing.sqlalchemy_uri = sqlalchemy_uri
        db_session.commit()
        return existing
    database = Database(
        database_name=database_name,
        sqlalchemy_uri=sqlalchemy_uri,
        expose_in_sqllab=True,
        allow_run_async=False,
        allow_ctas=False,
        allow_cvas=False,
        allow_dml=False,
    )
    db_session.add(database)
    db_session.commit()
    return database


def _get_or_create_dataset(db_session, database, schema: str, table_name: str, sql: str | None = None):
    from superset.connectors.sqla.models import SqlaTable

    existing = (
        db_session.query(SqlaTable)
        .filter_by(database_id=database.id, schema=schema, table_name=table_name)
        .one_or_none()
    )
    if existing:
        existing.schema = schema
        existing.table_name = table_name
        existing.sql = sql
        db_session.commit()
        _sync_dataset(existing)
        return existing
    dataset = SqlaTable(
        table_name=table_name,
        schema=schema,
        database_id=database.id,
        sql=sql,
    )
    db_session.add(dataset)
    db_session.commit()
    _sync_dataset(dataset)
    return dataset


def _sync_dataset(dataset) -> None:
    try:
        dataset.fetch_metadata()
        from superset import db

        db.session.commit()
        columns = [c.column_name for c in dataset.columns]
        print(f"Synced {dataset.schema}.{dataset.table_name}: {len(columns)} columns")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: could not fetch metadata for {dataset.schema}.{dataset.table_name}: {exc}")


def _table_params(all_columns: list[str], **overrides) -> dict:
    params = {
        "query_mode": "raw",
        "all_columns": all_columns,
        "include_search": True,
        "page_length": 50,
        "order_desc": True,
        "show_cell_bars": True,
        "table_timestamp_format": "smart_date",
    }
    params.update(overrides)
    return params


def _big_number_params(metric_column: str, aggregate: str = "SUM") -> dict:
    return {
        "metric": _col_metric(metric_column, aggregate),
        "adhoc_filters": [],
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": ",.0f",
        "time_format": "smart_date",
        "extra_form_data": {},
        "dashboards": [],
    }


def _dist_bar_params(groupby: list[str], metric_column: str, aggregate: str = "SUM") -> dict:
    return {
        "metrics": [_col_metric(metric_column, aggregate)],
        "groupby": groupby,
        "adhoc_filters": [],
        "row_limit": 10000,
        "order_desc": True,
        "color_scheme": "supersetColors",
        "show_legend": True,
        "show_value": True,
        "rich_tooltip": True,
        "x_axis_label": "",
        "y_axis_label": "",
    }


def _pie_params(groupby: list[str], metric_column: str, aggregate: str = "SUM") -> dict:
    return {
        "metrics": [_col_metric(metric_column, aggregate)],
        "groupby": groupby,
        "adhoc_filters": [],
        "row_limit": 100,
        "show_legend": True,
        "show_labels": True,
        "label_type": "key_percent",
        "number_format": ",.0f",
    }


def _build_query_context(dataset_id: int, params: dict, viz_type: str) -> dict:
    if viz_type == "table":
        columns = params.get("all_columns", [])
        row_limit = params.get("page_length", 1000)
        queries = [
            {
                "filters": [],
                "extras": {"having": "", "where": ""},
                "applied_time_extras": {},
                "columns": columns,
                "metrics": [],
                "orderby": [],
                "annotation_layers": [],
                "row_limit": row_limit,
                "series_limit": 0,
                "order_desc": params.get("order_desc", True),
                "url_params": {},
                "custom_params": {},
                "custom_form_data": {},
            }
        ]
    else:
        queries = [
            {
                "filters": [],
                "extras": {"having": "", "where": ""},
                "applied_time_extras": {},
                "columns": params.get("groupby", []),
                "metrics": params.get("metrics", [params.get("metric")]),
                "orderby": [],
                "annotation_layers": [],
                "row_limit": params.get("row_limit", 10000),
                "series_limit": 0,
                "order_desc": params.get("order_desc", True),
                "url_params": {},
                "custom_params": {},
                "custom_form_data": {},
            }
        ]
    return {
        "datasource": {"id": dataset_id, "type": "table"},
        "force": False,
        "queries": queries,
        "form_data": {
            **params,
            "datasource": f"{dataset_id}__table",
            "viz_type": viz_type,
        },
        "result_format": "json",
        "result_type": "full",
    }


def _upsert_chart(db_session, dataset, chart_name: str, viz_type: str, params: dict):
    from superset.models.slice import Slice

    if viz_type == "table":
        params.setdefault("query_mode", "raw")

    chart = db_session.query(Slice).filter_by(slice_name=chart_name).one_or_none()
    if chart is None:
        chart = Slice(
            slice_name=chart_name,
            viz_type=viz_type,
            datasource_type="table",
            datasource_id=dataset.id,
        )
        db_session.add(chart)
    chart.viz_type = viz_type
    chart.datasource_type = "table"
    chart.datasource_id = dataset.id
    chart.params = json.dumps(params)
    chart.query_context = json.dumps(_build_query_context(dataset.id, params, viz_type))
    db_session.commit()
    return chart


def _delete_existing_dva_dashboards(db_session) -> None:
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice

    slugs = [
        "dva-executive-portfolio",
        "dva-run-command-center",
        "dva-validation-deep-dive",
        "dva-row-forensics",
    ]
    for slug in slugs:
        dashboard = db_session.query(Dashboard).filter_by(slug=slug).one_or_none()
        if dashboard:
            db_session.delete(dashboard)
    db_session.commit()

    chart_names = [
        "KPI Missing Records",
        "KPI Extra Records",
        "KPI Hash Mismatches",
        "KPI Pass Rate",
        "KPI Total Runs",
        "KPI Failed Runs",
        "KPI Open Issues",
        "KPI Datasets Passed",
        "KPI Datasets Failed",
        "KPI Total Mismatches",
        "KPI Rules Failed",
        "KPI Source Count",
        "KPI Target Count",
        "KPI Count Diff Pct",
        "KPI Hash Mismatches",
        "KPI Missing Records",
        "KPI Extra Records",
        "Run Status Timeline",
        "Dataset Status Breakdown",
        "Rule Outcomes by Type",
        "Hash Breakdown",
        "Aggregate Drift Top",
        "Statistical Drift Top",
        "Portfolio Pass Rate",
        "Dataset Status Heatmap",
        "Validation Engine Coverage",
        "Issue Recurrence",
        "Run Summary Table",
        "Dataset Results",
        "Rule Outcomes",
        "Execution Log",
        "Execution Errors",
        "Schema Contract Failures",
        "Count Reconciliation",
        "Row Hash Summary",
        "Aggregate Drift",
        "Statistical Drift",
        "Data Quality Failures",
        "Duplicate Keys",
        "Hash Mismatches",
        "Missing Records",
        "Extra Records",
        "Validation Issues",
        "Validation Trends",
    ]
    for name in chart_names:
        chart = db_session.query(Slice).filter_by(slice_name=name).one_or_none()
        if chart:
            db_session.delete(chart)
    db_session.commit()


def _filter_uid(name: str) -> str:
    return f"NATIVE_FILTER-{uuid.uuid5(uuid.NAMESPACE_DNS, f'dva.{name}').hex[:12]}"


RUN_ID_FILTER = _filter_uid("run_id")
DATASET_FILTER = _filter_uid("dataset_name")


def _select_filter(
    *,
    filter_id: str,
    name: str,
    dataset_id: int,
    column: str,
    cascade_parent_ids: list[str] | None = None,
    sort_ascending: bool = False,
    default_to_first: bool = False,
) -> dict:
    return {
        "id": filter_id,
        "name": name,
        "filterType": "filter_select",
        "targets": [{"datasetId": dataset_id, "column": {"name": column}}],
        "defaultDataMask": {
            "extraFormData": {},
            "filterState": {"value": None},
            "ownState": {},
        },
        "cascadeParentIds": cascade_parent_ids or [],
        "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
        "controlValues": {
            "enableEmptyFilter": False,
            "defaultToFirstItem": default_to_first,
            "multiSelect": True,
            "searchAllOptions": True,
            "inverseSelection": False,
            "sortAscending": sort_ascending,
        },
        "sortMetric": None,
        "type": "NATIVE_FILTER",
        "description": "",
    }


def _build_native_filters(filter_dataset_id: int) -> list[dict]:
    return [
        _select_filter(
            filter_id=RUN_ID_FILTER,
            name="Run ID",
            dataset_id=filter_dataset_id,
            column="run_id",
            sort_ascending=False,
            default_to_first=True,
        ),
        _select_filter(
            filter_id=DATASET_FILTER,
            name="Dataset Name",
            dataset_id=filter_dataset_id,
            column="dataset_name",
            cascade_parent_ids=[RUN_ID_FILTER],
            sort_ascending=True,
        ),
        _select_filter(
            filter_id=_filter_uid("source_connection"),
            name="Source",
            dataset_id=filter_dataset_id,
            column="source_connection",
            cascade_parent_ids=[RUN_ID_FILTER],
            sort_ascending=True,
        ),
        _select_filter(
            filter_id=_filter_uid("target_connection"),
            name="Target",
            dataset_id=filter_dataset_id,
            column="target_connection",
            cascade_parent_ids=[RUN_ID_FILTER],
            sort_ascending=True,
        ),
        _select_filter(
            filter_id=_filter_uid("status"),
            name="Status",
            dataset_id=filter_dataset_id,
            column="status",
            cascade_parent_ids=[RUN_ID_FILTER],
            sort_ascending=True,
        ),
    ]


def _dashboard_link(slug: str) -> str:
    return f"/superset/dashboard/{slug}/?expand_filters=0"


def _build_dashboard(
    db_session,
    title: str,
    slug: str,
    layout_rows: list[list[tuple]],
    *,
    filter_dataset_id: int,
    nav_markdown: str = "",
):
    from superset.models.dashboard import Dashboard

    position: dict = {
        "DASHBOARD_VERSION": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {
            "type": "GRID",
            "id": "GRID_ID",
            "children": [],
            "parents": ["ROOT_ID"],
        },
    }
    grid_children = position["GRID_ID"]["children"]
    all_charts = []

    if nav_markdown:
        row_id = "ROW-NAV"
        col_id = "COLUMN-NAV"
        md_id = "MARKDOWN-NAV"
        grid_children.append(row_id)
        position[row_id] = {
            "type": "ROW",
            "id": row_id,
            "children": [col_id],
            "parents": ["GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        position[col_id] = {
            "type": "COLUMN",
            "id": col_id,
            "children": [md_id],
            "parents": [row_id],
            "meta": {"width": 12, "background": "BACKGROUND_TRANSPARENT"},
        }
        position[md_id] = {
            "type": "MARKDOWN",
            "id": md_id,
            "children": [],
            "parents": [col_id],
            "meta": {"width": 12, "height": 20, "code": nav_markdown},
        }

    for row_idx, row in enumerate(layout_rows):
        row_id = f"ROW-{row_idx + 1}"
        grid_children.append(row_id)
        col_ids = []
        position[row_id] = {
            "type": "ROW",
            "id": row_id,
            "children": col_ids,
            "parents": ["GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        for col_idx, (chart, width, height) in enumerate(row):
            col_id = f"COLUMN-{row_idx + 1}-{col_idx + 1}"
            chart_key = f"CHART-{chart.id}-{row_idx}-{col_idx}"
            col_ids.append(col_id)
            position[col_id] = {
                "type": "COLUMN",
                "id": col_id,
                "children": [chart_key],
                "parents": [row_id],
                "meta": {"width": width, "background": "BACKGROUND_TRANSPARENT"},
            }
            position[chart_key] = {
                "type": "CHART",
                "id": chart_key,
                "children": [],
                "parents": [col_id],
                "meta": {
                    "width": width,
                    "height": height,
                    "chartId": chart.id,
                    "sliceName": chart.slice_name,
                },
            }
            all_charts.append(chart)

    unique_charts: list = []
    seen_chart_ids: set[int] = set()
    for chart in all_charts:
        if chart.id not in seen_chart_ids:
            seen_chart_ids.add(chart.id)
            unique_charts.append(chart)

    dashboard = Dashboard(
        dashboard_title=title,
        slug=slug,
        published=True,
        uuid=uuid.uuid4(),
        position_json=json.dumps(position),
        json_metadata=json.dumps(
            {
                "native_filter_configuration": _build_native_filters(filter_dataset_id),
                "filter_bar_orientation": "HORIZONTAL",
                "cross_filters_enabled": True,
                "chart_configuration": {},
                "global_chart_configuration": {
                    "scope": {"excluded": [], "rootPath": ["ROOT_ID"]},
                    "chartsInScope": [chart.id for chart in unique_charts],
                },
                "timed_refresh_immune_slices": [],
                "expanded_slices": {},
                "refresh_frequency": 0,
                "color_scheme": "supersetColors",
                "label_colors": {},
                "shared_label_colors": {},
            }
        ),
    )
    dashboard.slices = unique_charts
    db_session.add(dashboard)
    db_session.commit()
    return dashboard


def main() -> None:
    dva_url = os.environ.get("DVA_DATABASE_URL", "postgresql://dva:dva@postgres:5432/dva")
    superset_url = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql+psycopg2://dva:dva@postgres:5432/superset",
    )
    wait_for_db(superset_url)
    wait_for_db(dva_url)

    from superset.app import create_app

    app = create_app()
    with app.app_context():
        from superset import db

        sqlalchemy_uri = dva_url.replace("postgresql://", "postgresql+psycopg2://")
        database = _get_or_create_database(db.session, sqlalchemy_uri, "DVA Results")

        view_names = [
            "run_summary",
            "dataset_summary",
            "v_run_portfolio",
            "v_validation_trends",
            "v_validation_coverage",
            "v_issue_recurrence",
            "v_execution_errors",
            "v_chart_rule_results",
            "v_chart_schema_results",
            "v_chart_count_results",
            "v_chart_hash_summary",
            "v_chart_aggregate_results",
            "v_chart_statistical_results",
            "v_chart_dq_results",
            "v_chart_duplicate_keys",
            "v_chart_hash_mismatches",
            "v_chart_missing_records",
            "v_chart_extra_records",
            "v_chart_validation_issues",
            "v_chart_execution_logs",
            "v_dashboard_filters",
            "v_run_kpis",
            "v_dataset_status_counts",
            "v_hash_breakdown",
            "v_aggregate_drift_top",
            "v_statistical_drift_top",
            "v_rule_outcome_counts",
            "v_validation_trends_chart",
        ]
        datasets = {
            name: _get_or_create_dataset(db.session, database, "dva", name) for name in view_names
        }

        filter_dataset_id = datasets["v_dashboard_filters"].id
        _delete_existing_dva_dashboards(db.session)

        kpis = datasets["v_run_kpis"]
        charts = {
            "kpi_pass_rate": _upsert_chart(
                db.session, kpis, "KPI Pass Rate", "big_number_total",
                _big_number_params("pass_rate_pct", "AVG"),
            ),
            "kpi_total_runs": _upsert_chart(
                db.session, datasets["run_summary"], "KPI Total Runs", "big_number_total",
                _big_number_params("dataset_count", "COUNT"),
            ),
            "kpi_failed_runs": _upsert_chart(
                db.session, kpis, "KPI Failed Runs", "big_number_total",
                _big_number_params("failed_datasets", "SUM"),
            ),
            "kpi_open_issues": _upsert_chart(
                db.session, kpis, "KPI Open Issues", "big_number_total",
                _big_number_params("open_issues", "SUM"),
            ),
            "kpi_datasets_passed": _upsert_chart(
                db.session, kpis, "KPI Datasets Passed", "big_number_total",
                _big_number_params("passed_datasets", "SUM"),
            ),
            "kpi_datasets_failed": _upsert_chart(
                db.session, kpis, "KPI Datasets Failed", "big_number_total",
                _big_number_params("failed_datasets", "SUM"),
            ),
            "kpi_total_mismatches": _upsert_chart(
                db.session, kpis, "KPI Total Mismatches", "big_number_total",
                _big_number_params("total_mismatches", "SUM"),
            ),
            "kpi_rules_failed": _upsert_chart(
                db.session, kpis, "KPI Rules Failed", "big_number_total",
                _big_number_params("failed_rules", "SUM"),
            ),
            "kpi_missing_records": _upsert_chart(
                db.session, datasets["v_chart_hash_summary"], "KPI Missing Records", "big_number_total",
                _big_number_params("missing_count", "SUM"),
            ),
            "kpi_extra_records": _upsert_chart(
                db.session, datasets["v_chart_hash_summary"], "KPI Extra Records", "big_number_total",
                _big_number_params("extra_count", "SUM"),
            ),
            "kpi_hash_mismatches": _upsert_chart(
                db.session, datasets["v_chart_hash_summary"], "KPI Hash Mismatches", "big_number_total",
                _big_number_params("mismatch_count", "SUM"),
            ),
            "run_timeline": _upsert_chart(
                db.session, datasets["run_summary"], "Run Status Timeline", "dist_bar",
                _dist_bar_params(["status"], "dataset_count", "SUM"),
            ),
            "dataset_status_breakdown": _upsert_chart(
                db.session, datasets["v_dataset_status_counts"], "Dataset Status Breakdown", "pie",
                _pie_params(["status"], "dataset_count", "SUM"),
            ),
            "rule_outcomes_by_type": _upsert_chart(
                db.session, datasets["v_rule_outcome_counts"], "Rule Outcomes by Type", "dist_bar",
                _dist_bar_params(["rule_type", "rule_status"], "outcome_count", "SUM"),
            ),
            "hash_breakdown": _upsert_chart(
                db.session, datasets["v_hash_breakdown"], "Hash Breakdown", "dist_bar",
                _dist_bar_params(["breakdown_type"], "breakdown_count", "SUM"),
            ),
            "aggregate_drift_top": _upsert_chart(
                db.session, datasets["v_aggregate_drift_top"], "Aggregate Drift Top", "dist_bar",
                _dist_bar_params(["column_name", "metric"], "abs_pct_difference", "MAX"),
            ),
            "statistical_drift_top": _upsert_chart(
                db.session, datasets["v_statistical_drift_top"], "Statistical Drift Top", "dist_bar",
                _dist_bar_params(["column_name", "metric"], "abs_pct_difference", "MAX"),
            ),
            "portfolio_table": _upsert_chart(
                db.session, datasets["v_run_portfolio"], "Portfolio Pass Rate", "table",
                _table_params(
                    ["project_name", "total_runs", "passed_runs", "failed_runs", "error_runs", "pass_rate_pct"],
                    include_search=False,
                ),
            ),
            "dataset_heatmap": _upsert_chart(
                db.session, datasets["v_validation_trends_chart"], "Dataset Status Heatmap", "table",
                _table_params(
                    ["run_id", "dataset_name", "status", "source_connection", "target_connection", "mismatch_count"],
                ),
            ),
            "validation_coverage": _upsert_chart(
                db.session, datasets["v_validation_coverage"], "Validation Engine Coverage", "table",
                _table_params(
                    ["run_id", "dataset_name", "rule_type", "check_count", "passed", "failed", "errored"],
                    include_search=False,
                ),
            ),
            "issue_recurrence": _upsert_chart(
                db.session, datasets["v_issue_recurrence"], "Issue Recurrence", "table",
                _table_params(
                    ["run_id", "dataset_name", "rule_name", "severity", "recurrence_label", "recurrence_count"],
                ),
            ),
            "execution_errors": _upsert_chart(
                db.session, datasets["v_execution_errors"], "Execution Errors", "table",
                _table_params(
                    ["run_id", "dataset_name", "severity", "issue_source", "issue_detail"],
                    page_length=100,
                ),
            ),
            "run_summary": _upsert_chart(
                db.session, datasets["run_summary"], "Run Summary Table", "table",
                _table_params(
                    ["run_id", "project_name", "status", "start_time", "dataset_count", "passed_count", "failed_count"],
                ),
            ),
            "dataset_results": _upsert_chart(
                db.session, datasets["dataset_summary"], "Dataset Results", "table",
                _table_params(
                    ["run_id", "dataset_name", "status", "source_count", "target_count", "missing_count", "extra_count", "mismatch_count"],
                ),
            ),
            "rule_outcomes": _upsert_chart(
                db.session, datasets["v_chart_rule_results"], "Rule Outcomes", "table",
                _table_params(["run_id", "dataset_name", "rule_name", "rule_type", "status", "details"]),
            ),
            "execution_log": _upsert_chart(
                db.session, datasets["v_chart_execution_logs"], "Execution Log", "table",
                _table_params(["run_id", "timestamp", "level", "dataset_name", "message"]),
            ),
            "schema_failures": _upsert_chart(
                db.session, datasets["v_chart_schema_results"], "Schema Contract Failures", "table",
                _table_params(["run_id", "dataset_name", "check_name", "status", "details"]),
            ),
            "count_reconciliation": _upsert_chart(
                db.session, datasets["v_chart_count_results"], "Count Reconciliation", "table",
                _table_params(
                    ["run_id", "dataset_name", "source_count", "target_count", "difference", "pct_difference", "status"],
                ),
            ),
            "hash_summary": _upsert_chart(
                db.session, datasets["v_chart_hash_summary"], "Row Hash Summary", "table",
                _table_params(
                    ["run_id", "dataset_name", "matched_count", "missing_count", "extra_count", "mismatch_count", "status"],
                ),
            ),
            "aggregate_drift": _upsert_chart(
                db.session, datasets["v_chart_aggregate_results"], "Aggregate Drift", "table",
                _table_params(
                    ["run_id", "dataset_name", "group_key", "column_name", "metric", "source_value", "target_value", "pct_difference", "status"],
                ),
            ),
            "statistical_drift": _upsert_chart(
                db.session, datasets["v_chart_statistical_results"], "Statistical Drift", "table",
                _table_params(
                    ["run_id", "dataset_name", "column_name", "metric", "source_value", "target_value", "pct_difference", "status"],
                ),
            ),
            "dq_failures": _upsert_chart(
                db.session, datasets["v_chart_dq_results"], "Data Quality Failures", "table",
                _table_params(["run_id", "dataset_name", "rule_name", "side", "failed_count", "severity", "status"]),
            ),
            "duplicate_keys": _upsert_chart(
                db.session, datasets["v_chart_duplicate_keys"], "Duplicate Keys", "table",
                _table_params(["run_id", "dataset_name", "side", "primary_key", "duplicate_count"]),
            ),
            "hash_mismatches": _upsert_chart(
                db.session, datasets["v_chart_hash_mismatches"], "Hash Mismatches", "table",
                _table_params(["run_id", "dataset_name", "primary_key", "source_hash", "target_hash"]),
            ),
            "missing_records": _upsert_chart(
                db.session, datasets["v_chart_missing_records"], "Missing Records", "table",
                _table_params(["run_id", "dataset_name", "primary_key", "record"]),
            ),
            "extra_records": _upsert_chart(
                db.session, datasets["v_chart_extra_records"], "Extra Records", "table",
                _table_params(["run_id", "dataset_name", "primary_key", "record"]),
            ),
            "validation_issues": _upsert_chart(
                db.session, datasets["v_chart_validation_issues"], "Validation Issues", "table",
                _table_params(["run_id", "dataset_name", "rule_name", "issue_type", "severity", "failed_count"]),
            ),
            "validation_trends": _upsert_chart(
                db.session, datasets["v_validation_trends"], "Validation Trends", "table",
                _table_params(["project_name", "run_id", "dataset_name", "start_time", "status", "mismatch_count"]),
            ),
        }

        filter_hint = (
            "> Use the **Filters** button (top-right) to scope by Run ID or Dataset when needed.\n\n"
        )

        _build_dashboard(
            db.session,
            "Executive Portfolio",
            "dva-executive-portfolio",
            [
                [
                    (charts["kpi_pass_rate"], 3, 30),
                    (charts["kpi_total_runs"], 3, 30),
                    (charts["kpi_failed_runs"], 3, 30),
                    (charts["kpi_open_issues"], 3, 30),
                ],
                [(charts["run_timeline"], 6, 50), (charts["dataset_heatmap"], 6, 50)],
                [(charts["portfolio_table"], 6, 50), (charts["issue_recurrence"], 6, 50)],
                [(charts["execution_errors"], 12, 50)],
            ],
            filter_dataset_id=filter_dataset_id,
            nav_markdown=filter_hint + f"[Drill into Run Command Center →]({_dashboard_link('dva-run-command-center')})",
        )
        _build_dashboard(
            db.session,
            "Run Command Center",
            "dva-run-command-center",
            [
                [
                    (charts["kpi_datasets_passed"], 3, 30),
                    (charts["kpi_datasets_failed"], 3, 30),
                    (charts["kpi_total_mismatches"], 3, 30),
                    (charts["kpi_rules_failed"], 3, 30),
                ],
                [(charts["dataset_status_breakdown"], 6, 50), (charts["rule_outcomes_by_type"], 6, 50)],
                [(charts["dataset_results"], 6, 50), (charts["rule_outcomes"], 6, 50)],
                [(charts["run_summary"], 6, 40), (charts["execution_log"], 6, 40)],
            ],
            filter_dataset_id=filter_dataset_id,
            nav_markdown=(
                filter_hint
                + f"[↑ Executive Portfolio]({_dashboard_link('dva-executive-portfolio')}) · "
                f"[↓ Validation Deep Dive]({_dashboard_link('dva-validation-deep-dive')})"
            ),
        )
        _build_dashboard(
            db.session,
            "Validation Deep Dive",
            "dva-validation-deep-dive",
            [
                [
                    (charts["kpi_total_mismatches"], 3, 30),
                    (charts["hash_breakdown"], 9, 50),
                ],
                [(charts["aggregate_drift_top"], 6, 50), (charts["statistical_drift_top"], 6, 50)],
                [
                    (charts["count_reconciliation"], 6, 50),
                    (charts["hash_summary"], 6, 50),
                ],
                [(charts["aggregate_drift"], 6, 50), (charts["statistical_drift"], 6, 50)],
                [(charts["dq_failures"], 6, 40), (charts["duplicate_keys"], 6, 40)],
            ],
            filter_dataset_id=filter_dataset_id,
            nav_markdown=(
                filter_hint
                + f"[↑ Run Command Center]({_dashboard_link('dva-run-command-center')}) · "
                f"[↓ Row Forensics]({_dashboard_link('dva-row-forensics')})"
            ),
        )
        _build_dashboard(
            db.session,
            "Row-Level Forensics",
            "dva-row-forensics",
            [
                [
                    (charts["kpi_missing_records"], 4, 30),
                    (charts["kpi_extra_records"], 4, 30),
                    (charts["kpi_hash_mismatches"], 4, 30),
                ],
                [(charts["hash_mismatches"], 12, 60)],
                [(charts["missing_records"], 6, 50), (charts["extra_records"], 6, 50)],
                [(charts["validation_issues"], 12, 50)],
            ],
            filter_dataset_id=filter_dataset_id,
            nav_markdown=filter_hint + f"[↑ Validation Deep Dive]({_dashboard_link('dva-validation-deep-dive')})",
        )

        print("Superset DVA dashboards refreshed successfully.")


if __name__ == "__main__":
    main()
