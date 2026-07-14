-- Row-level hash mismatches between source and target.
SELECT
    run_id,
    dataset_name,
    primary_key,
    source_hash,
    target_hash
FROM read_parquet('validation_runs/*/run_id=*/hash_mismatches.parquet')
ORDER BY run_id DESC;
