# Feature: Validation Assurance & Coverage Dashboard

## Status

| Field      | Value                                                              |
| ---------- | -------------------------------------------------------------------|
| Priority   | High                                                                |
| Status     | Approved — Ready for Implementation                                |
| Complexity | Medium–Large                                                        |
| Output     | New per-run coverage metrics plus a new fifth Superset dashboard    |

---

## Problem

DVA currently ships four dashboards focused on validation outcomes such as passed, failed, and mismatched results for source-versus-target comparisons.

Those dashboards do not answer a different governance question: how much of the warehouse is protected by automated validation, and how complete that protection is.

A data governance lead or executive cannot currently determine what percentage of warehouse columns are covered by configured checks, how many validation control types are enabled, how many individual automated checks are executed, which business areas have strong or weak coverage, or which datasets have complete validation coverage.

Add a new coverage-computation layer and a separate dashboard that reports the scale, completeness, and breadth of the validation framework without showing failure or mismatch detail.

---

## Goal

For every dataset validated in a run:

* Calculate column coverage.
* Calculate enabled-control coverage.
* Calculate the number of individual configured checks.
* Capture the number of records verified using existing run results.
* Associate the dataset with an optional business area.
* Classify fully assured datasets.
* Persist the measurements per run and dataset.
* Present warehouse-level, business-area-level, and dataset-level coverage through a new Superset dashboard.

---

## In Scope

* Optional, backward-compatible business-area tag for datasets.
* Column-coverage calculation.
* Enabled-control count.
* Individual-check count.
* Records-verified metric based on existing count-comparison results.
* Per-run, per-dataset persistence.
* Warehouse and business-area rollups.
* Fully-assured classification.
* A new, separate fifth Superset dashboard.
* Unit tests for all new calculation and persistence behavior.
* Runtime verification using available project configuration and Superset services.

## Out of Scope

* Changes to pass/fail logic in existing validation engines.
* Changes to the first four dashboards.
* Editing existing results-table or view definitions.
* Automatically inferring a dataset's business area.
* Automatically inferring foreign-key relationships.
* Backfilling coverage for runs completed before this feature exists.
* Additional full-table reads solely for coverage calculation.
* Replacing existing dashboard-building conventions or tooling.

## Grain

One coverage record per attempted dataset per run.

Each dataset actually processed in a run must produce exactly one coverage record, including datasets whose coverage calculation finishes with a warning.

Each coverage record must contain enough information to report:

* Run identifier.
* Dataset identifier and display name.
* Business area.
* Total available columns.
* Covered columns.
* Column-coverage percentage.
* Enabled-control count.
* Total supported control-type count.
* Individual-check count.
* Records verified.
* Fully-assured status.
* Coverage status such as `complete` or `warning`.
* Warning reason when calculation is incomplete.

---

## Functional Requirements

### FR-01: Business Area Tag

A dataset may optionally define a business-area value such as `Sales`, `Customer`, or `Finance`.

The field must be optional. Existing configuration files without the field must continue to load and run unchanged. Missing, blank, or whitespace-only values must be stored and reported as `Unclassified`, and `Unclassified` must participate in all warehouse and business-area rollups like any other business area.

### FR-02: Total Available Columns

For every validated dataset, determine the total available column set using the case-insensitive union of source and target schema columns.

Normalize column names case-insensitively for comparison and count each logical column once. A column present on only one side must still be included in the total available-column set. Preserve a readable column name for reporting if names differ only by case.

### FR-03: Covered Columns

Covered columns are the case-insensitive union of configured primary-key columns and resolved compare columns used by the dataset.

Remove duplicates case-insensitively and count only columns present in the total available-column set. If compare columns are derived by existing defaults, use the fully resolved compare-column list rather than only explicitly written YAML values. Do not count a column more than once because it participates in multiple validations.

### FR-04: Column Coverage

Calculate:

```text
column_coverage_pct = covered_column_count / total_available_column_count * 100
```

Store the percentage using a consistent numeric precision. A fully covered dataset must report exactly `100%` after applying the project's normal numeric handling. If total available columns is zero or unavailable, do not fabricate `0%` or `100%` — record the coverage status as `warning`, leave the percentage unavailable, and record a sanitized warning reason. Datasets with unavailable coverage percentages must be excluded from percentage denominators in aggregate rollups and counted separately as warning records.

### FR-05: Enabled-Control Coverage

For every dataset, calculate `enabled_control_count` (the number of distinct supported dataset-level validation control types enabled after defaults are resolved) and `total_supported_control_count` (the number of supported dataset-level validation control types in the current resolved configuration model).

Internal, deprecated, operational, or non-dataset controls must not be counted. A control type is counted once regardless of how many checks exist inside it. The implementation must enumerate the supported control types explicitly based on the current project model, and no supported control type may be silently ignored.

### FR-06: Individual-Check Count

For every enabled control type, count the actual configured checks it represents rather than counting only the control type itself.

