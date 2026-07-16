# AGENTS.md — Data Validation Accelerator

Machine-readable reference for AI coding agents working in this repository.

## Project overview

- **Purpose:** Config-driven source vs target data validation for migration/ETL testing
- **Stack:** Python 3.14+, Typer CLI, Pydantic config, Postgres results store, Superset dashboards
- **Key dirs:** `src/dva/` (package), `configs/` (YAML projects), `sql/postgres/` (schema/views), `superset/` (dashboard bootstrap)

## Commands cheat sheet

```bash
uv sync --system-certs
docker compose up postgres -d
uv run dva init-db
uv run dva validate-config --config configs/examples/postgres_to_snowflake_table.yaml
uv run dva run --config configs/adventureworks_oltp_to_snowflake_dwh_validation_config_public.yml
uv run dva results --project adventureworks_internet_sales_validation --summary
uv run dva results --project adventureworks_internet_sales_validation --forensics --dataset fact_internet_sales_validation --max-rows 50
docker compose exec superset python /app/bootstrap/setup_dashboards.py
uv run pytest tests/unit -q
```

## CLI flags — complete list

### `dva run`

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--config` | string | required | YAML project path |
| `--output-path` | string | from config | Override output directory |
| `--datasets` | string | all | Comma-separated dataset names/globs |
| `--validations` | string | six core types | Only run listed validation types |
| `--skip-validations` | string | none | Exclude listed validation types |
| `--allow-validation-fail` | bool | false | Exit 0 on FAIL/ERROR |

### `dva results`

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--project` | string | required | Project name |
| `--database-url` | string | `DVA_DATABASE_URL` | Postgres URL |
| `--failed-only` | bool | false | Filter to FAIL/ERROR datasets |
| `--summary` | bool | false | Table-level drift only |
| `--forensics` | bool | false | Row-level samples only |
| `--detail` | bool | false | Summary + forensics |
| `--dataset` | string | all | Single dataset filter |
| `--max-rows` | int | 100 | Forensics row cap |

### `dva init-db`

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--database-url` | string | `DVA_DATABASE_URL` | Postgres URL |

### `dva validate-config`

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--config` | string | required | YAML path to validate |

## Validation aliases

| Alias | Canonical type |
|---|---|
| `hash` | `row_hash` |
| `stats`, `stat` | `statistical` |
| `agg` | `aggregate` |
| `dq` | `data_quality` |
| `duplicates`, `duplicate` | `duplicate_keys` |
| `schema` | `schema_contract` |

## Config schema

```yaml
project: { name, output_path, results_database_url?, environment? }
execution: { fail_fast?, write_generated_sql?, max_parallel_datasets? }
connections: { <name>: { type: postgres|snowflake|duckdb|parquet|databricks, ... } }
defaults:
  hash: { algorithm, null_token, delimiter, ... }
  validations: { count?, row_hash?, aggregate?, statistical?, data_quality?, ... }
datasets:
  - name: string
    mapping_mode: table_to_table | query_to_query
    source: { connection, object? | query?/sql? }
    target: { connection, object? | query?/sql? }
    primary_key: [string, ...]          # required
    compare_columns: [string, ...]    # for row_hash
    validations: { ... }                # optional; omit = all six defaults
```

### Auto-generation (when metrics/rules empty)

