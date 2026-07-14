-- Dataset status over time, oldest first, for spotting regressions/trends.
SELECT
    ds.dataset_name,
    rs.start_time,
    ds.status,
    ds.source_count,
    ds.target_count,
    ds.mismatch_count
FROM read_parquet('validation_runs/*/run_id=*/dataset_summary.parquet') ds
JOIN read_parquet('validation_runs/*/run_id=*/run_summary.parquet') rs
    ON ds.run_id = rs.run_id
ORDER BY ds.dataset_name, rs.start_time;
