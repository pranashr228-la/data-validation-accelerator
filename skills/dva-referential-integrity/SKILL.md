---
name: dva-referential-integrity
description: Use when implementing, extending, or debugging the referential_integrity validation type in the Data Validation Accelerator (DVA), including its YAML config model, SQL generation, Postgres persistence, CLI reporting, or Superset visibility.
---

# DVA Referential Integrity — Project Standards

---

## 1. Read before writing
Do not rely on any fixed list of file names — the codebase may change. Instead, discover what to
read by exploring the project structure itself, in this order:

1. Read the full feature specification referenced by the task (its FR/AC/NFR sections) before
   touching any code.
2. List the engine/orchestration package and read whatever module defines the validation
   execution order, the run-time dataset/connector context objects, and how connectors are opened
   and keyed — these determine whether cross-dataset lookups (see §2) are even possible today.
3. List the validations package and open the *simplest* existing single-dataset validation module
   you can find (smallest file, no grouping/aggregation logic) purely as a style reference for
   naming, structure, and shared helper usage — do not assume which one that is in advance; pick it
   by inspection.
4. List the config package and read whatever module holds the Pydantic model bundle for
   per-dataset validation settings, and whatever module performs semantic/cross-field validation
   beyond basic type checking.
5. List the reporting package and read whatever modules define result models, the in-memory
   result collector, and the database bulk-insert helper — every existing validation type follows
   one consistent pattern across these three; find and match it rather than inventing a new one.
6. List the SQL migration directory and read the existing files to learn the current table/view
   naming, indexing, and formatting conventions before adding a new migration.
7. Locate the project's real, currently-used validation configuration file (the one referenced by
   the project's own run instructions or README/AGENTS docs, not one you create) — this is the
   file relationships must be added to; see §6.
8. Locate and read the dashboard/reporting bootstrap script to learn how existing charts/datasets
   are registered idempotently, before adding a new one.

Confirm the feature does not already exist before writing any code.

---

## 2. Cross-dataset architecture — the core new capability

Every existing validation type (`count`, `row_hash`, `aggregate`, `statistical`, `data_quality`, `duplicate_keys`, `schema_contract`) operates on exactly one dataset's own source/target pair. `DatasetContext` only carries `source`/`target` connectors and SQL for the dataset currently being validated.

Referential integrity is different: it must reach a **second, different dataset** (the parent) while validating the current dataset (the child). To do this:

- `Orchestrator.run_validation()` already builds `connectors: dict[str, Connector]` keyed by connection name — this dict is available in scope. The parent dataset's connector is almost always already open (same named connections reused across datasets).
- You must be able to resolve `parent_dataset` (a dataset **name** from YAML) to that dataset's `DatasetConfig`, then build its target-side SQL using `build_base_sql(parent_dataset.target)` from `normalization/sql_builder.py` — the same builder every other validation already uses.
- Thread whatever you need (`RootConfig.datasets` list, `connectors` dict) through `RunContext`, or pass it explicitly into the new validation function — do not duplicate config-loading logic.
- Do not confuse this cross-dataset lookup with "automatic relationship discovery" at run time — the engine still requires relationships to be explicitly listed in YAML (NFR-02). Discovery only happens once, at config-authoring time, by a human or implementation agent editing YAML (see §6).

---

## 3. Config model conventions

Follow the exact Pydantic style already used for every other validation block in `config/models.py`:

```python
class RIRelationship(BaseModel):
    name: str
    child_column: str | None = None
    child_columns: list[str] | None = None
    parent_dataset: str
    parent_column: str | None = None
    parent_columns: list[str] | None = None
    child_side: Literal["target"] = "target"
    parent_side: Literal["target"] = "target"

class ReferentialIntegrityConfig(BaseModel):
    enabled: bool = False
    max_samples: int = 50
    null_handling: Literal["ignore", "fail"] = "ignore"
    relationships: list[RIRelationship] = Field(default_factory=list)
```

