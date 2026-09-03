# ppar Correctness Roadmap: Phase 10 Implementation

Status: Complete  
Implementation date: September 1, 2026

## Outcome

Phase 10 removes fixed absolute zero tests from ex-post risk-ratio division. Sharpe,
Sortino, and information ratios now decide whether risk is resolvable from the
floating-point scale of the source returns. Treynor uses every finite nonzero beta as
an ordinary signed divisor, including a small negative beta.

Exact or resolution-limited zero nonnegative risk retains the established boundary:
a zero numerator produces `NaN`, while a nonzero numerator produces signed infinity.
An undefined beta keeps Treynor undefined. The corrected periodic Sharpe and Sortino
results flow through their annualized forms, and corrected Sharpe flows through
M-squared.

## Test-first evidence

Nine focused regression methods were added before the production change. The initial
risk-invariant run had five failures, demonstrating that:

- a valid Sharpe ratio of approximately `2.2360679775` became `NaN` at a small
  absolute return scale;
- valid small Sortino and information-ratio denominators were classified as zero;
- a finite negative beta near `-1e-9` produced positive infinity instead of a finite
  negative Treynor ratio; and
- the minimum two-observation sample could not retain a small finite Sharpe ratio.

Independent NumPy calculations supply the expected Sharpe, Sortino, information,
beta, and Treynor values. Scale-metamorphic cases use three positive return scales,
and full-year cases verify annualized Sharpe, annualized Sortino, and M-squared.

The boundary cases cover exact zero numerator over zero risk, nonzero numerator over
zero risk, one-ULP volatility, one-ULP downside shortfall, zero beta, undefined beta,
ordinary volatility, and the two-observation minimum.

## Implementation

### Source-aware risk denominators

The generic division helper no longer calls `np.isclose()` for either operand. It
performs ordinary division for every finite nonzero denominator and applies the
zero-risk result only when the denominator is exactly zero or its caller has proven
that its source data cannot resolve the risk magnitude from zero.

Sharpe and information ratio reuse the scale-aware variation rule established for
beta and correlation. Sortino compares downside deviation with one `float64` unit at
the maximum scale of the source returns and periodic minimum acceptable return.
No absolute return-level cutoff remains in these ratio decisions.

### Signed and zero beta

Treynor does not apply an effective-zero magnitude test to a finite nonzero beta.
This preserves the denominator's sign and produces the ordinary quotient for the
tested beta near `-1e-9`.

A mathematically zero covariance can acquire a tiny residual when positive and
negative centered cross-products cancel. Beta now treats a covariance no larger than
one ULP at the scale of those centered cross-products as exact zero. This restores
the established signed-infinity result for zero beta without discarding a small beta
supported by observable source co-variation.

### Exact constant sources

Testing the undefined-beta boundary exposed an additional numerical artifact: twelve
identical `0.02` returns produced a nonzero NumPy sample variance because their
calculated mean rounded slightly. The variation check now recognizes an exactly
constant source series before calculating variance. Genuinely constant risk is
therefore zero even when a derived mean would introduce a rounding residue.

### Documentation

The `RiskStatistics` API docstring, methodology, and Python API guide now explain the
source-resolution rule, zero-risk outcomes, covariance cancellation rule, and signed
Treynor behavior.

## Validation

The complete focused risk suite passed with 43 tests. The combined risk, public-output,
and stored-regression selection passed with 60 tests.

`./.venv/bin/python scripts/check_project.py` passed with:

- 353 tests and 435 subtests;
- Mypy clean across 38 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- all documentation-image checks current;
- wheel build, Twine validation, isolated installation, and `pip check` passing; and
- both installed setup demonstrations producing their unchanged ordered bundles of
  11 reports.

The documentation gallery was regenerated for the corrected source fingerprint. All
12 retained images remain in the documented inventory; no report or image selection
changed.

The unchanged 500x scale workflow passed:

- large-site 500x median paired ratio: 1.096x, above the unchanged 1.05x warning
  boundary and below the unchanged 1.10x failure boundary;
- selected-workload 10x ratio: 1.894x, below the unchanged 2.10x warning and 2.20x
  failure boundaries; and
- genuine long-history 5x ratio: 1.325x, below the unchanged 1.58x warning and 1.65x
  failure boundaries.

No public output column, report inventory, financial formula, established tolerance,
test threshold, or performance gate was changed or relaxed.
