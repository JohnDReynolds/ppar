# ppar Correctness Roadmap: Phase 4 Implementation

Status: Complete  
Implementation date: August 31, 2026  
Starting revision: `718f5054dc34cb88490cc92ffffa825e8448abdc`

## Outcome

Phase 4 restores conservation across accepted irregular histories, multi-period
contributions, mapped signed groups, and direct attribution construction:

- overall identifier weights are averaged over observed source-period days rather
  than calendar days for which no observation exists;
- an inexpensive production audit requires overall weights to sum to 1.0;
- `Performance.df_overall()` uses the established logarithmic linking coefficients,
  so identifier contributions sum to the geometrically linked total return;
- an inexpensive production audit requires those linked contributions to foot;
- a mapped group with exactly zero net weight and nonzero contribution retains its
  contribution and represents its mathematically undefined return as null;
- Brinson-Fachler total effect is calculated directly from contributions and weights,
  without fabricating a return for a zero-net group;
- allocation remains standard when the benchmark group return is defined; otherwise
  allocation is zero and selection carries the complete total effect; and
- direct `Attribution` construction validates that both source classification names
  match the requested classification.

No financial tolerance, release threshold, public output column, or standard report
artifact was added, removed, or relaxed.

## Test-first evidence

The focused regressions were added before the Phase 4 implementation. Against the
Phase 3 code, the initial focused run produced eight failures while 60 tests and
seven subtests passed. The failures demonstrated that:

- a missing calendar month diluted otherwise valid overall weights;
- irregular histories of unequal period length used the calendar span instead of
  accepted observed coverage;
- two 10% single-security periods produced a 20% overall contribution beside a 21%
  linked return;
- multi-security contributions did not match an independent Carino calculation;
- a zero-net mapped signed group lost its contribution when return was forced to
  zero; and
- direct attribution could label two `Security` performances as `Sector`.

The final regressions also cover continuous histories, negative returns, a zero
linked total return, portfolio and benchmark weight footing, exactly zero
weight/contribution, a nonzero near-zero weight, null-safe HTML/CSV/chart output,
and both defined and undefined benchmark group returns.

## Observed-period overall weights

For each accepted source period, ppar uses its inclusive elapsed-day count. The
overall weight for identifier *i* is now:

```text
sum(weight_i,t * observed_days_t) / sum(observed_days_t)
```

The denominator is calculated from one row per accepted source period. Days in a
calendar gap are therefore not invented as zero-weight observations. The overall
date range still reports the earliest and latest accepted dates, while
`quantity_of_days` represents the accepted observed coverage used in the weighting
calculation.

Every `df_overall()` calculation verifies, with the unchanged eight-decimal weight
criterion, that its overall identifier weights sum to 1.0.

## Linked overall contributions

Simple period contributions cannot be added across time when returns compound.
`Performance.df_overall()` now multiplies every identifier-period contribution by
the same established logarithmic linking coefficient used by the analytics path.
The resulting identifier contributions sum to the geometrically linked total return.

The implementation was independently cross-checked in tests using
`log1p(period_return) / period_return`, normalized by the corresponding coefficient
for the overall linked return. The established zero-return branch remains supported.
Every overall calculation verifies contribution footing at the unchanged
11-decimal criterion.

## Zero-net mapped signed groups

When long and short constituents map to one group, their weights can sum to exactly
zero while their contributions do not. No finite group return can satisfy

```text
group_contribution = group_weight * group_return
```

Phase 4 therefore preserves the mapped contribution and stores a null group return
internally and in existing outputs. Exactly zero weight with exactly zero
contribution retains a defined zero return. A nonzero near-zero weight remains
mathematically defined and is not converted to the zero-net case; no tolerance was
introduced or changed.

For every group, the simple total Brinson-Fachler effect is calculated directly as:

```text
portfolio_contribution
- benchmark_contribution
- (portfolio_weight - benchmark_weight) * benchmark_period_return
```

If the benchmark group return is defined, allocation uses the standard
Brinson-Fachler formula and selection is the residual needed to equal total effect.
If the benchmark group return is undefined, allocation is zero and selection equals
total effect. Active-period linking is then applied to total and allocation, and the
smoothed selection effect remains their residual. The existing contribution and
attribution footing audits remain enabled.

## Direct classification validation

`Attribution` now rejects a nonempty requested classification unless both copied
source performances carry that exact classification name. The error reports the
requested, portfolio, and benchmark names. `Performance.audit_performances()` repeats
the check defensively when attribution is audited.

## Documentation and retained images

`docs/methodology.md` now explains observed-period overall weighting, linked overall
contributions, and the zero-net mapped-group convention. The separate pre-existing
description of an interaction effect remains assigned to the Phase 6 documentation
item; Phase 4 did not broaden into that later phase.

The tracked output gallery was regenerated from the current calculations and source
fingerprint. Its inventory remains the same.

## Complete validation

The complete release-candidate gate passed:

- Tests: 299 passed; 301 subtests passed.
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

- Analytics large-site 500x: warning only; 12,126 to 6,063,000 rows; timing ratio
  1.07x against the unchanged 1.05x warning and 1.10x failure boundaries.
- Analytics selected-workload 10x: pass; 12,126 to 121,260 rows; timing ratio 1.78x
  against the unchanged 2.10x warning and 2.20x failure boundaries.
- Analytics long-history 5x: pass; 12,246 to 61,230 rows; timing ratio 1.02x against
  the unchanged 1.58x warning and 1.65x failure boundaries.

The known long-history harness limitation remains the separately remediable Item 15
in Phase 7. Phase 4 did not change that scenario or any scale threshold.

## Phase 4 conclusion

Phase 4 is complete. Phase 5 can now harden the risk-statistics numerical and
financial domains on top of restored performance and attribution conservation.