Add `referential_integrity: ReferentialIntegrityConfig = Field(default_factory=ReferentialIntegrityConfig)` to `ValidationsConfig`, matching every other block's pattern. `enabled` defaults to `False` (opt-in), matching `schema_contract` — not the six default-on types.

Reject a relationship that mixes single-column (`child_column`/`parent_column`) and composite-column (`child_columns`/`parent_columns`) syntax. Reject composite lists of mismatched length. Reject any `child_side`/`parent_side` value other than `target`. Reject a `parent_dataset` name that does not exist elsewhere in the same config. Do all of this in `config/validator.py`, matching how existing semantic checks are structured there — not inside the Pydantic model's own field validators, unless that is the existing project convention for a given check.

---

## 4. SQL generation conventions

- Reuse `dialect.quote_ident()` for every identifier — never string-format raw column names.
- Reuse `build_base_sql()` for both child and parent SQL — do not write ad-hoc SELECT logic.
- Prefer a portable `LEFT JOIN ... WHERE parent.key IS NULL` anti-join over dialect-specific `NOT EXISTS`/`EXCEPT` syntax, so the same code works across Postgres, Snowflake, DuckDB, and Databricks without dialect branching (per NFR-05).
- Never fetch full parent/child row sets into Python for comparison — compute `missing_key_count` and `affected_row_count` via SQL aggregation, and only fetch a bounded sample (`max_samples`) for `sample_missing_keys`. Fetching entire tables into Python violates NFR-04 and will not scale on real fact tables (60K+ rows in the AdventureWorks config).
- Write generated SQL files (child/parent/missing queries) using `ctx.run.write_generated_sql()` with the exact label format `<dataset>__referential_integrity_<relationship>_<child|parent|missing>.sql`, matching the naming convention every other validation type already uses.
- Apply the `null_handling` rule (`ignore` default, `fail` optional) consistently for both single-column and composite keys — a composite key with any null component follows the same rule as a single null value.

---

## 5. Persistence conventions

- New migration file only: `sql/postgres/003_referential_integrity.sql`. Never edit `001_schema.sql` or `002_views.sql`.
- Table name: `dva.referential_integrity_results`. Follow the exact column-naming style of sibling tables (`dva.hash_summary`, `dva.aggregate_results`) — snake_case, `run_id` first, indexed on `run_id`/`dataset_name`/`parent_dataset_name`/`status`.
- Add the new `ReferentialIntegrityResult` Pydantic model to `reporting/models.py`, add a `referential_integrity_results: list[...]` field to `ReportCollector` in `reporting/writer.py`, and add the corresponding `bulk_insert(conn, "dva.referential_integrity_results", ...)` call inside `write_all()` — mirror the exact pattern already used for every other result type; do not invent a new persistence path.
- Register the new migration file in `reporting/database.py`'s schema-file list and in the results-truncation helper, matching how `002_views.sql` is already registered.
- Create `dva.v_referential_integrity_failures` and `dva.v_chart_referential_integrity_results` views in the same or a follow-up migration, joining in dataset-level dimensions from `dva.dataset_summary` (source/target connection, dataset status) exactly like the existing `v_chart_*` views already do.

---

## 6. Real-config discipline — do not fabricate demo data

This is the single most common failure mode observed when implementing this feature. Follow strictly:

- Identify the project's real, currently-used validation configuration file by inspecting the
  project's own documentation and run instructions — do not assume a specific file name in
  advance. Add `referential_integrity` relationships **directly into that real file**. Never create
  a brand-new demo or example configuration file as a substitute for configuring the real one.
- Never create a synthetic or fabricated dataset solely to produce a passing/failing result for
  your own verification. If you need a quick sanity check while developing, delete every trace of
  it afterward — including any rows it wrote to the results table and any temporary YAML file —
  before reporting completion.
