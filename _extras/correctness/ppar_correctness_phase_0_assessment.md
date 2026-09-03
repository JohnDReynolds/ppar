# ppar Correctness Roadmap: Phase 0 Assessment

Status: Complete  
Assessment date: August 31, 2026  
Production code changed: No  
Tests changed: No

## Outcome

The seven correctness contracts in Phase 0 are accepted with the qualifications
recorded below. They are sufficiently precise to guide regression tests and fixes
without changing output columns or weakening a financial invariant.

The unchanged release-candidate gate passes at the starting revision. This establishes
that the reviewed defects are gaps in edge-case coverage rather than failures already
detected by the current gate.

## Baseline identity

- Git revision: `718f5054dc34cb88490cc92ffffa825e8448abdc`
- Python: `3.12.1`
- Package version: `0.2.0`
- Constraints file: `constraints/ci.txt`
- Constraints SHA-256:
  `bc3a4116477347a9b23334be3b6f08e66ca140c1ff7c2225ca279e17524b29a4`
- Tracked worktree state after validation: clean
- Baseline command: `./.venv/bin/python scripts/check_release_candidate.py`

## Confirmed behavioral contracts

### Contract 1: Comparable returns require equal actual coverage

Decision: Accepted, with separate native-frequency and fixed-frequency rules.

For `Frequency.AS_OFTEN_AS_POSSIBLE`:

- Portfolio and benchmark rows may be compared only when the complete inclusive
  `(from_date, thru_date)` pair matches.
- Leading or trailing observations outside the maximal common comparison window may
  be trimmed. This preserves the documented behavior of restricting analysis to
  common history.
- Once the common comparison window begins, a period present on only one side is an
  interior mismatch and must raise `PparError`. It must not be folded into an earlier
  or later period.
- Common from dates and common thru dates must not be computed independently and then
  paired into intervals that did not exist in both sources.

For monthly, quarterly, and yearly output:

- Portfolio and benchmark may use different source granularity, such as daily versus
  monthly rows, but the rows consolidated into a reporting bucket must form the same
  complete, gapless inclusive coverage on both sides.
- Every source row must be wholly contained in exactly one reporting bucket.
- Source coverage must be audited before reporting dates are synthesized or replaced.
- A source interval spanning more than the requested reporting bucket cannot be
  treated as one observation at that frequency.

The established incomplete-endpoint behavior remains in scope:

- A jointly incomplete terminal bucket may be omitted when neither side publishes it
  as complete.
- Asymmetric terminal coverage remains an error.
- Existing explicitly warned truncation for an incomplete interior frequency endpoint
  is not broadened by this roadmap. It must never relabel an incomplete interval as a
  complete one.

### Contract 2: Axys/APX portfolio and security periods must be complete

Decision: Accepted.

After applying the requested portfolio code and date window, the period-key sets in
`portperf` and `secperf` must be equal for that portfolio. A mismatch at the beginning,
middle, or end of the selected window is an error with portfolio and date context.

The Axys/APX adapter must not inner-join away unmatched source periods. Core analytics
may still trim equivalent leading or trailing history when comparing a portfolio with
its benchmark, but each individual Axys/APX portfolio must first be internally
complete.

The current test that requires unmatched Axys/APX periods to be removed will need to
be replaced by a stricter regression test. This changes an unsafe behavior; it does
not relax a gate or tolerance.

### Contract 3: Codes and identifiers are strings

Decision: Accepted.

Portfolio codes, security identifiers, and classification codes must be parsed and
compared as strings before CSV type inference can interpret them as numbers. Leading
zeroes and other meaningful string characters must survive the complete ingestion and
reporting path.

Existing validation of null, blank, padded, and ambiguous identity values remains in
force. Preserving `001` does not mean accepting whitespace-corrupted identifiers.

### Contract 4: Nonfinite source values are invalid, not missing

Decision: Accepted with a distinction between null evidence and nonfinite values.

- Portfolio returns and security returns are required finite numbers.
- Generic performance weights and returns remain required finite numbers.
- `NaN`, positive infinity, and negative infinity are always invalid. They must never
  be converted to zero, equal participation, or another fallback.
- An Axys/APX weight or contribution may be null only as explicitly missing evidence
  governed by Contract 5. A null is not interchangeable with `NaN` or infinity.