- **aggregate:** numeric cols → sum/avg/count; all cols → count_distinct/null_count
- **statistical:** numeric cols → mean/stddev/null_rate; text cols → distinct_count/null_rate
- **data_quality:** not_null on primary_key (CRITICAL) + *Key/*Id columns (HIGH)
- **row_hash:** disabled automatically when `compare_columns` is empty

## Validation engine reference

Execution order per dataset (`src/dva/engine/execution_plan.py`):

| Order | Type | Config gate | Postgres tables | Granularity |
|---|---|---|---|---|
| 1 | `schema_contract` | `enabled: true` + columns | `schema_results` | Table |
| 2 | `count` | `enabled: true` (default) | `count_results` | Table |
| 3 | `duplicate_keys` | `enabled: true` (default) | `duplicate_keys` | Row |
| 4 | `row_hash` | `enabled: true` + compare_columns | `hash_summary`, `hash_mismatches`, `missing_records`, `extra_records` | Table + row samples |
| 5 | `aggregate` | `enabled: true` + metrics | `aggregate_results` | Table/grouped |
| 6 | `statistical` | `enabled: true` + metrics | `statistical_results` | Table |
| 7 | `data_quality` | `enabled: true` + rules | `dq_results` | Table |

## Run scoping rules

- **No CLI flags:** all datasets, all six default validation types
- **`--datasets`:** filters `config.datasets` in orchestrator before loop
- **`--validations`:** replaces default set entirely (CLI takes precedence)
- **`--skip-validations`:** removes types from default six-type set
- Config `enabled: false` still respected unless type is in CLI `--validations` list

## Results investigation workflow

1. `dva results --project <name>` — dataset summary rollup
2. `dva results --project <name> --summary` — count, hash summary, aggregate, statistical
3. `dva results --project <name> --forensics --dataset <name> --max-rows 50` — row samples
4. Postgres: `SELECT * FROM dva.v_failed_rules`, `dva.aggregate_results`, `dva.statistical_results`
5. Superset: Validation Deep Dive dashboard (`dva-validation-deep-dive`)

## Dashboard navigation

| Level | Slug | Use for |
|---|---|---|
| 1 | `dva-executive-portfolio` | Portfolio KPIs, run timeline |
| 2 | `dva-run-command-center` | Per-run dataset/rule status |
| 3 | `dva-validation-deep-dive` | Table-level drift (start here for mismatches) |
| 4 | `dva-row-forensics` | Row-level proof (after table triage) |

- Filter panel: collapsed by default (`FILTERBAR_CLOSED_BY_DEFAULT = True`)
- Filters cascade: Run ID → Dataset Name
- Cross-dashboard links append `?expand_filters=0`
- Re-bootstrap: `docker compose exec superset python /app/bootstrap/setup_dashboards.py`

## Testing

```bash
docker compose up postgres -d
uv run pytest tests/unit -q
uv run pytest tests/integration -q   # requires Postgres + sample data
```

Key test files:
- `tests/unit/test_config_defaults.py` — defaults and auto-generation
- `tests/unit/test_cli_run_scope.py` — run scoping flags
- `tests/unit/test_cli_results.py` — results output
- `tests/integration/test_row_hash_validation.py` — full pipeline

## Common pitfalls

| Issue | Cause | Fix |
|---|---|---|
| No aggregate/statistical results | Metrics empty and auto-gen found no columns | Add `compare_columns` or explicit `metrics` |
| Row hash runs on empty compare | `compare_columns: []` | Add columns or disable `row_hash` |
| schema_contract fails validation | No column lists configured | Add `source_required_columns` or keep disabled |
| Dashboards empty | No `dva run` after Postgres up | Run validation, re-bootstrap dashboards |
| Too many row mismatches in CLI | Default `max_mismatch_samples: 10000` | Use `--summary` first; set `max_mismatch_samples: 100` in config |
| Filter panel always open | Old Superset config | Rebuild superset image; check `FILTERBAR_CLOSED_BY_DEFAULT` |

## Cross-references

- Human docs: [README.md](README.md)
- Dashboard guide: [docs/dashboards.md](docs/dashboards.md)
- Example config: [configs/examples/postgres_to_snowflake_table.yaml](configs/examples/postgres_to_snowflake_table.yaml)
- AdventureWorks config: [configs/adventureworks_oltp_to_snowflake_dwh_validation_config_public.yml](configs/adventureworks_oltp_to_snowflake_dwh_validation_config_public.yml)