- Discover which datasets — fact-type **or dimension-type** — need `referential_integrity` blocks
  by **reading the real config file's own dataset list and each dataset's own
  `primary_key`/`compare_columns` values at implementation time** — a column on any dataset that
  matches another dataset's `primary_key` name is a candidate relationship. This includes
  fact-to-dimension relationships (e.g. a sales fact referencing a product dimension) and
  dimension-to-dimension relationships (e.g. a product dimension referencing a product-category
  dimension, or a customer dimension referencing a geography dimension) — do not assume only fact
  tables can be children. Do not hardcode a fixed list of dataset or column names anywhere in your
  implementation or in your own working notes; the discovery must happen by inspecting the actual
  file's contents each time, not by memorizing today's dataset names (per NFR-07).
- Cover **every** dataset — fact or dimension — with a discoverable relationship, not just one.
  Leaving several tables with obvious FK columns unconfigured while only wiring up one does not
  satisfy the spec (per FR-15/AC-18).
- Final reported runtime-verification results must come only from a real run against this real
  config — never from synthetic or demo data left in place (per FR-16/AC-19/NFR-08).

---

## 7. Environment self-resolution — do not hand steps back to the user

- If `uv sync`, the virtual environment, or the Python interpreter version needs fixing, resolve it yourself using the project's own documented commands (see `AGENTS.md` "Commands cheat sheet" and `.python-version`). Do not tell the user to manually run `uv sync`, activate a venv, or change their Python version as a substitute for you doing it (per FR-17/AC-20).
- Never edit unrelated files (e.g. `certs/system-ca-bundle.pem`) to work around a network/TLS/proxy issue (per FR-17/AC-20). If Snowflake or Postgres is genuinely unreachable after a real attempt, stop and report it precisely as `Not verified` with the exact blocker (e.g. "Snowflake unreachable: corporate proxy/Zscaler blocks the connection; requires network/firewall allowlisting, not a code change") — do not fabricate a workaround (per AC-20).
- Before concluding a service (Postgres/Superset) is "not running," detect which container tool is actually available (`docker` vs `podman`) and list running containers by name — do not assume `docker` is installed if only `podman` is present. A container already reported as running/healthy must be treated as available even if a separate health-endpoint check fails for an unrelated reason (e.g. wrong host/port/protocol used by the check itself, not the service).

---

## 8. Running — use the full real config, not a hand-picked subset

Using the project's own CLI invocation pattern (see the project's command reference for the exact
executable name and flags), validate and run the real config file identified in §1/§6 — the one
already used for actual validation runs, not a file you created:

```bash
<project-cli> validate-config --config <real-config-file-you-identified>
<project-cli> run --config <real-config-file-you-identified> --allow-validation-fail
```

**The `validate-config` command alone never satisfies runtime verification.** It only parses YAML
and checks structural validity — it opens no database connection and executes no SQL, so it cannot
produce a real referential-integrity `PASS`/`FAIL` result. You must also run the `run` command
above against the real, live Postgres/Snowflake connections before reporting completion.

Do not scope the runtime-verification run to a hand-picked subset of datasets unless a genuine
external blocker (for example, an unreachable target system) makes the full run impossible — and
if so, state exactly which datasets were excluded and why (per FR-18/AC-21).

---

## 9. Verification — logic, not just green tests

Automated tests passing is necessary but not sufficient. After implementation:

1. **Config validation** — `dva validate-config` against the real config must succeed with the new relationships present.
2. **Live run against real data** — run the full real config; confirm at least one relationship reports `PASS` and, if any real orphaned key exists in the actual warehouse data, confirm it reports `FAIL` with correct `missing_key_count`/`affected_row_count`.
3. **Postgres persistence check**:
   ```sql
   SELECT dataset_name, relationship_name, status, missing_key_count, affected_row_count
   FROM dva.referential_integrity_results
   WHERE run_id = '<latest_run_id>';
   ```
   Row count must equal the number of relationships configured across all datasets (fact and dimension alike) in the config — not just one dataset's relationships.
4. **CLI check** — `dva results --project <name> --summary` must show the `-- Referential integrity --` section with every configured relationship.
5. **Superset check** — after running the bootstrap script, the "Referential Integrity Failures" chart must appear on the Validation Deep Dive dashboard, and re-running the bootstrap a second time must not create duplicates.
6. **AC-by-AC sign-off** — for every AC in `docs/FEATURE_referential_integrity_validation.md`, state explicitly how it was verified (mocked test reference, or live command + result) and never present a mocked-only result as live proof (per AC-14/AC-19).

