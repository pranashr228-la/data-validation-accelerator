-- Superset-friendly views for dashboard datasets.

ALTER TABLE dva.dataset_summary
    ADD COLUMN IF NOT EXISTS source_connection TEXT,
    ADD COLUMN IF NOT EXISTS target_connection TEXT;

CREATE INDEX IF NOT EXISTS idx_dataset_summary_source ON dva.dataset_summary (source_connection);
CREATE INDEX IF NOT EXISTS idx_dataset_summary_target ON dva.dataset_summary (target_connection);

DROP VIEW IF EXISTS dva.v_validation_trends_chart CASCADE;
DROP VIEW IF EXISTS dva.v_rule_outcome_counts CASCADE;
DROP VIEW IF EXISTS dva.v_statistical_drift_top CASCADE;
DROP VIEW IF EXISTS dva.v_aggregate_drift_top CASCADE;
DROP VIEW IF EXISTS dva.v_hash_breakdown CASCADE;
DROP VIEW IF EXISTS dva.v_dataset_status_counts CASCADE;
DROP VIEW IF EXISTS dva.v_run_kpis CASCADE;
DROP VIEW IF EXISTS dva.v_dashboard_filters CASCADE;
DROP VIEW IF EXISTS dva.v_chart_execution_logs CASCADE;
DROP VIEW IF EXISTS dva.v_chart_validation_issues CASCADE;
DROP VIEW IF EXISTS dva.v_chart_extra_records CASCADE;
DROP VIEW IF EXISTS dva.v_chart_missing_records CASCADE;
DROP VIEW IF EXISTS dva.v_chart_hash_mismatches CASCADE;
DROP VIEW IF EXISTS dva.v_chart_duplicate_keys CASCADE;
DROP VIEW IF EXISTS dva.v_chart_dq_results CASCADE;
DROP VIEW IF EXISTS dva.v_chart_statistical_results CASCADE;
DROP VIEW IF EXISTS dva.v_chart_aggregate_results CASCADE;
DROP VIEW IF EXISTS dva.v_chart_hash_summary CASCADE;
DROP VIEW IF EXISTS dva.v_chart_count_results CASCADE;
DROP VIEW IF EXISTS dva.v_chart_schema_results CASCADE;
DROP VIEW IF EXISTS dva.v_chart_rule_results CASCADE;
DROP VIEW IF EXISTS dva.v_issue_recurrence CASCADE;
DROP VIEW IF EXISTS dva.v_execution_errors CASCADE;
DROP VIEW IF EXISTS dva.v_validation_coverage CASCADE;
DROP VIEW IF EXISTS dva.v_run_portfolio CASCADE;
DROP VIEW IF EXISTS dva.v_failed_datasets CASCADE;
DROP VIEW IF EXISTS dva.v_failed_rules CASCADE;
DROP VIEW IF EXISTS dva.v_validation_trends CASCADE;
DROP VIEW IF EXISTS dva.v_latest_run_summary CASCADE;

CREATE OR REPLACE VIEW dva.v_latest_run_summary AS
SELECT *
FROM dva.run_summary
ORDER BY start_time DESC
LIMIT 1;

CREATE OR REPLACE VIEW dva.v_validation_trends AS
SELECT
    ds.dataset_name,
    rs.start_time,
    rs.project_name,
    rs.run_id,
    ds.status,
    ds.source_connection,
    ds.target_connection,
    ds.source_count,
    ds.target_count,
    ds.mismatch_count
FROM dva.dataset_summary ds
JOIN dva.run_summary rs ON ds.run_id = rs.run_id
ORDER BY ds.dataset_name, rs.start_time;

CREATE OR REPLACE VIEW dva.v_failed_rules AS
SELECT
    rr.run_id,
    rs.project_name,
    rr.dataset_name,
    ds.source_connection,
    ds.target_connection,
    rr.rule_name,
    rr.rule_type,
    rr.status,
    rr.details,
    rr.start_time,
    rr.end_time
FROM dva.rule_results rr
JOIN dva.run_summary rs ON rr.run_id = rs.run_id
LEFT JOIN dva.dataset_summary ds
    ON rr.run_id = ds.run_id AND rr.dataset_name = ds.dataset_name
WHERE rr.status IN ('FAIL', 'ERROR')
ORDER BY rr.start_time DESC;

CREATE OR REPLACE VIEW dva.v_failed_datasets AS
SELECT
    ds.run_id,
    rs.project_name,
    ds.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    ds.source_count,
    ds.target_count,
    ds.missing_count,
    ds.extra_count,
    ds.mismatch_count
