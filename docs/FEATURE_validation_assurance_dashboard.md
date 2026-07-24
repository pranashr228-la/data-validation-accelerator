# Feature: Validation Assurance & Coverage Dashboard

## Status

| Field      | Value                                                                                   |
| ---------- | ---------------------------------------------------------------------------------------- |
| Priority   | High                                                                                      |
| Status     | Approved — Ready for Implementation                                                       |
| Complexity | Medium                                                                                    |
| Output     | New coverage metrics per validation run, plus a new 5th Superset dashboard                |

---

## Problem

DVA currently ships four dashboards. Every chart across all four shows what passed, failed, or
mismatched for a single dataset's source-vs-target comparison. None of them answer a different,
equally important question: how much of the warehouse is actually protected by automated
validation, and how thoroughly?

A data governance lead or executive today cannot see, for example, that 95.8% of warehouse
columns are covered by automated checks, or that hundreds of individual automated controls ran
across the warehouse in the last run. The tool can prove there are defects; it cannot yet prove
the scale and completeness of its own coverage.

Add a new computation that measures validation coverage and control completeness for every
dataset in a run, and present it through a brand-new dashboard that is entirely distinct from
the first four — one that shows the strength and scale of the validation framework itself,
never failure or mismatch detail.

---

## Goal

For every dataset validated in a run, calculate:

* How much of its columns are actually covered by the configured checks.
* How many distinct validation controls are enabled and how many individual checks they
  represent.
* Which business area the dataset belongs to, so coverage can be rolled up by business area
  rather than only by technical table name.

Persist these measurements so they can be reported per run, per dataset, and per business area,
and present them through a new dashboard focused entirely on coverage, scale, and completeness.

---

## Business Questions This Feature Answers

* How much of our data warehouse is protected by automated validation — by table, by column, by
  business area?
* How many records were successfully verified in the most recent run?
* How many individual automated controls are actually running, not just how many validation
  types are turned on?
* Which business areas have the strongest validation coverage?
* Which datasets have complete, full-spectrum validation coverage?

---

## In Scope

* A way to tag a dataset with a business area/domain, optional, backward compatible
* Calculating column coverage: how many of a dataset's available columns are actually checked
  versus how many exist in total
* Calculating control coverage: how many of the validation control types are enabled for a
  dataset, and how many individual checks that represents
* Persisting these coverage measurements per dataset, per run
* Rolling coverage up by business area
* Identifying datasets with complete coverage ("Fully Assured")
* A new, separate dashboard presenting coverage, scale, and completeness — never failure detail
* Unit tests for the new coverage calculations

## Out of Scope

* Any change to the pass/fail logic of the existing validation types
* Any change to the charts, data, or behavior of the first four existing dashboards
* Modifying any existing results table or view definition
* Automatically inferring a dataset's business area or its foreign-key relationships
* Backfilling coverage for runs that occurred before this feature existed

---

## Source Data Mapping

| Required Field | Derived From | Notes |
|---|---|---|
| Total available columns | The full column list on each side of a dataset's comparison | Already obtainable via existing schema introspection capability used by schema-contract validation |
| Covered columns | The dataset's configured primary key plus configured compare columns | Already part of every dataset's configuration |
| Enabled validation controls | The dataset's fully resolved validation configuration (post-default-application) | Already part of every dataset's configuration once defaults are applied |
| Individual check count | The number of metrics/checks/rules configured within each enabled control type | Already part of every dataset's configuration |
| Records verified | The row counts already produced by the existing count comparison for the same dataset and run | Already produced during a normal run |
| Business area | A new, optional tag on a dataset | New — user-supplied, not inferred |

---

## Functional Requirements

### FR-01: Business Area Tag

A dataset may optionally be tagged with a business area (e.g. "Sales", "Customer", "Finance").
If a dataset is not tagged, it must be treated as belonging to an "Unclassified" area. Existing
configurations that do not use this tag must continue to load and run exactly as they do today.

### FR-02: Column Coverage

For every dataset validated in a run, determine:

* The total number of distinct columns available across the source and target sides of the
  comparison.
* The number of those columns that are actually covered by the dataset's configured checks
  (its primary key plus its configured compare columns).
* The resulting coverage percentage: covered columns divided by total available columns.