---

## 10. Key reference

| Item | Value / Location | Notes |
|---|---|---|
| Execution order slot | `src/dva/engine/execution_plan.py` | After `row_hash`, before `aggregate` |
| Config block | `validations.referential_integrity` | Opt-in, `enabled: false` default |
| CLI aliases | `ri`, `fk`, `foreign_keys` | Map to canonical `referential_integrity` in `run_scope.py` |
| New migration | `sql/postgres/003_referential_integrity.sql` | Never edit 001/002 |
| New table | `dva.referential_integrity_results` | Grain: one row per relationship per child dataset per run |
| Real config file | Identified by inspection at implementation time (§1/§6) — not a fixed name | Must be edited directly — no demo file |
| Default `null_handling` | `ignore` | Nullable FKs common in warehouses |
| Sample cap | `max_samples` (default 50) | Bounds `sample_missing_keys` |

---

## 11. Strict feature requirement compliance

Before writing any code, read `docs/FEATURE_referential_integrity_validation.md` in full. Map every FR (FR-01 through FR-18) and every AC (AC-01 through AC-21) to a specific line of code, config entry, test, or verification step. Do not consider the task complete until every FR and AC has been explicitly addressed and reported on — silence on an AC is not acceptable.

**Traceability rule:** If FR-15 says relationships must be discovered by inspecting the real config file, verify your implementation actually reads dataset names/primary keys programmatically during authoring — not a hardcoded list that happens to match today's config.

---

## 12. New feature checklist

- [ ] Every FR (01–18) in the spec has a corresponding implementation step
- [ ] Every AC (01–21) has been verified and explicitly reported on
- [ ] Config model added to `ValidationsConfig` following existing Pydantic style
- [ ] Config validator rejects unknown `parent_dataset`, mismatched composite columns, non-`target` sides
- [ ] SQL generation uses `build_base_sql()` + dialect-quoted anti-join, no dialect-specific branching
- [ ] No full-table fetch into Python; only bounded samples fetched
- [ ] New migration `003_referential_integrity.sql` created; 001/002 untouched
- [ ] `ReferentialIntegrityResult` model, `ReportCollector` field, `write_all()` call added
- [ ] Execution plan updated; CLI aliases (`ri`/`fk`/`foreign_keys`) added to `run_scope.py`
- [ ] CLI `_print_summary` extended with `-- Referential integrity --` section
- [ ] Superset bootstrap registers new view/chart on Validation Deep Dive; idempotent on re-run
- [ ] Relationships added to the REAL config file only — no demo config, no synthetic dataset
- [ ] Every dataset (fact or dimension) with a discoverable FK relationship is covered — not just one
- [ ] Any temporary test artifacts (data, config, DB rows) fully cleaned up before completion
- [ ] Environment issues (venv, Python version, deps) resolved autonomously, not handed to user
- [ ] No unrelated files (CA bundle, certs) modified as a workaround
- [ ] Full real config run executed (not `--datasets` subset) unless a real blocker is documented
- [ ] Postgres persistence verified live: row count matches total configured relationships
- [ ] CLI and Superset visibility verified live, not only via mocks
- [ ] Unit tests cover config parsing, null handling, composite keys, persistence, CLI output
- [ ] All pre-existing tests still pass unmodified
- [ ] Final report separates mocked-test results from live verification results per system

---

## ⚠️ AGENT CRITICAL REMINDER

Do not consider implementation complete until you have actually executed the real **run** command
(not only `validate-config`) against the real, already-configured Postgres/Snowflake connections
(§8) and verified all five items in §9 (config validation, live run, Postgres persistence, CLI
check, Superset check) with real command output — not by asking the user whether to proceed, and
not by stopping once the code compiles, unit tests pass, or config validation passes. Code
compilation, unit tests, and config validation are all prerequisites, not endpoints — none of them
opens a live connection or executes real SQL, so none of them can substitute for the live `run`.