FROM dva.dataset_summary ds
JOIN dva.run_summary rs ON ds.run_id = rs.run_id
WHERE ds.status IN ('FAIL', 'ERROR')
ORDER BY rs.start_time DESC;

CREATE OR REPLACE VIEW dva.v_run_portfolio AS
SELECT
    project_name,
    COUNT(*) AS total_runs,
    SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passed_runs,
    SUM(CASE WHEN status = 'FAIL' THEN 1 ELSE 0 END) AS failed_runs,
    SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) AS error_runs,
    ROUND(
        100.0 * SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
        1
    ) AS pass_rate_pct
FROM dva.run_summary
GROUP BY project_name;

CREATE OR REPLACE VIEW dva.v_validation_coverage AS
SELECT
    rr.run_id,
    ds.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    rr.rule_type,
    COUNT(*) AS check_count,
    SUM(CASE WHEN rr.status = 'PASS' THEN 1 ELSE 0 END) AS passed,
    SUM(CASE WHEN rr.status = 'FAIL' THEN 1 ELSE 0 END) AS failed,
    SUM(CASE WHEN rr.status = 'ERROR' THEN 1 ELSE 0 END) AS errored
FROM dva.rule_results rr
LEFT JOIN dva.dataset_summary ds
    ON rr.run_id = ds.run_id AND rr.dataset_name = ds.dataset_name
GROUP BY
    rr.run_id,
    ds.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    rr.rule_type
ORDER BY rr.run_id DESC, ds.dataset_name, rr.rule_type;

CREATE OR REPLACE VIEW dva.v_execution_errors AS
SELECT
    el.run_id,
    rs.project_name,
    el.timestamp AS event_time,
    el.level AS severity,
    el.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    'execution'::TEXT AS issue_source,
    el.message AS issue_detail
FROM dva.execution_logs el
JOIN dva.run_summary rs ON el.run_id = rs.run_id
LEFT JOIN dva.dataset_summary ds
    ON el.run_id = ds.run_id AND el.dataset_name IS NOT DISTINCT FROM ds.dataset_name
WHERE el.level IN ('ERROR', 'WARN')

UNION ALL

SELECT
    rr.run_id,
    rs.project_name,
    rr.end_time AS event_time,
    rr.status AS severity,
    rr.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    rr.rule_type AS issue_source,
    CASE
        WHEN rr.details <> '' THEN rr.rule_name || ': ' || rr.details
        ELSE rr.rule_name
    END AS issue_detail
FROM dva.rule_results rr
JOIN dva.run_summary rs ON rr.run_id = rs.run_id
LEFT JOIN dva.dataset_summary ds
    ON rr.run_id = ds.run_id AND rr.dataset_name = ds.dataset_name
WHERE rr.status IN ('FAIL', 'ERROR')

ORDER BY event_time DESC;

CREATE OR REPLACE VIEW dva.v_issue_recurrence AS
SELECT
    vi.issue_fingerprint,
    vi.run_id,
    vi.dataset_name,
    ds.source_connection,
    ds.target_connection,
    vi.rule_name,
    vi.issue_type,
    vi.severity,
    vi.status,
    vi.recurrence_count,
    vi.first_seen_run_id,
    vi.last_seen_run_id,
    CASE WHEN vi.recurrence_count > 1 THEN 'Recurring' ELSE 'New' END AS recurrence_label
FROM dva.validation_issues vi
LEFT JOIN dva.dataset_summary ds
    ON vi.run_id = ds.run_id AND vi.dataset_name = ds.dataset_name
ORDER BY vi.recurrence_count DESC, vi.severity;

-- Enriched chart views: attach dataset filter dimensions to detail tables.

CREATE OR REPLACE VIEW dva.v_chart_rule_results AS
SELECT
    rr.run_id,
    rr.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    rr.rule_name,
    rr.rule_type,
    rr.status,
    rr.details,
    rr.start_time,
    rr.end_time
FROM dva.rule_results rr
LEFT JOIN dva.dataset_summary ds
    ON rr.run_id = ds.run_id AND rr.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_schema_results AS
SELECT
    sr.run_id,
    sr.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    sr.check_name,
    sr.status,
    sr.details
FROM dva.schema_results sr
LEFT JOIN dva.dataset_summary ds
    ON sr.run_id = ds.run_id AND sr.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_count_results AS
SELECT
    cr.run_id,
    cr.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    cr.source_count,
    cr.target_count,
    cr.difference,
    cr.pct_difference,
    cr.status
FROM dva.count_results cr
LEFT JOIN dva.dataset_summary ds
    ON cr.run_id = ds.run_id AND cr.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_hash_summary AS
