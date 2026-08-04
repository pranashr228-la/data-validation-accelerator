# Feature: Referential Integrity Validation

## Status

| Field      | Value                                         |
| ---------- | ---------------------------------------------- |
| Priority   | High                                            |
| Status     | Approved — Ready for Implementation             |
| Complexity | Medium-Large                                    |
| Output     | New validation type: `referential_integrity`    |

---

## Problem

DVA validates source-vs-target for one dataset at a time (count, duplicate-key, row-hash, aggregate,
statistical, data-quality, schema-contract). None of these prove the target warehouse is internally
usable: if a fact table's key doesn't exist in its related dimension (or a dimension's key doesn't
exist in another dimension it depends on), business reports can silently lose or misclassify rows,
even when every existing check passes.

Add a validation that checks whether configured child keys in one dataset exist in configured
parent keys from another dataset already defined in the same config.

## Goal

* Check configured cross-dataset relationships (e.g. `fact_sales.ProductKey -> dim_product.ProductKey`).
* Run as part of the normal validation plan when enabled in YAML.
* Report missing parent keys and affected child-row counts; persist to Postgres; surface in CLI and Superset.
* Stay fully backward compatible and opt-in.

## In Scope

New `referential_integrity` validation type · YAML config model · validation engine · result model
+ Postgres persistence (new migration + views) · CLI reporting · Superset visibility · unit/integration
tests · docs update.

## Out of Scope

CSV export · automatic relationship discovery or FK inference from catalogs · enforcing physical DB
constraints · changing existing validation behavior/results · requiring every dataset to define
relationships · orchestrator/connector redesign · replacing schema-contract validation.

## Grain

One result row per configured relationship per child dataset per run, containing: run id, child
dataset, relationship name, child side/columns, parent dataset, parent side/columns, status,
missing-key count, affected-row count, sample missing keys, optional details/error.

---

## Functional Requirements

### FR-01: YAML Configuration

```yaml
validations:
  referential_integrity:
    enabled: true
    max_samples: 50
    null_handling: ignore
    relationships:
      - name: product_key_exists
        child_column: ProductKey        # or child_columns: [...] for composite
        parent_dataset: dim_product_validation
        parent_column: ProductKey       # or parent_columns: [...] for composite
```
Reject a relationship that mixes single-column and composite-column syntax.

### FR-02: Backward Compatibility
Configs without `referential_integrity` load and run unchanged. Disabled by default unless
explicitly enabled with at least one relationship. Existing CLI/tables/dashboards keep working.

### FR-03: Relationship Reference Validation
Reject: unknown `parent_dataset`, empty `name`, mixed single/composite syntax, mismatched composite
list lengths, and self-references (a dataset naming itself as its own parent — out of scope).
Column *existence* is checked at runtime via the existing schema-probe, not at parse time.

### FR-04: Child and Parent Sides
Default and only supported value for now: `target` vs `target` (both `child_side` and
`parent_side`). Any other value must be rejected with a clear error.

### FR-05: Validation Logic
Per relationship: build child/parent SQL from each dataset's target object/query → select distinct
keys on each side → find child keys missing from parent → count distinct missing keys and affected
child rows → sample up to `max_samples` → write one result row. `PASS` if none missing, `FAIL` if
any missing, `ERROR` on a SQL/connector failure (dataset status follows existing error rules).

### FR-06: Null Handling
`null_handling: ignore` (default) — null child keys don't fail. `fail` — nulls count as missing.
Applies the same way to composite keys with any null component.

### FR-07: SQL Generation
Use existing dialect quoting and `build_base_sql()`; prefer a portable `LEFT JOIN ... WHERE parent
IS NULL` anti-join over dialect-specific syntax. Write generated SQL (when
`execution.write_generated_sql` is true) as
`<dataset>__referential_integrity_<relationship>_<child|parent|missing>.sql`.

### FR-08: Result Persistence
New migration `sql/postgres/003_referential_integrity.sql` (never edit 001/002) creating
`dva.referential_integrity_results` with columns: `id, run_id, dataset_name, relationship_name,
child_side, child_columns, parent_dataset_name, parent_side, parent_columns, status,
missing_key_count, affected_row_count, sample_missing_keys, details`. Index `run_id`,
`dataset_name`, `parent_dataset_name`, `status`. Use text/JSON-text for column lists and samples.

### FR-09: Views
In the same or a follow-up migration: `dva.v_referential_integrity_failures` and
`dva.v_chart_referential_integrity_results` (the latter joined with `dva.dataset_summary` for
source/target connection and dataset status), matching the existing `v_chart_*` pattern.

