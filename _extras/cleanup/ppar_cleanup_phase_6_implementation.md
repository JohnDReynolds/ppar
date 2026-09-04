# ppar Cleanup Phase 6 Implementation

Status: Complete
Date: September 4, 2026
Baseline revision: `5d5d15682b49784c26b9a6aa53756de53f54f3e9`

## Objective

Remove dead compatibility calculations and archaeological tests without changing any
documented workflow, financial result, output schema, report inventory, or release
threshold.

## Changes

- Removed `Performance.df_overall()`, `Performance.overall_return()`, their private
  cache state, and the adapter's unused self-attribution calculation.
- Removed `utilities.date_str()`, the test-only `MappingDataSource` alias, and the
  unnecessary `AllDataSources` alias layer.
- Removed ten tests that covered only the deleted overall-performance route, an absent
  historical mutation method, absent conversion methods, and a dead utility.
- Removed obsolete negative assertions about an earlier report-output replacement
  policy.
- Simplified the lazy chart import by relying on the chart dependencies already required
  by the base package instead of translating an unreachable missing-dependency branch.
- Preserved existing in-progress correctness changes in the adapter, risk calculations,
  and their tests.

The proposed chart-comment cleanup was deliberately omitted. The image provenance gate
fingerprints all top-level ppar sources, and changing a rendering module solely to remove
comments does not provide enough value to justify that source churn.

## Accounting

Phase 6 added 5 lines and removed 252 lines, for a net reduction of 247 lines:

- production: 3 added, 70 removed, net 67 removed;
- tests: 2 added, 182 removed, net 180 removed.

The suite changed from 378 tests and 524 subtests to 368 tests and 522 subtests. The ten
tests and two subtests removed were confined to the deleted compatibility behavior and
negative archaeology.

## Validation

- Focused cleanup tests: 96 tests and 81 subtests passed.
- Complete suite: 368 tests and 522 subtests passed in 31.47 seconds.
- Mypy: clean across 38 source files.
- Pyright: 0 errors and 0 warnings.
- Pylint errors-only and focused unused/deprecated/unreachable checks: clean.
- README image regeneration and provenance check: passed.
- Universal wheel build and Twine validation: passed.
- Isolated wheel installation, dependency check, CLI version, generic setup, and Axys/APX
  setup: passed.
- Both installed demonstrations produced the ordered 11-report bundle.
- `git diff --check`: passed.

The complete release-candidate and 500x scale sequence remains assigned to Phase 9,
after the cross-cutting contract and test-ownership work.
