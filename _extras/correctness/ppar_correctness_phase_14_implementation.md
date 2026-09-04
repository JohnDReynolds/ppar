# ppar Correctness Roadmap: Phase 14 Implementation

Status: Complete
Implementation date: September 4, 2026

## Outcome

Phase 14 closes the correctness reassessment performed after the `perfattr` migration.
Three defects were reproduced before implementation and corrected with narrow changes
at ppar's host boundaries:

- caller-supplied generic contribution can no longer override ppar's documented
  `weight * return` calculation;
- inferred display names now come only from financially retained periods; and
- annualized returns that cannot be represented as finite values fail explicitly.

The reassessment also reconciles the roadmap's historical Phase 9 recommendation
with the current public identity contract: generic surrounding whitespace is trimmed
consistently, blank identities fail, and meaningful identity text such as leading
zeroes and internal spaces remains intact.

No output column, public report schema, tolerance, warning threshold, failure
threshold, invariant, or release gate changed.

## Pre-fix evidence

The new focused tests were run before changing production code. All four test methods
failed for the intended reasons:

1. A two-period input carrying contributions that disagreed with `weight * return`
   produced contribution-derived subperiod returns instead of the supplied returns.
2. A direct `Performance` date window chose `Alpha New` from an excluded later period
   instead of retained `Alpha Old`.
3. Portfolio history extending beyond benchmark history created a false conflicting
   name assignment from an unmatched trailing period.
4. Twelve finite, extremely large monthly returns published an infinite annualized
   mean return and emitted a runtime overflow warning instead of raising `PparError`.

The pre-fix focused result was 4 failures, with no unrelated failure.

## Implementation

### Generic contribution boundary

`_load_performance_input()` no longer forwards a raw generic `contribution` column to
portable preparation. Polars input selection is limited to the established required
columns plus optional display name. Canonical CSV input still passes through the
portable reader and its structural validation, but any returned source contribution
is removed before calculation.

`perfattr` consequently derives the internal contribution from normalized weight and
return for both source types. The existing calculated contribution columns remain
available to attribution and reporting.

### Retained-period display metadata

Raw optional names remain paired with their source dates and identifiers until
portable preparation finishes. `_classification_items_for_prepared()` then:

- applies the same surrounding-whitespace normalization used at the public boundary;
- limits candidates to identifiers and date bounds present in prepared output; and
- deterministically selects the latest accepted name for each identifier.

Direct `Performance` date windows and paired `Analytics` alignment therefore use the
same retained-history rule.

### Finite annualization

`RiskStatistics._annualize_return()` now distinguishes deliberate undefined values
from invalid or unrepresentable values. Insufficient history and `NaN` retain their
existing undefined result. Nonfinite periodic inputs, Python exponentiation overflow,
or a nonfinite annualized result raise contextual `PparError`.

Using `math.pow()` also prevents a NumPy runtime warning from becoming the only signal
that a report value overflowed.

## Regression coverage

The focused additions cover:

- conflicting input contribution through both Polars and canonical CSV sources;
- subperiod return and contribution, source-period totals, and compounded overall
  return under the weight-times-return contract;
- a direct date window with an excluded later rename;
- portfolio/benchmark alignment with unmatched trailing named history; and
- finite monthly inputs whose annualized mean cannot be represented finitely.

The complete focused normalization and risk-validation files pass with 53 tests and
41 subtests.

## Validation

The unchanged release-candidate command
`./.venv/bin/python scripts/check_release_candidate.py` passed with:

- 378 tests and 524 subtests;
- Mypy clean across 38 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- README-image provenance refreshed and current;
- wheel build and Twine metadata validation passing;
- isolated wheel installation, import-origin validation, and `pip check` passing;
- both installed setup demonstrations producing their ordered 11-report bundles; and
- the complete unchanged 500x scale workflow passing.

The scale measurements were:

- large-site 500x: 12,126 to 6,063,000 rows, 9.39s to 9.57s (1.020x), observation
  only with no performance threshold;
- selected-workload 10x: 12,126 to 121,260 rows, 0.38s to 0.77s (2.036x), observation
  only with no performance threshold; and
- genuine long-history 5x: 12,246 to 61,230 rows, 9.51s to 10.16s (1.068x), below
  the unchanged 1.58x warning and 1.65x failure boundaries.

README images were regenerated solely to update their embedded source provenance
fingerprints after production code changed. Their filenames, dimensions, and file
sizes remain unchanged.