### FR-10: CLI Reporting
Extend `dva results --summary`/detail output with a `-- Referential integrity --` section showing
dataset, relationship, child/parent columns, missing-key count, affected-row count, status — visible
without needing Superset.

### FR-11: Superset Reporting
Register `v_chart_referential_integrity_results` as a dataset; add a `Referential Integrity
Failures` chart. Add it to whichever existing dashboard already presents table-level validation
drift detail — identify that dashboard by inspecting the bootstrap script's existing dashboard
definitions, not by assuming a fixed name. Don't touch unrelated charts. No CSV output.

### FR-12: Validation Issues
On failure, record an issue via the existing mechanism: `rule_type=referential_integrity`,
`issue_type=missing_parent_keys`, `severity=HIGH` default, sample values = sampled missing keys.

### FR-13: Execution Order & Scoping
Insert after `row_hash`, before `aggregate`:
`schema_contract → count → duplicate_keys → row_hash → referential_integrity → aggregate → statistical → data_quality`.
Respect `--validations`/`--skip-validations`. Aliases: `ri`, `fk`, `foreign_keys`.

### FR-14: Mandatory Runtime Verification
Passing `dva validate-config` (or the project's equivalent structural/parse-only check) never
satisfies this requirement by itself — that command only confirms the YAML parses; it opens no
database connection and executes no SQL. Runtime verification requires actually executing the
project's real run command (e.g. `dva run --config <real-config>`) against the real, live
Postgres/Snowflake connections, so that at least one relationship reports `PASS` and at least one
reports `FAIL` from real query results — covering every relationship added under FR-15, not just
one dataset.

If you have only run config validation and have not yet executed the real run command against live
connections, you have not completed this requirement — do so next, in this same session.

Before concluding any prerequisite (service, credential, tool) is unavailable: detect which
container tool is actually installed (don't assume `docker` over `podman` or vice versa) and match
against the service names the project's own orchestration file defines; retry with the other tool
if one fails. A container already reported running/healthy counts as available even if a separate
health check fails for an unrelated reason (wrong host/port/protocol in the check itself).

Only report an item `Not verified` after genuinely attempting the above, stating exactly what's
missing and what was tried. Report each runtime item (Postgres persistence, CLI, Superset) as
`✅ Verified / ❌ Failed / ⚠️ Not verified / ⏭️ Skipped`, plus: config and command used, run id,
relationships checked/passed/failed, a sample failure if present. Never present mocked-test success
as live proof.

### FR-15: Mandatory Full-Warehouse Coverage in the Real Configuration
Configure this feature directly in the project's real, already-used config file — never a new
demo/example file. Inspect **every** dataset in that file, fact-type and dimension-type alike, and
identify columns that match another dataset's primary key by name — this covers both
fact-to-dimension relationships and dimension-to-dimension relationships (e.g. a product dimension
referencing a product-category dimension, or a customer dimension referencing a geography
dimension). Add a `referential_integrity` relationship for every such discovered pair, except
self-references (FR-03).

Coverage must come from inspecting the actual file's datasets/primary keys/columns at
implementation time — never from a fixed, pre-named list. Wiring up only one dataset while others
have discoverable relationships does not satisfy this requirement. This discovery is a one-time
config-authoring step, not the "automatic relationship discovery" that stays out of scope for the
engine itself (NFR-02) — the engine still requires relationships explicitly listed in YAML.

### FR-16: No Synthetic or Demo Verification Data
Runtime verification uses only the real config and real connections from FR-15 — never a fabricated
dataset or demo config created just to force a pass/fail. Any temporary data/config created during
development (including rows in `dva.referential_integrity_results`) must be fully removed before
completion is reported. Reported results must come only from a real run against the real config.

### FR-17: Autonomous Environment Resolution
Resolve environment issues (interpreter, venv, dependencies) yourself using whatever setup commands
and interpreter/version files the project's own docs/packaging already define — never hand the user
manual steps ("run this," "activate that," "change your Python version") as a substitute for doing
it yourself. Never edit unrelated files (e.g. an existing CA bundle) to work around a
network/TLS/proxy issue. If a genuine external blocker remains after a real attempt (network,
firewall, missing credentials), stop and report it precisely as `Not verified` with the exact
blocker and the exact external action needed — never work around it by hardcoding, patching
unrelated files, or fabricating a result.

### FR-18: Full-Configuration Runtime Execution
Run the complete real config with the project's standard invocation — don't scope to a hand-picked
dataset subset unless a real external blocker (FR-17) makes the full run impossible, in which case
report exactly which datasets were excluded and why.

---

## Acceptance Criteria

| ID | Acceptance Criterion |
|---|---|
| AC-01 | Configs without `referential_integrity` load/run unchanged. |
| AC-02 | Unknown `parent_dataset` is rejected at config validation. |
| AC-03 | Mismatched composite child/parent column counts are rejected. |
| AC-04 | All child keys present in parent → `PASS`. |
| AC-05 | Any missing child key → `FAIL`, with missing-key count, affected-row count, samples. |
| AC-06 | Null child keys ignored by default; `null_handling: fail` counts them as missing. |
| AC-07 | Composite-key relationships work and are tested. |
| AC-08 | Generated SQL is written when `execution.write_generated_sql` is true. |
| AC-09 | Results persist in `dva.referential_integrity_results`; failures create `rule_type=referential_integrity` issues. |
| AC-10 | Failures are visible in CLI summary/detail; Superset bootstrap registers the new dataset/chart idempotently. |
| AC-11 | `--validations`/`--skip-validations`/aliases (`ri`/`fk`/`foreign_keys`) work as expected. |
| AC-12 | No existing validation type's behavior changes; all pre-existing tests pass unmodified. |
| AC-13 | Unit tests cover config parsing, null handling, composite keys, persistence, CLI output. |
| AC-14 | Runtime verification separates automated-test results from live results; a mocked-only check reports `Not verified`, never `Verified`. |
| AC-15 | Runtime verification includes a per-item table (`Verified/Failed/Skipped/Not verified`) for Postgres persistence, CLI reporting, and Superset visibility, each with an actionable error if failed. |
| AC-16 | Before any item is marked `Not verified`, the container tool actually available is detected and matched against the project's real service names — a running/healthy container is never marked unavailable just because the wrong tool/name was tried. |
| AC-17 | `referential_integrity` relationships are added to the real, existing project config file only — never a new demo/example file. |
| AC-18 | Every dataset (fact or dimension) with a discoverable FK relationship to another dataset already in the config is covered, found by inspecting the file's own datasets/keys — not a hardcoded list — and runtime verification reports per-dataset relationship counts so coverage is visible. |
| AC-19 | Reported runtime results come only from a real run against the real config — no synthetic dataset/demo config is used, and any temporary test artifacts (data, config, DB rows) are fully cleaned up before completion. |
| AC-20 | Environment setup (interpreter, venv, deps) is resolved autonomously, without manual steps handed to the user, and no unrelated files (e.g. CA bundle) are modified as a workaround; a genuine external blocker is reported precisely as `Not verified` with the exact blocker and required external action. |
| AC-21 | The full real config is run (not a hand-picked `--datasets` subset) unless a real external blocker makes that impossible, in which case the reduced scope and reason are explicitly reported. |

---

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Backward compatible; no automatic relationship discovery or FK inference; no new third-party dependencies. |
| NFR-02 | Avoid fetching full parent/child datasets into Python — compute counts via SQL aggregation, sample only up to `max_samples`. |
| NFR-03 | Query generation stays dialect-aware through existing dialect abstractions; error messages identify the relationship and dataset that failed. |
| NFR-04 | No credentials, connection strings, or secrets in persisted details or CLI output. |
| NFR-05 | Superset changes are idempotent under repeated bootstrap runs; result persistence is additive, non-destructive. |
| NFR-06 | Runtime verification must not assume a specific container tool is installed — detect and use whichever is actually present. |
| NFR-07 | Coverage decisions come from inspecting the real config file's datasets/keys/columns at implementation time — never a hardcoded list of names in the spec or the implementation. |
| NFR-08 | Runtime verification must not depend on synthetic/demo/fabricated data left behind — clean up any temporary artifacts so persisted results reflect only real runs. |

---

## ⚠️ MANDATORY: This feature is not complete until live verification has run

Writing code, passing unit tests, and confirming things compile are **not** completion. Running
only `dva validate-config` (or an equivalent structural/parse-only check) is **not** completion
either — that command never opens a live database connection or executes SQL, so it cannot produce
a real `PASS`/`FAIL` referential-integrity result. Per FR-14 through FR-18 and AC-14 through AC-21,
you must actually execute the project's real run command (e.g. `dva run --config <real-config>`)
against the real, already-configured Postgres/Snowflake connections, and report the live
`PASS`/`FAIL` results it produces — not ask the user whether you should, and not stop after
implementation or after config validation alone. If you have finished writing code, or only run
config validation, and have not yet executed the real run command against live connections, you
are not done — proceed to do so now, in this same session, before reporting completion.
