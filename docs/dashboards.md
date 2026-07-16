# Superset Dashboards

Enterprise dashboards for the Data Validation Accelerator, powered by Apache
Superset and Postgres-primary result storage.

See also: [README.md](../README.md) (human reference) and [AGENTS.md](../AGENTS.md) (AI agent reference).

## Prerequisites

- Docker Desktop or Colima
- Python environment with `uv sync` completed

## Quick start

1. Start Postgres (and optionally Superset):

   ```bash
   docker compose up postgres -d
   ```

2. Initialize the results schema (first time only — also auto-applied on `dva run`):

   ```bash
   uv run dva init-db
   ```

3. Build sample data and run validations:

   ```bash
   uv run python sample_data/build_sample_data.py
   uv run dva run --config configs/examples/postgres_to_snowflake_table.yaml
   uv run dva run --config configs/examples/query_to_query_fact_order.yaml
   ```

4. Seed multiple runs for trend charts (optional):

   ```bash
   uv run python scripts/demo_seed.py 2
   ```

5. Build and start Superset (first time only needs `build`):

   ```bash
   docker compose build superset
   docker compose up superset
   ```

6. Open **http://localhost:8088** and log in:

   - Username: `admin`
   - Password: `admin`

## Dashboard suite

Four linked dashboards are created automatically on first Superset boot:

| Dashboard | Slug | Purpose |
|---|---|---|
| Executive Portfolio | `dva-executive-portfolio` | KPI callouts, run timeline, portfolio overview |
| Run Command Center | `dva-run-command-center` | Per-run dataset and rule breakdown |
| Validation Deep Dive | `dva-validation-deep-dive` | Count/hash/aggregate/statistical drift charts |
| Row-Level Forensics | `dva-row-forensics` | Hash mismatches, missing/extra records |

### Filter panel (collapsed by default)

The filter bar is **hidden on load**. Click the **Filters** button (top-right) to expand it when you need to scope by Run ID or Dataset. This is configured via `FILTERBAR_CLOSED_BY_DEFAULT = True` in `superset/superset_config.py`. Cross-dashboard drill links keep filters collapsed (`?expand_filters=0`).

### Drill-down hierarchy

```
Executive Portfolio  →  Run Command Center  →  Validation Deep Dive  →  Row Forensics
     (portfolio)            (per run)           (table-level drift)      (row samples)
```

Use markdown navigation links at the top of each dashboard to drill up/down. Within a dashboard, click chart bars to cross-filter sibling charts.

### Drill-down filters

Each dashboard includes native filters (expand via Filters button):

| Filter | Applies to | Cascade |
|---|---|---|
| **Run ID** | All charts with a `run_id` column | Parent filter (defaults to latest run) |
| **Dataset Name** | Dataset-level charts | Cascades from Run ID |
| **Source** | Connection name from config | Cascades from Run ID |
| **Target** | Connection name from config | Cascades from Run ID |
| **Status** | Dataset status | Cascades from Run ID |

Filters are backed by `dva.v_dashboard_filters`, which unions distinct values from
dataset summaries and row-level result tables.

**Note:** Source and target connection names are stored on new validation runs. Re-run
`dva run` after upgrading to populate them on existing projects.

The **Execution Errors** panel lists runtime log errors (ERROR/WARN) and failed
validation rules (FAIL), with rule name and details in the `issue_detail` column.

## Architecture

```
dva run  →  INSERT into Postgres (dva schema)  →  Superset charts
                ↑
         docker compose postgres
```

- **Results DB:** `postgresql://dva:dva@localhost:5433/dva` (schema `dva`)
- **Superset metadata DB:** `postgresql://dva:dva@localhost:5432/superset`

## Investigation workflow

When count/hash mismatches occur:

1. Start on **Validation Deep Dive** — hash breakdown bar, aggregate/statistical drift charts
2. Use CLI: `dva results --project <name> --summary`
3. Only then open **Row-Level Forensics** or `dva results --forensics --dataset <name> --max-rows 50`

## 5-minute demo script

1. **Executive Portfolio** — show KPI callouts (pass rate, failed runs), run timeline bar
2. Filter to a **failed run** — open **Run Command Center** for dataset status pie chart
3. **Validation Deep Dive** — walk hash breakdown, aggregate drift, statistical drift bars
4. **Row-Level Forensics** — show hash mismatch samples only after table-level triage
5. Mention CLI: `uv run dva results --project customer_migration --summary`

## SQL views

Pre-built views in `sql/postgres/002_views.sql`:

- `dva.v_run_kpis` — per-run KPI rollups for big-number charts
- `dva.v_hash_breakdown` — matched/missing/extra/mismatch counts
- `dva.v_aggregate_drift_top` / `dva.v_statistical_drift_top` — top drift failures
- `dva.v_dataset_status_counts` — status breakdown per run
- `dva.v_rule_outcome_counts` — rule outcomes by type
- `dva.v_run_portfolio` — project pass rates
- `dva.v_validation_trends` — dataset status over time
- `dva.v_failed_rules` / `dva.v_failed_datasets`

## Troubleshooting

| Issue | Fix |
|---|---|
| `dva run` fails connecting to Postgres | `docker compose up postgres -d` and verify `DVA_DATABASE_URL` |
| Superset shows empty charts | Run at least one `dva run` after Postgres is up |
| Dashboards not created | Check `docker compose logs superset` for bootstrap errors |
| Charts show column/metric errors | Re-run bootstrap: `docker compose exec superset python /app/bootstrap/setup_dashboards.py` |
| Only seeing row-level mismatches | Enable aggregate/statistical (now default); use Validation Deep Dive, not Row Forensics first |
| Filter panel always visible | Rebuild superset; verify `FILTERBAR_CLOSED_BY_DEFAULT = True` |
| Clear All still shows filtered data | Click **Apply Filters** after Clear All (Superset 4.1.x requires this). Then hard-refresh if needed. Empty filters are configured to show all rows |
| Reset all results | `TRUNCATE dva.run_summary CASCADE` or recreate Postgres volume |

## Files

| Path | Purpose |
|---|---|
| `sql/postgres/001_schema.sql` | Results table definitions |
| `sql/postgres/002_views.sql` | Dashboard-friendly views |
| `superset/superset_config.py` | Branding, feature flags, filter bar default |
| `superset/bootstrap/setup_dashboards.py` | Auto-create datasets and dashboards |
| `scripts/demo_seed.py` | Populate trend data |