Column names must be compared without regard to letter case, consistent with how the rest of
the tool already treats column-name matching between systems that use different casing
conventions.

### FR-03: Control Coverage

For every dataset validated in a run, determine:

* How many of the distinct validation control types are enabled for that dataset.
* How many individual checks those enabled controls actually represent — not just whether a
  control type is on or off, but the real count of metrics, checks, and rules configured within
  it. A control type with many configured checks must count for more than a control type with
  a single configured check.

### FR-04: Records Verified

For every dataset validated in a run, capture the row counts that were already produced by the
existing count comparison for that dataset and run, so that a "total records verified" figure
can be reported without any additional data fetching.

### FR-05: Fully Assured Classification

A dataset must be classified as fully covered when both of the following are true:

* Its column coverage is 100%.
* Every one of the validation control types is enabled for it.

### FR-06: Persistence

All of the above measurements must be persisted per dataset, per run, in a way that can be
queried and rolled up:

* Per run (overall coverage, total records verified, total individual checks executed).
* Per business area (average coverage, dataset count).
* Per dataset (detailed coverage breakdown, which control types are enabled).
* As a list of fully-assured datasets.

### FR-07: Failure Isolation

If coverage cannot be calculated for a particular dataset in a run (for example, because its
schema could not be read), this must not stop the run, must not affect that dataset's actual
validation results, and must be recorded as a warning rather than a silent gap or a fabricated
value.

### FR-08: New Dashboard

Present the coverage measurements through a new, separate dashboard that is structurally
distinct from the first four. This dashboard must never show failure or mismatch detail — its
entire purpose is to communicate the scale and completeness of the validation framework
positively. At minimum it must show:

* Overall coverage percentage across the warehouse.
* Total records verified.
* How many tables/datasets are covered.
* Total number of individual automated checks executed.
* Coverage broken down by business area.
* Which validation control types are enabled per dataset, in a way that is easy to scan across
  many datasets at once.
* The list of fully-assured datasets.
* The full per-dataset coverage detail, for drill-down.

The new dashboard must not alter, remove, or duplicate anything shown on the first four
dashboards, and must not be reachable in a way that confuses it with them (it needs its own
clear identity/title).

---

## Acceptance Criteria

| ID | Acceptance Criterion |
|---|---|
| AC-01 | Every dataset actually validated in a run produces exactly one coverage measurement for that run. |
| AC-02 | Column coverage is correctly calculated as covered columns divided by total available columns, expressed as a percentage. |
| AC-03 | Control coverage correctly counts how many of the distinct control types are enabled, not just whether validation ran at all. |
| AC-04 | The individual-check count reflects the real number of configured checks within enabled controls, not merely the number of control types turned on. |
| AC-05 | A dataset with no business area tag is treated as "Unclassified" and is still included in every coverage calculation and rollup. |
| AC-06 | A coverage calculation failure for one dataset does not stop the run, does not affect that dataset's actual validation results, and is recorded as a warning. |
| AC-07 | A dataset is classified as fully assured only when it has 100% column coverage and every control type enabled; a partially covered dataset is never classified this way. |
| AC-08 | Coverage rolled up by business area correctly reflects the datasets tagged to that area. |
| AC-09 | The new dashboard is created without altering the charts, data, or behavior of the first four existing dashboards. |
| AC-10 | Re-creating/refreshing the new dashboard does not produce duplicate charts or duplicate dashboards. |
| AC-11 | All pre-existing tests continue to pass without modification. |
| AC-12 | Existing configurations that do not use the new business-area tag continue to load and run without any error. |

---

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Coverage calculation must add negligible runtime to a validation run — it must not require any additional full-table data fetch beyond what schema introspection already costs. |
| NFR-02 | A coverage calculation failure for one dataset must never fail the overall run. |
| NFR-03 | No breaking changes to any existing configuration, results storage, dashboard, or command — this feature must be purely additive. |
| NFR-04 | Any new persistent storage this feature requires must be added alongside existing storage without altering or removing anything that exists today. |
| NFR-05 | The new dashboard must be built using the same conventions, patterns, and tooling already used to build the existing four dashboards — it must not introduce a new, different way of building dashboards. |
| NFR-06 | All new coverage calculation logic must be independently unit-testable without requiring a live database or dashboard server. |
