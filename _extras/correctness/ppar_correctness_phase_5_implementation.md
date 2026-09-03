# ppar Correctness Roadmap: Phase 5 Implementation

Status: Complete  
Implementation date: August 31, 2026  
Starting revision: `718f5054dc34cb88490cc92ffffa825e8448abdc`

## Outcome

Phase 5 hardens the numerical and financial domains of ex-post risk statistics:

- a representable low-volatility benchmark retains a finite beta instead of being
  classified as constant by NumPy's fixed default absolute tolerance;
- a genuinely constant benchmark, or variation below one `float64` resolution unit
  at the scale of its values, continues to produce an undefined beta;
- the same scale-aware variation decision prevents valid low-volatility correlation
  from being discarded;
- accepted NumPy signed integers, unsigned integers, `float32`, and `float64` values
  are normalized to `float64` before subtraction or any other calculation;
- periodic portfolio and benchmark returns must be finite and strictly greater than
  -100% before risk statistics are calculated;
- positive leveraged returns retain no artificial upper cap; and
- a derived return-like statistic at or below -100% cannot be geometrically
  annualized into a plausible but unsupported value.

No financial tolerance, release threshold, public output column, or standard report
artifact was added, removed, or relaxed.

## Test-first evidence

The focused Phase 5 regressions were introduced against the Phase 4 implementation.
The initial run produced 14 failures while 29 tests and 13 subtests passed. Those
failures demonstrated that:

- a low-volatility benchmark with independently calculated beta 2 produced `NaN`;
- shrinking otherwise equivalent return series changed a defined beta to `NaN`;
- two nonconstant low-volatility observations could not define beta;
- signed integer and `float32` arrays were not normalized to `float64`;
- unsigned subtraction wrapped around and changed the information ratio;
- returns equal to or below -100% were accepted through both direct arrays and
  `Performance` inputs; and
- twelve -200% returns could produce a superficially valid annualized result.

The final focused suite contains ten new test methods. Its parameterized cases cover
three common return scales, four accepted NumPy dtypes, both return sources, exact
-100%, values just below -100%, -200%, ordinary negative returns, positive leveraged
returns, a constant benchmark, the two-observation minimum, and invalid derived
annualization.

## Scale-aware beta and correlation

Beta continues to use sample covariance divided by sample benchmark variance, with
`ddof=1` on both quantities. The zero-variance decision no longer uses
`np.isclose(variance, 0.0)`, whose default absolute tolerance is much too large for a
squared return quantity.

All risk arrays are first represented as `float64`. For a finite return series, ppar
then compares its sample standard deviation with `math.ulp(max(abs(returns)))`, one
representable `float64` unit at the scale of the input. Exact zero variance is handled
directly. This decision is invariant to a common scaling of portfolio and benchmark
returns and still treats numerically indistinguishable observations as constant.

Correlation uses the same effective-variation decision for both series. This avoids
reporting a finite beta beside an incorrectly undefined correlation for the same
low-volatility observations.

## NumPy arithmetic normalization

The public NumPy path still accepts only one-dimensional, real integer or floating
arrays. After validating shape and dtype, both arrays are converted to `float64`.
Length, minimum-observation, finiteness, and compounding-domain validation then apply
to those normalized arrays.

Normalizing before calculating active returns prevents unsigned subtraction such as
`0 - 1` from wrapping to the dtype's maximum value. It also gives signed integers,
unsigned integers, `float32`, and `float64` one calculation model. Performance-backed
period totals are normalized to the same dtype.

## Geometric-compounding domain

Every portfolio and benchmark periodic return must satisfy:

```text
return > -1.0
```

This makes every wealth relative, `1 + return`, positive for geometric
annualization and consistent with the existing logarithmic-linking domain. Exactly
-100% and every lower return raise contextual `PparError` before statistics are
calculated. Error context identifies the portfolio or benchmark source and includes
sample invalid indices and values.

There is no fixed upper return boundary. This retains valid positive leveraged
returns while rejecting losses that make the report's compounding model undefined.

The same guard now applies immediately before a finite return-like statistic is
annualized. For example, source returns can all exceed -100% while a regression
intercept is below -100%; ppar reports an error rather than raising a negative wealth
relative to an integer power and publishing the resulting positive number.

## Documentation and retained images

`docs/methodology.md` records the compounding domain, NumPy normalization, and
scale-aware beta convention. `docs/python_api.md` now includes a direct NumPy risk
example and its validation contract.

The retained output gallery was regenerated with the current source fingerprint.
The demonstration data already satisfied the new risk domain, so its report inventory
and visible calculation contract remain unchanged.

## Complete validation

The complete release-candidate gate passed:

- Tests: 309 passed; 314 subtests passed.
- Mypy: no issues in 37 source files.
- Pyright: 0 errors, 0 warnings, 0 information messages.
- Pylint error checks: passed.
- Active-documentation, local-link, terminology, demonstration-reference, and README
  image checks: passed.
- Wheel: `ppar-0.2.0-py3-none-any.whl`, direct universal wheel, passed Twine check.
- Installed-wheel isolation and `pip check`: passed.
- Installed vendor-neutral demonstration: passed and wrote 11 artifacts.
- Installed Axys/APX demonstration: passed and wrote 11 artifacts.

The unchanged scale gate also passed:

- Analytics large-site 500x: pass; 12,126 to 6,063,000 rows; timing ratio 1.04x
  against the unchanged 1.05x warning and 1.10x failure boundaries.
- Analytics selected-workload 10x: pass; 12,126 to 121,260 rows; timing ratio 1.85x
  against the unchanged 2.10x warning and 2.20x failure boundaries.
- Analytics long-history 5x: pass; 12,246 to 61,230 rows; timing ratio 0.95x against
  the unchanged 1.58x warning and 1.65x failure boundaries.

One earlier integrated attempt narrowly exceeded the large-site timing boundary at a
displayed 1.10x. Investigation confirmed that Phase 5 processes the same 19-period
risk arrays in the baseline and scaled versions; none of its added operations scales
with the millions of unselected site rows. An unchanged standalone rerun passed at
1.07x, and the complete integrated rerun above passed at 1.04x. No threshold, sample
count, workload, or timing rule was changed.

The known long-history harness limitation remains the separately remediable Item 15
in Phase 7. Phase 5 did not change that scenario.

## Phase 5 conclusion

Phase 5 is complete. Phase 6 can now address duplicate heatmap names and align the
methodology with the implemented two-effect attribution presentation.
