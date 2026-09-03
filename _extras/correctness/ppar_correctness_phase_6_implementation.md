# ppar Correctness Roadmap: Phase 6 Implementation

Status: Complete  
Implementation date: August 31, 2026  
Starting revision: `718f5054dc34cb88490cc92ffffa825e8448abdc`

## Outcome

Phase 6 removes heatmap ambiguity without changing report schemas or artifacts:

- each classification identifier now occupies one stable heatmap row across the
  complete reporting period;
- display-name collisions are detected across every chart date, not only the first;
- identifiers involved in a collision use `identifier: name` labels;
- a name change retains one series and uses the identifier's chronologically latest
  display name;
- duplicate values for one identifier and date fail before pivoting; and
- the heatmap pivot no longer uses `aggregate_function="first"` to silently discard
  a colliding value.

The methodology now accurately describes ppar's two-effect attribution presentation.
ppar reports allocation and portfolio-weighted selection. The selection output
combines the terms that a conventional three-effect presentation identifies as
benchmark-weighted selection and interaction; there is no separate interaction
output column.

No financial tolerance, release threshold, public output column, or standard report
artifact was added, removed, or relaxed.

## Test-first evidence

Three initial renderer regressions were introduced against the Phase 5
implementation. Two failed and one passed:

- when a second identifier acquired an existing display name after the first date,
  its later value was discarded and replaced with zero in its original row; and
- when one identifier's name changed, its values were split between two heatmap rows.

The first-date duplicate case passed because the previous implementation inspected
only the first date and prefixed identifiers in that limited case. This established
why existing demonstrations could look correct while later collisions remained
undetected.

The final Phase 6 suite adds six test methods:

- three heatmap identity scenarios covering a late collision, an initial collision,
  and a chronological name change;
- one rejection case proving duplicate identifier/date values cannot reach the
  pivot;
- one numerical attribution identity proving portfolio-weighted selection equals
  conventional selection plus interaction; and
- one documentation contract check for the two-effect description.

## Stable heatmap identity

Heatmap preparation now retains the classification identifier until a stable label
has been chosen. It scans all chart rows to find names associated with more than one
identifier. Every affected identifier is prefixed in the visible label, even when the
collision first appears late in the period.

For an identifier whose name changes, rows are ordered chronologically and the latest
name represents the complete series. This matches the established display-name
selection contract elsewhere in the package and prevents one identifier from being
split across historical labels.

Before pivoting, ppar proves that each date and identifier has exactly one metric
value and that the resulting display labels are unique. The pivot is then performed
without an aggregation function. A malformed or ambiguous input therefore raises an
explicit error instead of selecting an arbitrary first value.

## Two-effect attribution methodology

For defined group returns, the reported selection effect is:

```text
portfolio weight × (portfolio group return - benchmark group return)
```

The conventional three-effect terms are:

```text
selection   = benchmark weight × active group return
interaction = (portfolio weight - benchmark weight) × active group return
```

Their sum equals ppar's portfolio-weighted selection effect. The numerical regression
checks both forms against `Selection_Effect_Simple` and confirms that no interaction
column is present. `docs/methodology.md` explains this presentation, and the executable
documentation gate requires that explanation while rejecting the retired statement
that ppar reports a separate interaction effect.

## Reports and retained images

The retained output gallery was regenerated with the current source fingerprint.
The standard data has no heatmap name collisions, so the report inventory remains
unchanged.

Both source-generated demonstrations passed and each wrote all 11 expected artifacts.
The installed-wheel gate repeated both demonstrations successfully.

## Complete validation

The complete release-candidate gate passed:

- Tests: 315 passed; 314 subtests passed.
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

- Analytics large-site 500x: warning; 12,126 to 6,063,000 rows; timing ratio 1.07x
  against the unchanged 1.05x warning and 1.10x failure boundaries.
- Analytics selected-workload 10x: pass; 12,126 to 121,260 rows; timing ratio 1.84x
  against the unchanged 2.10x warning and 2.20x failure boundaries.
- Analytics long-history 5x: pass; 12,246 to 61,230 rows; timing ratio 1.00x against
  the unchanged 1.58x warning and 1.65x failure boundaries.

The large-site result remained within the established passing range. No threshold,
sample count, workload, or timing rule was changed.

## Phase 6 conclusion

Phase 6 is complete. Phase 7 can now repair the genuine long-history scale workload
so its expanded source history reaches report calculation and output.
