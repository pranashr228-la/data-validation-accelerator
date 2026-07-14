-- Datasets that failed or errored, most mismatches first.
SELECT
    run_id,
    dataset_name,
    status,
    source_count,
    target_count,
    missing_count,
    extra_count,
    mismatch_count
FROM read_parquet('validation_runs/*/run_id=*/dataset_summary.parquet')
WHERE status IN ('FAIL', 'ERROR')
ORDER BY mismatch_count DESC;