SELECT
    hs.run_id,
    hs.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    hs.matched_count,
    hs.missing_count,
    hs.extra_count,
    hs.mismatch_count,
    hs.status
FROM dva.hash_summary hs
LEFT JOIN dva.dataset_summary ds
    ON hs.run_id = ds.run_id AND hs.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_aggregate_results AS
SELECT
    ar.run_id,
    ar.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    ar.group_key,
    ar.column_name,
    ar.metric,
    ar.source_value,
    ar.target_value,
    ar.pct_difference,
    ar.status
FROM dva.aggregate_results ar
LEFT JOIN dva.dataset_summary ds
    ON ar.run_id = ds.run_id AND ar.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_statistical_results AS
SELECT
    st.run_id,
    st.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    st.column_name,
    st.metric,
    st.source_value,
    st.target_value,
    st.pct_difference,
    st.status
FROM dva.statistical_results st
LEFT JOIN dva.dataset_summary ds
    ON st.run_id = ds.run_id AND st.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_dq_results AS
SELECT
    dq.run_id,
    dq.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    dq.rule_name,
    dq.side,
    dq.failed_count,
    dq.severity,
    dq.status
FROM dva.dq_results dq
LEFT JOIN dva.dataset_summary ds
    ON dq.run_id = ds.run_id AND dq.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_duplicate_keys AS
SELECT
    dk.run_id,
    dk.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    dk.side,
    dk.primary_key,
    dk.duplicate_count
FROM dva.duplicate_keys dk
LEFT JOIN dva.dataset_summary ds
    ON dk.run_id = ds.run_id AND dk.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_hash_mismatches AS
SELECT
    hm.run_id,
    hm.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    hm.primary_key,
    hm.source_hash,
    hm.target_hash,
    hm.source_record,
    hm.target_record
FROM dva.hash_mismatches hm
LEFT JOIN dva.dataset_summary ds
    ON hm.run_id = ds.run_id AND hm.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_missing_records AS
SELECT
    mr.run_id,
    mr.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    mr.primary_key,
    mr.record
FROM dva.missing_records mr
LEFT JOIN dva.dataset_summary ds
    ON mr.run_id = ds.run_id AND mr.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_extra_records AS
SELECT
    er.run_id,
    er.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    er.primary_key,
    er.record
FROM dva.extra_records er
LEFT JOIN dva.dataset_summary ds
    ON er.run_id = ds.run_id AND er.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_validation_issues AS
SELECT
    vi.run_id,
    vi.dataset_name,
    ds.source_connection,
    ds.target_connection,
    vi.status,
    vi.rule_name,
    vi.issue_type,
    vi.severity,
    vi.failed_count,
    vi.recurrence_count
FROM dva.validation_issues vi
LEFT JOIN dva.dataset_summary ds
    ON vi.run_id = ds.run_id AND vi.dataset_name = ds.dataset_name;

CREATE OR REPLACE VIEW dva.v_chart_execution_logs AS
SELECT
    el.run_id,
    el.timestamp,
    el.level,
    el.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    el.message
FROM dva.execution_logs el
LEFT JOIN dva.dataset_summary ds
    ON el.run_id = ds.run_id AND el.dataset_name = ds.dataset_name;

-- Distinct filter values across dataset summaries and row-level result tables.
CREATE OR REPLACE VIEW dva.v_dashboard_filters AS
SELECT DISTINCT
    run_id,
    dataset_name,
    source_connection,
    target_connection,
    status
FROM (
    SELECT run_id, dataset_name, source_connection, target_connection, status
    FROM dva.dataset_summary
    UNION ALL
    SELECT run_id, dataset_name, source_connection, target_connection, status
    FROM dva.v_chart_hash_mismatches
    UNION ALL
    SELECT run_id, dataset_name, source_connection, target_connection, status
    FROM dva.v_chart_missing_records
    UNION ALL
    SELECT run_id, dataset_name, source_connection, target_connection, status
    FROM dva.v_chart_extra_records
    UNION ALL
    SELECT run_id, dataset_name, source_connection, target_connection, status
    FROM dva.v_chart_validation_issues
    UNION ALL
    SELECT run_id, dataset_name, source_connection, target_connection, status
    FROM dva.v_chart_rule_results
    UNION ALL
    SELECT run_id, dataset_name, source_connection, target_connection, status
    FROM dva.v_execution_errors
) filter_values
WHERE dataset_name IS NOT NULL;

-- Chart-friendly aggregate views for KPI and graphical dashboards.

