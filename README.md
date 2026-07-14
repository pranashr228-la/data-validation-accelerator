# Data Validation Accelerator

A Python, CLI-first, config-driven data validation accelerator for data migration
and ETL testing. Compares a source and target dataset using schema contract,
count, duplicate-key, row-hash, aggregate, statistical, and data-quality checks,
and writes Parquet reports that can be queried with DuckDB.

## Requirements

- Python 3.14+
- [`uv`](https://docs.astral.sh/uv/)

If your network requires the system certificate store (corporate proxy/MITM
TLS), pass `--system-certs` to `uv` commands, e.g. `uv sync --system-certs`.

## Setup

```bash
uv python pin 3.14
uv sync --system-certs
```

## Demo: AdventureWorks OLTP (Postgres) -> AdventureWorks DWH (Snowflake)

No live Postgres/Snowflake instances were available while building this MVP,
so the bundled example configs point at two local DuckDB files that stand in
for a Postgres source and a Snowflake target. The generated SQL, connectors,
and dialects are otherwise identical to what a real `type: postgres` /
`type: snowflake` connection would use — swapping in real credentials is a
config change, not a code change (see the commented-out blocks in
`configs/examples/postgres_to_snowflake_table.yaml`).

1. Build the sample AdventureWorks-shaped data (small, intentionally
   imperfect: missing rows, an extra row, a duplicate key, a drifted
   balance, and a couple of data-quality violations are seeded on purpose so
   the demo run actually finds something):

   ```bash
   uv run --system-certs python sample_data/build_sample_data.py
   ```

2. Validate a config without running it:

   ```bash
   uv run --system-certs dva validate-config --config configs/examples/postgres_to_snowflake_table.yaml
   ```

3. Run the compare:

   ```bash
   uv run --system-certs dva run --config configs/examples/postgres_to_snowflake_table.yaml
   ```

4. Show the latest results:

   ```bash
   uv run --system-certs dva results --project customer_migration
   ```

   Add `--detail` for a full row/column-level breakdown — schema contract
   check failures, count diff, duplicate keys, missing/extra records, row
   hash mismatches (with full source/target values when
   `write_full_mismatches: true`), aggregate/statistical drift per column,
   data quality rule failures, and the rolled-up validation issues:

   ```bash
   uv run --system-certs dva results --project customer_migration --detail
   uv run --system-certs dva results --project customer_migration --detail --dataset customer_table_validation
   ```

5. Query the Parquet reports directly with DuckDB (see `sql/duckdb/*.sql` for
   more), e.g.:

   ```bash
   duckdb -c "SELECT * FROM read_parquet('validation_runs/*/run_id=*/rule_results.parquet')"
   ```

### Other bundled examples

- `configs/examples/query_to_query_fact_order.yaml` — query-to-query mapping
  joining order -> customer -> person (source) against a curated fact table
  (target), demonstrating SQL-defined mappings for cases where source and
  target schemas differ.
- `configs/examples/parquet_to_parquet.yaml` — validates two local Parquet
  extracts directly, no database involved.
- `configs/examples/schema_contract_customer.yaml` — schema-contract-only
  check using `mapping_based` mode with unmapped target columns.

## Connecting to real Postgres / Snowflake

Copy `.env.example` to `.env` and fill in real credentials, then change a
dataset's connection block from `type: duckdb` to `type: postgres` /
`type: snowflake` (see the commented examples in the YAML files). The
validation engines, SQL generation, and reports are unchanged either way.

## Running with Docker

Works with Docker Desktop or [Colima](https://github.com/abiquo/colima)
(`colima start` first if using Colima).

```bash
docker build -t data-validation-accelerator .
docker run --rm data-validation-accelerator --help
docker run --rm -v "$(pwd)/validation_runs:/app/validation_runs" \
  data-validation-accelerator run --config configs/examples/postgres_to_snowflake_table.yaml
docker compose up
```

If the build fails on `pip install uv` with an SSL certificate error (common
behind a corporate TLS-inspecting proxy), the Dockerfile trusts
`certs/system-ca-bundle.pem` — see `certs/README.md` to (re)generate it from
the local macOS keychain.

## Project layout

See `src/dva/` for the package: `config` (Pydantic models, YAML loading, env
substitution), `connectors` (Postgres/Snowflake/DuckDB/Parquet/Databricks),
`dialects` (per-engine SQL differences), `engine` (orchestrator, dataset
runner), `validations` (the seven validation engines), `normalization`
(row hashing), `reporting` (Parquet/manifest/JSONL writers), `issues`
(fingerprinted defect tracking).

## Tests

```bash
uv run --system-certs pytest --cov=dva --cov-report=term-missing
```

Unit tests cover config loading, hash normalization, tolerance logic, issue
fingerprinting, schema contract checks, and DuckDB reporting. Integration
tests run the full orchestrator against the bundled example configs and
assert that the seeded discrepancies are detected.

## Known limitations (MVP scope)

- Row-hash normalization/hashing happens in Python after fetching column
  values (not pushed down as SQL in each source engine), so results don't
  depend on vendor extensions like Postgres' `pgcrypto`. `dva.dialects`
  still implements native hash functions for reference/future use.
- Schema contract and row/column matching between source and target is
  case-insensitive on column names (Postgres commonly folds to lowercase,
  Snowflake to uppercase); this is intentional, not a bug.
- `databricks-sql-connector` is not a hard dependency; installing it is only
  required if a dataset actually targets Databricks.
- `mapping_config` (arbitrary column-to-column mapping) is out of scope for
  the MVP per the build plan; use `query_to_query` with explicit column
  aliases for cases where source and target schemas differ.
