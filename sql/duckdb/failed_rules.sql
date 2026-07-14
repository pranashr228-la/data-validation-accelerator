-- Individual rule failures across all runs.
SELECT
    run_id,
    dataset_name,
    rule_name,
    rule_type,
    status,
    details,
    start_time,
    end_time
FROM read_parquet('validation_runs/*/run_id=*/rule_results.parquet')
WHERE status IN ('FAIL', 'ERROR')
ORDER BY start_time DESC;
