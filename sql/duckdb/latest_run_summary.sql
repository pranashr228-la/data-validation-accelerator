-- Most recent run summary across all projects.
SELECT *
FROM read_parquet('validation_runs/*/run_id=*/run_summary.parquet')
ORDER BY start_time DESC
LIMIT 1;
