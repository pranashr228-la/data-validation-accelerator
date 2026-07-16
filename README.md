# Data Validation Accelerator

A Python, CLI-first, config-driven data validation accelerator for data migration
and ETL testing. Compares a source and target dataset using schema contract,
count, duplicate-key, row-hash, aggregate, statistical, and data-quality checks,
and writes validation results to Postgres for dashboards and CLI queries.

## Requirements

- Python 3.14+
- [`uv`](https://docs.astral.sh/uv/)

If your network requires the system certificate store (corporate proxy/MITM
TLS), pass `--system-certs` to `uv` commands, e.g. `uv sync --system-certs`.

## Setup

```bash
uv python pin 3.14
uv sync --system-certs
docker compose up postgres -d
uv run dva init-db
```

Set `DVA_DATABASE_URL` in `.env` (see `.env.example`; default:
`postgresql://dva:dva@localhost:5433/dva`).

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

   For table-level triage without row-level noise:

   ```bash
   uv run --system-certs dva results --project customer_migration --summary
   uv run --system-certs dva results --project customer_migration --forensics --dataset customer_table_validation --max-rows 50
   ```

   Or use `--detail` for the full breakdown (summary first, then forensics):

   ```bash
   uv run --system-certs dva results --project customer_migration --detail
   ```

5. Query results in Postgres (see `sql/postgres/*.sql` for views), e.g.:

   ```bash
   psql postgresql://dva:dva@localhost:5433/dva -c "SELECT * FROM dva.v_failed_rules"
   ```

6. Launch Superset dashboards (see [docs/dashboards.md](docs/dashboards.md)):

   ```bash
   docker compose build superset
   docker compose up superset
   ```

   Open http://localhost:8088 (admin / admin).

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
docker compose up postgres -d
docker compose run --rm dva run --config configs/examples/postgres_to_snowflake_table.yaml
docker compose up superset
```

See [docs/dashboards.md](docs/dashboards.md) for the full dashboard setup and demo walkthrough.

If the build fails on `pip install uv` with an SSL certificate error (common
behind a corporate TLS-inspecting proxy), the Dockerfile trusts
`certs/system-ca-bundle.pem` — see `certs/README.md` to (re)generate it from
the local macOS keychain.

## CLI reference

| Command | Purpose |
|---|---|
| `dva version` | Print version |
| `dva init-db` | Apply Postgres results schema |
| `dva validate-config --config <path>` | Validate YAML without running |
| `dva run --config <path>` | Run validation |
| `dva results --project <name>` | Show latest run dataset summary |

### `dva run` flags

| Flag | Default | Description |
|---|---|---|
| `--config` | required | Path to YAML project file |
| `--output-path` | from config | Override `project.output_path` |
| `--datasets` | all datasets | Comma-separated names or globs (e.g. `fact_*,dim_product_validation`) |
| `--validations` | all six core types | Comma-separated validation types (see aliases below) |
| `--skip-validations` | none | Skip specific validation types |
| `--allow-validation-fail` | false | Exit 0 even when status is FAIL/ERROR |

**Validation aliases:** `hash` → `row_hash`, `stats` → `statistical`, `agg` → `aggregate`, `dq` → `data_quality`, `duplicates` → `duplicate_keys`

```bash
# Full run — all datasets, all six validation types (default)
uv run dva run --config configs/adventureworks_oltp_to_snowflake_dwh_validation_config_public.yml

# Count + stats only on one dataset
uv run dva run --config ... --datasets fact_internet_sales_validation --validations count,stats

# Everything except expensive row hash
uv run dva run --config ... --skip-validations row_hash
```

### `dva results` flags

| Flag | Default | Description |
|---|---|---|
| `--project` | required | Project name from config |
| `--database-url` | `DVA_DATABASE_URL` | Postgres connection URL |
| `--failed-only` | false | Show only FAIL/ERROR datasets |
| `--summary` | false | Table-level detail: count, hash summary, aggregate, statistical |
| `--forensics` | false | Row-level samples: missing/extra/hash mismatches |
| `--detail` | false | Summary + forensics combined |
| `--dataset` | all | Limit output to one dataset |
| `--max-rows` | 100 | Cap rows per forensics table |

**Recommended triage order:** `dva results` → `--summary` → `--forensics --dataset <name> --max-rows 50`

## Validation types

Six validations run **by default** when a dataset omits a `validations:` block. `schema_contract` stays opt-in.

| Type | Default | Output level | Auto-config |
|---|---|---|---|
| `count` | enabled | Table (row counts) | none |
| `duplicate_keys` | enabled | Row (per duplicate PK) | uses `primary_key` |
| `row_hash` | enabled | Table summary + row samples | uses `compare_columns` |
| `aggregate` | enabled | Table or grouped | auto-metrics from columns |
| `statistical` | enabled | Table (column profiles) | auto-metrics from columns |
| `data_quality` | enabled | Table (failed counts) | auto `not_null` on PK/key columns |
| `schema_contract` | disabled | Table | requires explicit column lists |

Project-level defaults can be set under `defaults.validations` in YAML (e.g. `row_hash.max_mismatch_samples`).

## Config reference

```yaml
project:
  name: my_project
  output_path: ./validation_runs
  results_database_url: postgresql://...  # optional

defaults:
  validations:
    row_hash:
      max_mismatch_samples: 100
      write_full_mismatches: false

datasets:
  - name: my_dataset
    mapping_mode: query_to_query  # or table_to_table
    source: { connection: ..., query: | ... }
    target: { connection: ..., query: | ... }
    primary_key: [id]
    compare_columns: [col1, col2]
    validations:  # optional — omit to use all six defaults
      aggregate:
        group_by: [status]
        metrics:
          - column: amount
            checks: [sum, avg]
      statistical:
        metrics:
          - column: amount
            checks: [mean, stddev]
      data_quality:
        rules:
          - name: email_not_null
            type: not_null
            column: email
            severity: HIGH
```

See [AGENTS.md](AGENTS.md) for the full machine-readable reference used by AI agents.

## Dashboards

Four Superset dashboards are auto-created on boot. The filter panel is **collapsed by default** — click **Filters** (top-right) to scope by Run ID or Dataset.

| Dashboard | Slug | Purpose |
|---|---|---|
| Executive Portfolio | `dva-executive-portfolio` | KPIs, run timeline, portfolio overview |
| Run Command Center | `dva-run-command-center` | Dataset and rule breakdown per run |
| Validation Deep Dive | `dva-validation-deep-dive` | Count/hash/aggregate/statistical drift |
| Row-Level Forensics | `dva-row-forensics` | Hash mismatches, missing/extra records |

Drill path: Executive → Run Command Center → Validation Deep Dive → Row Forensics. See [docs/dashboards.md](docs/dashboards.md).

## Environment variables

| Variable | Purpose |
|---|---|
| `DVA_DATABASE_URL` | Postgres results database (default: `postgresql://dva:dva@localhost:5433/dva`) |
| Connection vars | See `.env.example` for Postgres/Snowflake credentials |

## Project layout

See `src/dva/` for the package: `config` (Pydantic models, YAML loading, env
substitution), `connectors` (Postgres/Snowflake/DuckDB/Parquet/Databricks),
`dialects` (per-engine SQL differences), `engine` (orchestrator, dataset
runner), `validations` (the seven validation engines), `normalization`
(row hashing), `reporting` (Postgres/manifest/JSONL writers), `issues`
(fingerprinted defect tracking).

## Tests

```bash
docker compose up postgres -d
uv run --system-certs pytest --cov=dva --cov-report=term-missing
```

Unit tests cover config loading, hash normalization, tolerance logic, issue
fingerprinting, schema contract checks, and Postgres reporting. Integration
tests require Postgres (`docker compose up postgres -d`) and run the full
orchestrator against the bundled example configs.

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