- Validation should occur at the ingestion boundary and be repeated defensively at
  reconciliation boundaries that can be called directly.
- Errors must identify the source, field, portfolio, and period when available.

### Contract 5: Axys/APX reconciliation must be evidence-based

Decision: Accepted. The safety contract is fixed; the exact numerical optimizer is a
Phase 3 implementation design.

- The purpose of the adapter remains to reconcile security-level performance to the
  corresponding `portperf` return.
- When finite contribution and nonzero security return imply a weight, that remains
  the preferred source anchor. A finite reported weight is the fallback where an
  implied weight cannot be calculated.
- If the source-derived weights already sum to one and reproduce the portfolio return,
  they must be preserved, including valid negative weights.
- The adapter must not impose a long-only model on signed source evidence. The core
  performance model already supports weights that sum to one while including shorts.
- Equal participation is not an acceptable substitute for missing evidence.
- A missing row-level anchor may be inferred only when the remaining valid anchors,
  the weight-sum equation, and the portfolio-return equation determine it uniquely.
  Otherwise reconciliation must fail as underdetermined.
- Contradictory or infeasible evidence must fail rather than produce the closest
  plausible report silently.
- If adjustment from valid anchors is necessary, Phase 3 must document and test one
  deterministic objective that preserves signed weights and minimizes departure from
  the evidence. Input order cannot influence the solution.

The current equal-weight fallback test and the current nonnegative-only solver contract
conflict with this decision and will need test-first replacement in Phase 3.

### Contract 6: Overall weights average over observed coverage

Decision: Accepted.

Irregular native-frequency history is valid when its periods are nonoverlapping and
otherwise pass validation. Its overall weights should be day-weighted over the union
of accepted observed periods, not over unobserved calendar gaps between the first and
last dates.

The denominator should therefore be the sum of the unique accepted period-day counts.
Because each accepted period's weights sum to one, the overall portfolio and benchmark
weights must each sum to one as well. A new overall-weight conservation audit should
enforce this result.

Fixed-frequency gaps remain governed by Contracts 1 and 2 and cannot be hidden by this
normalization rule.

### Contract 7: Zero-net mapped groups retain contribution without a fake return

Decision: Accepted with an explicit undefined-return convention.

- A mapped group whose signed constituents produce zero net weight and nonzero
  contribution is valid.
- Its aggregated weight and contribution must be preserved.
- Its group return is mathematically undefined and should be represented as null in
  the existing return column, not fabricated as zero or another finite value.
- Active contribution and total Brinson-Fachler effect should be calculated directly
  from contributions and active weight, so the total remains numeric and reconciles
  to active return without division by zero.
- Where the benchmark group return is defined, allocation keeps its established
  Brinson-Fachler formula and selection is the reconciling residual.
- Where the benchmark group return is also undefined, the allocation/selection split
  has no unique economic interpretation. The recommended explicit convention is zero
  allocation and the complete group total effect in selection. Phase 4 must document
  that convention and test it independently.
- No output column may be added. Tables, charts, and CSV output must handle the null
  return without dropping the group's valid contribution or effect.

## Existing tests whose asserted behavior must change

The following tests intentionally encode behavior that conflicts with the confirmed
contracts. They should be replaced or narrowed only when their corresponding phase is
implemented:

- `test_filter_to_common_periods_removes_unmatched_periods`: replace silent Axys/APX
  intersection with a contextual mismatch error.
- `test_invalid_anchors_fall_back_to_equal_weights`: replace arbitrary equal weights
  with insufficient-evidence validation.
- `test_all_period_reconciliation_preserves_duplicate_identifier_rows`: resolve the
  adapter contract so duplicate rows are either financially aggregated under a proven
  rule or rejected before `Analytics` receives them.

The following behavior remains valid and should stay covered:

- `test_date_alignment_keeps_only_common_periods`: retain trimming of non-common
  leading and trailing history, while adding separate interior-mismatch tests.
- Symmetric incomplete terminal fixed-frequency data may remain omitted rather than
  reported as complete.
- Existing fatal and ordinary reconciliation tolerances remain unchanged.

## Public output schema baseline

The generic and Axys/APX demonstrations produced identical schemas. Security and
classification attribution also used the same schema for each view.

### Performance data

The demonstration performance frames, which do not include the optional input `name`
column, currently expose this narrow and overall schema:

```text
from_date
thru_date
Quantity_Of_Days
Total_Return
identifier
return
weight
contribution
```

### `View.CUMULATIVE_ATTRIBUTION`

```text
from_date
thru_date
Portfolio_Return
Benchmark_Return
Active_Return
Cumulative_Portfolio_Return
Cumulative_Benchmark_Return
Cumulative_Active_Return
Portfolio_Contribution_Smoothed
Benchmark_Contribution_Smoothed
Active_Contribution_Smoothed
Cumulative_Portfolio_Contribution
Cumulative_Benchmark_Contribution
Cumulative_Active_Contribution
Allocation_Effect_Smoothed
Selection_Effect_Smoothed
Total_Effect_Smoothed
Cumulative_Allocation_Effect
Cumulative_Selection_Effect
Cumulative_Total_Effect
```

### `View.OVERALL_ATTRIBUTION`

```text
Classification_Identifier
Classification_Name
Portfolio_Weight
Portfolio_Return
Portfolio_Contribution_Smoothed
Benchmark_Weight
Benchmark_Return
Benchmark_Contribution_Smoothed
Active_Weight
Active_Return
Active_Contribution_Smoothed
Allocation_Effect_Smoothed
Selection_Effect_Smoothed
Total_Effect_Smoothed
```

### `View.SUBPERIOD_ATTRIBUTION`

```text
from_date
thru_date
Classification_Identifier
Classification_Name
Portfolio_Weight
Portfolio_Return
Portfolio_Contribution_Simple
Benchmark_Weight
Benchmark_Return
Benchmark_Contribution_Simple
Active_Weight
Active_Return
Active_Contribution_Simple
Allocation_Effect_Simple
Selection_Effect_Simple
Total_Effect_Simple
```

### `View.SUBPERIOD_SUMMARY`

```text
from_date
thru_date
Portfolio_Return
Benchmark_Return
Active_Return
Portfolio_Contribution_Simple
Benchmark_Contribution_Simple
Active_Contribution_Simple
Allocation_Effect_Simple
Selection_Effect_Simple
Total_Effect_Simple
```

### Risk statistics

```text
column
Portfolio
Benchmark
Difference
Category
```

### Standard demonstration artifact inventory

Both installed workflows produced exactly these 11 files:

```text
security_overall_attribution.html
classification_cumulative_attribution.html
classification_overall_attribution.html
classification_overall_contribution.png
classification_overall_attribution.png
classification_subperiod_attribution.png
classification_heatmap_active_contribution.png
classification_heatmap_attribution.png
classification_cumulative_attribution.png
classification_cumulative_return.png
risk_statistics.html
```

Later phases may correct values, nullability, validation, or error behavior, but must
not add, remove, or reorder public output columns without separate approval. The
standard artifact inventory should also remain unchanged unless a later finding
specifically requires otherwise.

## Baseline validation result

The unchanged release-candidate command passed in full.

### Routine product gate

- Tests: 254 passed; 73 subtests passed.
- Mypy: no issues in 37 source files.
- Pyright: 0 errors, 0 warnings, 0 information messages.
- Pylint error checks: passed.
- Active-documentation, local-link, terminology, and demonstration-reference checks:
  passed.
- README image drift and image validation: passed.
- Wheel: `ppar-0.2.0-py3-none-any.whl`, direct universal wheel, passed Twine check.
- Installed-wheel isolation and `pip check`: passed.
- Installed generic demonstration: passed and wrote 11 artifacts.
- Installed Axys/APX demonstration: passed and wrote 11 artifacts.

### Required scale gate

- Analytics large-site 500x: PASS; 12,126 to 6,063,000 rows; displayed time ratio
  1.05x against the unchanged 1.10x failure boundary.
- Analytics selected-workload 10x: PASS; 12,126 to 121,260 rows; displayed time ratio
  2.01x against the unchanged 2.20x failure boundary.
- Analytics long-history 5x: PASS; 12,246 to 61,230 rows; displayed time ratio 1.03x
  against the unchanged 1.65x failure boundary.

## Phase 0 conclusion

Phase 0 is complete. No production implementation or test change was made. Phase 1
can proceed test-first with nonfinite Axys/APX input validation, string-preserving
identity loading, in-memory date normalization, and deterministic display-name
selection.
