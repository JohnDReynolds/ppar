# ppar Correctness Roadmap: Phase 2 Implementation

Status: Complete  
Implementation date: August 31, 2026  
Starting revision: `718f5054dc34cb88490cc92ffffa825e8448abdc`

## Outcome

Phase 2 now prevents portfolio and benchmark returns with different actual date
coverage from entering attribution or risk calculations:

- Native-frequency observations align only when the complete inclusive
  `(from_date, thru_date)` pair is present on both sides.
- Leading and trailing observations outside the maximal common native-frequency
  window may still be trimmed, but an unmatched or partially overlapping period
  inside that window raises `PparError`.
- Fixed-frequency buckets require equal actual portfolio and benchmark starts and
  ends, complete first-bucket coverage, gapless source intervals, and source rows
  contained within the aligned reporting interval.
- Different source partitions remain supported when their actual inclusive coverage
  is equal, including daily-to-monthly and monthly-to-quarterly consolidation.
- An incomplete terminal bucket may still be omitted when both sources are
  incomplete. If only one source publishes that terminal bucket as complete, the
  mismatch is an error.
- Axys/APX `portperf.csv` and `secperf.csv` period-key sets must be identical after
  portfolio and date selection. No beginning, interior, or ending period is silently
  removed by an inner join.

No financial tolerance, release threshold, public output column, or standard report
artifact was added or removed.

## Test-first evidence

The initial focused regression run against the Phase 1 implementation failed in the
expected alignment cases. It produced 15 failures while 66 tests and 29 subtests
passed. The failures demonstrated:

- native-frequency folding or relabeling of unmatched interior observations;
- fixed-frequency comparison of returns with different starts;
- acceptance of a source interval wider than its reporting bucket;
- acceptance of a gap inside fixed-frequency source coverage; and
- silent removal of unmatched Axys/APX periods.

After implementation and conversion of legacy mixed-granularity tests to request an
explicit fixed frequency, the expanded focused command passed:

```text
./.venv/bin/python -m pytest -q --tb=short \
  tests/test_calculation_invariants.py \
  tests/test_frequency_integration.py \
  tests/test_axys_reconciliation.py \
  tests/test_axys_pipeline.py \
  tests/test_attribution_validation.py \
  tests/test_regression_results.py \
  tests/test_mega_cap_demo_data_contract.py

85 passed, 41 subtests passed
```

The final focused coverage includes symmetric portfolio/benchmark mismatches,
partial overlaps, shared irregular native-frequency gaps, unequal fixed-frequency
starts and ends, interior gaps, over-wide observations, different partitions of
equal coverage, partial first buckets, asymmetric terminal completeness, holiday-
adjusted endpoints, and Axys/APX first/interior/last period mismatches.

## Implementation details

### Native-frequency alignment

The former backward as-of assignment has been removed. `Analytics` now intersects
complete period pairs, identifies the maximal common comparison window, and rejects
any unmatched interval that overlaps that window. Consolidation uses an exact
two-column date join and verifies that every retained source period maps once.

This preserves the established common-history trimming policy without allowing a
return to move into a reporting interval whose dates it did not cover.

### Fixed-frequency coverage

Endpoint qualification still uses the established calendar, weekend, and configured
holiday rules. Before reporting labels replace source dates, `Analytics` now verifies
for each common bucket that:

1. both sources end on the same actual qualified date;
2. each source's component intervals are consecutive and leave no interior date gap;
3. the first accepted bucket starts at a complete boundary;
4. later buckets start consistently after the prior actual endpoint;
5. portfolio and benchmark actual starts agree; and
6. no selected source interval extends outside the aligned bucket.

The existing incomplete-interior warning and symmetric incomplete-terminal omission
remain intact. A new explicit check rejects asymmetric terminal completeness even
when earlier shared history exists.

### Axys/APX period completeness

`filter_to_common_periods()` now performs anti-joins in both directions after checking
for a nonempty intersection. Any difference raises a contextual error that lists
period keys missing from `security_performance` and from `portfolio_performance`.
The validated frames then proceed unchanged; there is no silent common-period filter.

A public-path mutation test removes an interior month from either `portperf.csv` or
`secperf.csv` and confirms that quarterly consolidation cannot hide the omission.

### Demonstration window and documentation images

The packaged source history begins June 1, 2021, which is only one month of 2021 Q2.
Both demonstration scripts and the canonical README-image renderer now begin July 1,
2021, the first complete quarter. The standard demonstration therefore contains 19
complete quarterly observations instead of 20 observations that included a partial
first quarter.

All 11 standard artifacts remain present. The tracked documentation images were
regenerated because their financial window and visible results changed. Six
period-count-dependent images also have revised dimensions; the image manifest and
embedded source fingerprints were updated and validated.

## Complete validation

The routine product gate passed:

- Tests: 274 passed; 99 subtests passed.
- Mypy: no issues in 37 source files.
- Pyright: 0 errors, 0 warnings, 0 information messages.
- Pylint error checks: passed.
- Active-documentation, local-link, terminology, demonstration-reference, and README
  image checks: passed.
- Wheel: `ppar-0.2.0-py3-none-any.whl`, direct universal wheel, passed Twine check.
- Installed-wheel isolation and `pip check`: passed.
- Installed generic demonstration: passed and wrote 11 artifacts.
- Installed Axys/APX demonstration: passed and wrote 11 artifacts.

The unchanged scale gate also passed:

- Analytics large-site 500x: warning only; 12,126 to 6,063,000 rows; timing ratio
  1.09x against the unchanged 1.05x warning and 1.10x failure boundaries.
- Analytics selected-workload 10x: pass; 12,126 to 121,260 rows; timing ratio 1.73x
  against the unchanged 2.10x warning and 2.20x failure boundaries.
- Analytics long-history 5x: pass; 12,246 to 61,230 rows; timing ratio 1.01x against
  the unchanged 1.58x warning and 1.65x failure boundaries.

## Release-gate follow-up discovered during Phase 2

The established long-history harness attempts to extend the generated demonstration's
`THRU_DATE` by replacing an older annotated source line. The current demonstration
uses an unannotated assignment, so that replacement no longer changes the reporting
window. The expanded source files contain five times as many rows and 300 period keys,
but the report calculation still uses the original end date.

An exploratory correction was not retained because it would materially redefine the
established gate. With 25 years of complete calendar-month source data and report
output, the measured ratio was 1.87x, above the existing 1.65x threshold. Repairing
the scenario therefore requires a separate assessment of the intended workload,
evidence for the threshold, and explicit approval before any gate or threshold
change. Phase 2 ran and passed the unchanged gate as required.

## Phase 2 conclusion

Phase 2 is complete. Phase 3 can now make Axys/APX weight reconciliation
evidence-based without relying on silently intersected periods or ambiguously aligned
portfolio and benchmark returns.
