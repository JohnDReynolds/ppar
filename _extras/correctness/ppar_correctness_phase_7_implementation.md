# ppar Correctness Roadmap: Phase 7 Implementation

Status: Complete  
Implementation date: August 31, 2026  
Starting revision: `718f5054dc34cb88490cc92ffffa825e8448abdc`

## Outcome

Phase 7 repairs the long-history scale scenario so its fivefold source history
reaches calculation and every standard report:

- the generated `portperf.csv` and `secperf.csv` files contain 300 matching,
  consecutive monthly periods from June 1, 2021 through May 31, 2046;
- period endpoints follow the same weekend and configured-holiday calendar used by
  production frequency consolidation;
- the generated demonstration's executable `THRU_DATE` is changed through a checked
  transformation that must replace exactly one assignment;
- the transformed script is executed without running its main entry point to prove
  that its bound is May 31, 2046;
- the scale gate independently calculates the resulting reporting dates and requires
  99 complete quarterly periods from July 1, 2021 through March 30, 2046; and
- all 11 long-history report artifacts must still exist and be nonempty.

Profiling also removed one quadratic period-alignment operation and introduced an
equivalent large-heatmap annotation path. The corrected workload now passes the
existing timing gate without changing its 1.58x warning or 1.65x failure boundary.

No financial tolerance, release threshold, public output column, or standard report
artifact was added, removed, or relaxed.

## Test-first evidence

The initial Phase 7 harness regressions produced four failures while five tests and
eight subtests passed. They demonstrated that:

- no checked demo-bound transformation existed;
- no calendar-correct monthly history generator existed;
- the obsolete source substitution left `THRU_DATE` at May 29, 2026; and
- no assertion proved that expanded source rows reached report calculation.

After the functional harness was corrected, a profiling regression failed because
`_period_tuples()` was called 198 times while aligning the 99 portfolio and benchmark
quarterly periods. The required contract is two materializations, one per source.

The large-heatmap regression initially failed because there was no alternative to
constructing a separate Matplotlib text artist for every cell. Its final form renders
a 561-cell matrix, verifies that all 561 annotations are drawn, and requires a valid
PNG from the large-matrix path.

Phase 7 adds seven test methods: five scale-harness and alignment regressions and two
chart-layout and large-matrix regressions. The runtime-dependency contract was also
updated for the direct Pillow usage.

## Deterministic history construction

The former history builder copied five-year blocks with calendar-year offsets. That
could produce gaps, overlaps, or invalid business endpoints because weekdays, leap
years, and holidays do not repeat on a five-year cycle.

The replacement first verifies that the original 60 source periods follow the
configured monthly calendar. It then generates 300 consecutive periods. Each period
ends on the calendar month's effective business endpoint after rolling backward over
weekends and configured holidays; the next period begins on the following calendar
day. Tests explicitly cover leap-day February, a weekend month-end, and the configured
March 29, 2024 holiday.

The performance values repeat in five cycles, but their date keys come from this one
continuous schedule. Both Axys/APX performance files use the same generated keys.

## Checked demonstration bound and reporting horizon

The previous unverified `str.replace()` searched for an obsolete annotated line and
silently made no change. The new transformation matches either an annotated or
unannotated executable `THRU_DATE = dt.date(...)` assignment and requires exactly one
match. Zero or multiple matches are errors. The generated module is then loaded and
its actual Python value is compared with the intended final source date.

Source-row counts alone are no longer accepted as proof. After the timed demonstration
has written its 11 reports, the gate invokes the generated analytics builder and
checks its subperiod output. It must contain exactly 99 quarterly date pairs beginning
July 1, 2021 and ending March 30, 2046.

## Profiling and optimizations

The genuine workload initially measured 1.57x, 1.60x, and 1.84x in repeated runs. The
last result exceeded the unchanged 1.65x boundary, so the implementation was profiled
rather than treating the result as noise or changing the gate.

Two scaling costs were corrected:

1. Fixed-frequency alignment converted the complete source DataFrames into Python
   date pairs once for every portfolio and benchmark reporting bucket. The lists are
   now materialized once per source and reused, reducing 198 collections to two.
2. Wide heatmaps created and measured thousands of independent Matplotlib text
   artists. Cell annotations no longer participate in margin measurement because
   they lie entirely inside their axes. Heatmaps above 500 cells preserve every
   formatted value through an Agg and Pillow raster-annotation path without creating
   one Matplotlib artist per value. Ordinary heatmaps retain the established renderer.

The layout-measurement exclusion produced pixel-identical PNGs in direct comparison.
The large-matrix path retains the same cells, color-dependent light/dark annotation
choice, four-decimal formatting, labels, titles, and output format. Pillow is now an
explicit runtime dependency rather than only a development dependency.

Three repeated genuine-history measurements after both optimizations were 1.41x,
1.46x, and 1.62x. All remained below the unchanged 1.65x failure boundary. The
complete focused 500x workflow subsequently measured 1.39x.

## Complete validation

The complete release-candidate gate passed:

- Tests: 322 passed; 314 subtests passed.
- Mypy: no issues in 37 source files.
- Pyright: 0 errors, 0 warnings, 0 information messages.
- Pylint error checks: passed.
- Active-documentation, local-link, terminology, methodology, demonstration-reference,
  and README image checks: passed.
- Wheel: `ppar-0.2.0-py3-none-any.whl`, direct universal wheel, passed Twine check.
- Installed-wheel isolation and `pip check`: passed.
- Installed vendor-neutral demonstration: passed and wrote 11 artifacts.
- Installed Axys/APX demonstration: passed and wrote 11 artifacts.

The unchanged scale gate also passed:

- Analytics large-site 500x: warning; 12,126 to 6,063,000 rows; timing ratio 1.09x
  against the unchanged 1.05x warning and 1.10x failure boundaries.
- Analytics selected-workload 10x: pass; 12,126 to 121,260 rows; timing ratio 1.93x
  against the unchanged 2.10x warning and 2.20x failure boundaries.
- Analytics long-history 5x: pass; 12,246 to 61,230 rows; timing ratio 1.45x against
  the unchanged 1.58x warning and 1.65x failure boundaries.

No threshold, sample count, report selection, or timing rule was changed.

## Phase 7 conclusion

Phase 7 is complete. Phase 8 can perform the roadmap's final integrated regression,
artifact-contract, failure-publication, and release-candidate review.