The implementation must define a deterministic counting rule for every supported validation control type found in the current project. Controls configured over multiple columns, metrics, expressions, rules, or key groups must contribute the real number of configured checks. A control that represents one dataset-level comparison contributes one check unless the existing configuration model defines multiple distinct checks within it. The mapping between control type and counting rule must be covered by unit tests. Unsupported or unknown control types must produce a warning and must not be silently counted as zero.

### FR-07: Records Verified

Use the source-side row count already produced by the existing count comparison for the same dataset and run as `records_verified`.

Do not execute an additional full-table count solely for this feature. If the existing count result is unavailable, store the metric as unavailable and record a warning. A missing records-verified value must not fail the validation run.

### FR-08: Fully Assured Classification

A dataset is `Fully Assured` only when column coverage is exactly `100%`, `enabled_control_count` equals `total_supported_control_count`, and coverage status is not `warning`.

A dataset with unavailable metrics, partial column coverage, or any disabled supported control type must not be classified as fully assured.

### FR-09: Persistence

Persist coverage measurements in new additive storage without modifying existing table or view definitions.

Create new sequential database migration files when new database objects are required. Do not edit existing numbered migrations. Enforce one logical coverage record per run and dataset. Reprocessing or retrying the same logical record must not create duplicates — use an idempotent insert, upsert, or equivalent project-consistent approach. Warning cases must still create one record containing warning status and reason. Enabled controls must be stored in a queryable form suitable for dashboard filtering and matrix-style display; do not store only a presentation-formatted string.

### FR-10: Failure Isolation

Coverage-calculation or persistence failure for one dataset must not stop the overall validation run and must not change that dataset's actual validation results. It must be recorded using the project's existing warning or execution-logging mechanism, and must produce a warning coverage record when enough identifying information is available. Never fabricate coverage values, and continue processing remaining datasets.

### FR-11: Warehouse and Business-Area Rollups

Overall warehouse coverage must be column-weighted:

```text
overall_coverage_pct = sum(covered_column_count) / sum(total_available_column_count) * 100
```

Business-area coverage must use the same column-weighted formula within each business area. Do not use an unweighted average of dataset percentages. Exclude warning records with unavailable column counts from percentage denominators, and report warning-record counts separately. Include `Unclassified` as a normal business-area group. Total records verified is the sum of available `records_verified` values. Total individual checks is the sum of `individual_check_count` values. Dataset count is the number of coverage records included in the selected run or grouping.

### FR-12: New Superset Dashboard

Create a new, separate fifth dashboard focused only on validation assurance, coverage, scale, and completeness.

The dashboard must include at minimum: overall warehouse coverage percentage, total records verified, number of covered datasets, total individual checks executed, coverage by business area, enabled control types by dataset in a scan-friendly matrix or equivalent visualization, fully assured datasets, full per-dataset coverage detail, and warning or unavailable coverage count without showing validation failure or mismatch detail.

Use the same dashboard bootstrap conventions, patterns, and tooling as the existing four dashboards. Give the dashboard a unique title, slug, and identity. Do not alter existing chart definitions, slugs, layouts, datasets, or behavior in the first four dashboards. Re-running dashboard creation must not create duplicate datasets, charts, or dashboards. The dashboard must not present row mismatches, failed validations, defect detail, or other failure-oriented content.

### FR-13: Runtime Verification

After implementation and automated testing, run the real coverage workflow and verify the new
Superset dashboard using the available project environment. Do not stop after mocked tests only.

Before marking any runtime verification as `Not verified`, the implementation agent must:

1. Inspect the repository for Podman Compose or other documented local startup instructions.
2. Check whether the required Postgres and Superset services are already running.
3. Inspect available environment variables, `.env` files, mapped ports, and example configurations
   without exposing credentials or complete credential-bearing URLs.
4. Attempt to start only services that are not already running, using the project's documented process.
5. Verify actual service reachability directly:
   * List running containers with `podman ps` or the project-equivalent command.
   * Verify the results database by opening a connection and executing `SELECT 1`.
   * Verify Superset through its mapped host URL and `/health` endpoint.
6. Run the real coverage workflow using an available project configuration.
7. Verify exactly one coverage record is persisted for every processed dataset.
8. Verify warehouse-level and business-area rollups against the persisted dataset-level values.
9. Run or refresh the Superset dashboard bootstrap using the existing project process.
10. Verify the fifth dashboard exists with the required title, slug, datasets, charts, filters,
    and coverage content.
11. Run the dashboard bootstrap a second time and confirm it does not create duplicate datasets,
    charts, or dashboards.
12. Confirm the first four dashboards remain present and unchanged.
13. Record the exact runtime commands attempted and their outputs or sanitized failure reasons.

A service must not be marked unavailable merely because it was not already running.

A failure in a container-management command must not by itself be treated as proof that the
runtime services are unavailable. Verify the actual services directly using the available
container listing, mapped ports, database connectivity, and HTTP health endpoints.

If `podman machine` or an equivalent management command fails but `podman ps`, the database
endpoint, or the Superset health endpoint remains reachable, continue using the running services
and complete runtime verification. Do not restart, recreate, or replace already-running services
unless the documented project process requires it and direct service checks confirm they are unusable.