CREATE OR REPLACE VIEW dva.v_run_kpis AS
SELECT
    rs.run_id,
    rs.project_name,
    rs.status AS run_status,
    rs.start_time,
    COUNT(ds.dataset_name) AS total_datasets,
    SUM(CASE WHEN ds.status = 'PASS' THEN 1 ELSE 0 END) AS passed_datasets,
    SUM(CASE WHEN ds.status = 'FAIL' THEN 1 ELSE 0 END) AS failed_datasets,
    SUM(CASE WHEN ds.status = 'ERROR' THEN 1 ELSE 0 END) AS error_datasets,
    ROUND(
        100.0 * SUM(CASE WHEN ds.status = 'PASS' THEN 1 ELSE 0 END) / NULLIF(COUNT(ds.dataset_name), 0),
        1
    ) AS pass_rate_pct,
    COALESCE(SUM(ds.mismatch_count), 0) AS total_mismatches,
    COALESCE(SUM(ds.missing_count), 0) AS total_missing,
    COALESCE(SUM(ds.extra_count), 0) AS total_extra,
    (
        SELECT COUNT(*)
        FROM dva.rule_results rr
        WHERE rr.run_id = rs.run_id AND rr.status IN ('FAIL', 'ERROR')
    ) AS failed_rules,
    (
        SELECT COUNT(*)
        FROM dva.validation_issues vi
        WHERE vi.run_id = rs.run_id
    ) AS open_issues
FROM dva.run_summary rs
LEFT JOIN dva.dataset_summary ds ON rs.run_id = ds.run_id
GROUP BY rs.run_id, rs.project_name, rs.status, rs.start_time;

CREATE OR REPLACE VIEW dva.v_dataset_status_counts AS
SELECT
    ds.run_id,
    ds.status,
    COUNT(*) AS dataset_count
FROM dva.dataset_summary ds
GROUP BY ds.run_id, ds.status;

CREATE OR REPLACE VIEW dva.v_hash_breakdown AS
SELECT
    hs.run_id,
    hs.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    breakdown_type,
    breakdown_count
FROM dva.hash_summary hs
LEFT JOIN dva.dataset_summary ds
    ON hs.run_id = ds.run_id AND hs.dataset_name = ds.dataset_name
CROSS JOIN LATERAL (
    VALUES
        ('matched'::TEXT, hs.matched_count),
        ('missing'::TEXT, hs.missing_count),
        ('extra'::TEXT, hs.extra_count),
        ('mismatch'::TEXT, hs.mismatch_count)
) AS breakdown(breakdown_type, breakdown_count);

CREATE OR REPLACE VIEW dva.v_aggregate_drift_top AS
SELECT
    ar.run_id,
    ar.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    ar.group_key,
    ar.column_name,
    ar.metric,
    ar.source_value,
    ar.target_value,
    ar.pct_difference,
    ar.status,
    ABS(COALESCE(ar.pct_difference, 0)) AS abs_pct_difference
FROM dva.aggregate_results ar
LEFT JOIN dva.dataset_summary ds
    ON ar.run_id = ds.run_id AND ar.dataset_name = ds.dataset_name
WHERE ar.status IN ('FAIL', 'WARN');

CREATE OR REPLACE VIEW dva.v_statistical_drift_top AS
SELECT
    st.run_id,
    st.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    st.column_name,
    st.metric,
    st.source_value,
    st.target_value,
    st.pct_difference,
    st.status,
    ABS(COALESCE(st.pct_difference, 0)) AS abs_pct_difference
FROM dva.statistical_results st
LEFT JOIN dva.dataset_summary ds
    ON st.run_id = ds.run_id AND st.dataset_name = ds.dataset_name
WHERE st.status IN ('FAIL', 'WARN');

CREATE OR REPLACE VIEW dva.v_rule_outcome_counts AS
SELECT
    rr.run_id,
    rr.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status AS dataset_status,
    rr.rule_type,
    rr.status AS rule_status,
    COUNT(*) AS outcome_count
FROM dva.rule_results rr
LEFT JOIN dva.dataset_summary ds
    ON rr.run_id = ds.run_id AND rr.dataset_name = ds.dataset_name
GROUP BY
    rr.run_id,
    rr.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    rr.rule_type,
    rr.status;

CREATE OR REPLACE VIEW dva.v_validation_trends_chart AS
SELECT
    rs.run_id,
    rs.project_name,
    rs.start_time,
    ds.dataset_name,
    ds.source_connection,
    ds.target_connection,
    ds.status,
    ds.source_count,
    ds.target_count,
    ds.mismatch_count
FROM dva.dataset_summary ds
JOIN dva.run_summary rs ON ds.run_id = rs.run_id;
