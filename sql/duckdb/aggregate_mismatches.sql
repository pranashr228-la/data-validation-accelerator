-- Aggregate metric comparisons that fell outside tolerance.
SELECT
    run_id,
    dataset_name,
    group_key,
    column,
    metric,
    source_value,
    target_value,
    difference,
    pct_difference,
    status
FROM read_parquet('validation_runs/*/run_id=*/aggregate_results.parquet')
WHERE status IN ('WARN', 'FAIL')
ORDER BY pct_difference DESC;