A runtime item may be marked `Not verified` only after the required service or configuration has
been directly checked and a specific blocking prerequisite remains unavailable. The final report
must state exactly what was checked, which command failed, and what is required to complete the
verification.

### FR-14: Final Implementation Report

The final report must clearly separate implementation status, automated unit-test status, regression-test status, runtime coverage-workflow verification, persistence verification, and Superset dashboard verification.

The report must include: files created and modified, architecture decisions, status of every acceptance criterion, new-test count and final test count, number of coverage records created during runtime verification, warehouse-level coverage result from the verified run, business-area rollup result from the verified run, fifth-dashboard status, duplicate-bootstrap verification result, confirmation that the first four dashboards were unchanged, and the exact reason for anything marked `Not verified`.

---

## Acceptance Criteria

| ID | Acceptance Criterion |
|---|---|
| AC-01 | Every dataset actually processed in a run produces exactly one coverage record for that run, including warning cases where identifying information is available. |
| AC-02 | Total available columns are calculated as the case-insensitive union of source and target columns. |
| AC-03 | Covered columns are the case-insensitive union of resolved primary-key and compare columns, limited to available columns and deduplicated. |
| AC-04 | Column coverage is calculated as covered columns divided by total available columns and is expressed as a percentage. |
| AC-05 | Zero-column or unavailable-schema cases produce warning status and no fabricated percentage. |
| AC-06 | Enabled-control count reflects the number of distinct supported control types enabled after defaults are resolved. |
| AC-07 | Total-supported-control count is deterministic and excludes internal, deprecated, and non-dataset controls. |
| AC-08 | Individual-check count reflects the actual number of configured checks within enabled controls, using a tested rule for every supported control type. |
| AC-09 | Missing business area is stored and reported as `Unclassified` and remains included in all rollups. |
| AC-10 | Records verified uses the existing source-side count-comparison result and does not trigger another full-table count. |
| AC-11 | A coverage calculation failure for one dataset does not stop the run or change that dataset's validation result, and it records a warning. |
| AC-12 | A dataset is fully assured only when column coverage is 100%, every supported control type is enabled, and coverage status is not warning. |
| AC-13 | Overall warehouse coverage uses the documented column-weighted formula, not a simple average of dataset percentages. |
| AC-14 | Business-area coverage uses the same weighted formula and correctly groups tagged and `Unclassified` datasets. |
| AC-15 | Persistence enforces one logical record per run and dataset and does not create duplicates when the same record is retried. |
| AC-16 | Enabled-control data is persisted in a queryable form suitable for dataset-by-control reporting. |
| AC-17 | The fifth dashboard contains all required coverage, records-verified, dataset-count, individual-check, business-area, control-matrix, fully-assured, detail, and warning views. |
| AC-18 | The fifth dashboard contains no failure, mismatch, or defect-detail content from the first four dashboards. |
| AC-19 | Creating or refreshing the dashboard repeatedly does not create duplicate datasets, charts, or dashboards. |
| AC-20 | The charts, slugs, layouts, data, and behavior of the first four dashboards remain unchanged. |
| AC-21 | Existing configurations without the business-area field continue to load and run unchanged. |
| AC-22 | All new calculation, warning, persistence, and aggregation behavior is unit-tested without requiring live databases or Superset. |
| AC-23 | All pre-existing tests continue to pass without modification. |
| AC-24 | Runtime verification persists coverage records using an available project configuration, or the final report states the exact unavailable prerequisite. |
| AC-25 | The final report clearly separates mocked test success from runtime persistence and live dashboard verification. |
| AC-26 | Before live verification is marked unavailable, the agent checks for and attempts the project's documented local Postgres and Superset startup process. |
| AC-27 | The final report lists every runtime command attempted and the exact reason each blocked verification could not complete. |
| AC-28 | Runtime verification does not stop solely because `podman machine` or another container-management command fails when `podman ps`, mapped ports, database connectivity, or the Superset health endpoint remain reachable. |
| AC-29 | Live verification directly confirms results-database connectivity with `SELECT 1` and Superset reachability through `/health` before either service is marked unavailable. |
| AC-30 | The fifth dashboard is verified live, its bootstrap is run twice without duplicates, and the first four dashboards are confirmed unchanged; otherwise each unverified item is reported separately with its exact blocker. |

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Coverage calculation must add negligible runtime and must not perform additional full-table reads beyond existing validation work. |
| NFR-02 | A coverage failure for one dataset must never fail the overall run. |
| NFR-03 | The feature must be additive and backward compatible. |
| NFR-04 | New persistent storage must be added through new sequential migrations without changing existing storage definitions. |
| NFR-05 | Dashboard implementation must use the same conventions and bootstrap tooling as the existing dashboards. |
| NFR-06 | Coverage calculation and aggregation logic must be independently unit-testable. |
| NFR-07 | Persistence operations must be idempotent for the same run and dataset. |
| NFR-08 | Warning messages and persisted reasons must not expose credentials, tokens, or complete credential-bearing URLs. |
| NFR-09 | The implementation must not change existing CLI behavior, validation results, or dashboard behavior. |
| NFR-10 | New dashboard queries and charts must remain responsive for normal project-scale run history. |
