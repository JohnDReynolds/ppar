# ppar Correctness Roadmap: Phase 3 Implementation

Status: Complete  
Implementation date: August 31, 2026  
Starting revision: `718f5054dc34cb88490cc92ffffa825e8448abdc`

## Outcome

Phase 3 makes Axys/APX security-weight reconciliation depend on source evidence
instead of long-only and equal-participation assumptions:

- finite contribution divided by a nonzero security return remains the preferred
  row-level weight anchor;
- a finite reported weight is the fallback when no implied weight is available;
- exact signed anchors, including shorts, zero weights, and leveraged long/short
  portfolios, are preserved;
- one or two missing anchors are inferred only when the weight-sum and
  portfolio-return equations determine every missing value uniquely;
- underdetermined, contradictory, nonfinite, and infeasible evidence raises a
  contextual error instead of inventing weights;
- complete imperfect anchors use one deterministic minimum-departure objective;
- aggregate reconciliation independently geometrically links every target period and
  every achieved period, so signed simple-return residuals cannot cancel; and
- duplicate security identifiers within an account and source period are rejected at
  the adapter boundary because no generally valid lot-aggregation rule is available.

No financial tolerance, release threshold, public output column, or standard report
artifact was added, removed, or relaxed.

## Test-first evidence

The focused regression tests were changed before the solver implementation. They
failed against the Phase 2 code in the expected areas:

- all-null evidence still produced an arbitrary exact-return solution;
- negative implied weights were discarded;
- missing rows were replaced by equal-participation anchors;
- zero-return/nonzero-contribution contradictions were accepted;
- duplicate account/period/security rows passed through reconciliation;
- aggregate target and achieved returns were compared by signed simple-return sums;
  and
- randomized exact signed portfolios did not preserve their source weights.

The final focused tests cover exact implied and reported signed weights, zero weights,
leveraged portfolios, one- and two-row unique inference, three-row and equal-return
underdetermination, contradictory evidence, targets outside the supported feasible
range, input-order independence, duplicate-row context, opposing and same-sign
period residuals, benign floating-point noise, and 200 deterministic randomized
conservation cases.

## Selected weight-adjustment policy

When all anchors are present but do not already satisfy both reconciliation
equations, Phase 3 solves the strictly convex objective

```text
minimize  sum((derived_weight_i - anchor_weight_i) ** 2)
subject to
          sum(derived_weight_i) = 1
          sum(derived_weight_i * security_return_i) = portfolio_return
```

The objective also retains the direction supported by each source anchor:

- a positive anchor may remain positive or become zero;
- a negative anchor may remain negative or become zero; and
- a zero anchor remains zero.

The solver therefore supports signed portfolios without creating a short from a
positive anchor or a long from a negative anchor. A target that cannot be reached
under those constraints is rejected. The active-set solution is deterministic and
the strictly convex objective gives the same result regardless of input row order.

This adjustment policy applies only to complete evidence. It is not used to make an
underdetermined missing-evidence system appear solvable.

## Missing and contradictory evidence

The two financial equations can uniquely determine at most two missing weights:

- one missing weight is fixed by the sum equation and must also satisfy the return
  equation;
- two missing weights are solved from both equations when their security returns are
  distinguishable; and
- more than two missing weights, or two missing rows with indistinguishable returns,
  are underdetermined and fail.

A nonzero contribution paired with a zero security return is explicitly
contradictory. A unique inferred solution that does not satisfy both equations also
fails. Solver failures are wrapped in `PparError` with the portfolio code and source
period when reconciliation is entered through `AxysData`.

## Aggregate reconciliation

Every period now contributes to the aggregate comparison, including periods whose
target and achieved returns are exactly equal. The calculation compares

```text
product(1 + target_return_i)
```

with

```text
product(1 + achieved_return_i)
```

rather than subtracting signed sums of simple returns. Period residuals above the
unchanged ordinary tolerance remain available separately in contextual error output.
The established ordinary tolerance of `0.0000001` and fatal tolerance of `0.0001`
remain unchanged.

## Duplicate-row boundary

`secperf.csv` rows must now be unique by portfolio code, from date, thru date, and
security identifier. A duplicate key is rejected before weight solving and before
the narrower `Performance` model receives the rows. The error includes sample
portfolio, period, identifier, and row-count evidence.

Automatic aggregation was intentionally not implemented. Without source-specific lot
semantics, adding contributions while selecting or compounding returns and weights
would be an unsupported financial policy.

## Documentation

The active configuration guide and the README generated by `ppar setup --axys-apx`
now describe signed-weight support, unique missing-weight inference, failure for
unsupported evidence, and the duplicate-row constraint. Documentation images were
regenerated to carry the current source fingerprint; their report inventory remains
unchanged.

## Complete validation

The complete release-candidate gate passed:

- Tests: 288 passed; 299 subtests passed.
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
  1.09x against the unchanged 1.05x warning and 1.10x failure boundaries.
- Analytics selected-workload 10x: pass; 12,126 to 121,260 rows; timing ratio 1.77x
  against the unchanged 2.10x warning and 2.20x failure boundaries.
- Analytics long-history 5x: pass; 12,246 to 61,230 rows; timing ratio 0.99x against
  the unchanged 1.58x warning and 1.65x failure boundaries.

The known long-history harness limitation remains the separately remediable Item 15
in Phase 7. Phase 3 did not change that scenario or any scale threshold.

## Phase 3 conclusion

Phase 3 is complete. Phase 4 can now address gapped-history overall weights,
zero-net mapped groups, contribution footing, and the remaining lower-impact
aggregation checks on top of explicit Axys/APX source-evidence contracts.
