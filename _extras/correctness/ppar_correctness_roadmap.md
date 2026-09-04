# ppar Correctness Roadmap

Status: Complete; Phases 0 through 14 are complete
Original review date: August 31, 2026
Post-cleanup reassessment date: September 1, 2026
Post-`perfattr` reassessment date: September 4, 2026

Phase 0 decisions and baseline evidence are recorded in
[`ppar_correctness_phase_0_assessment.md`](ppar_correctness_phase_0_assessment.md).
Phase 1 implementation and validation evidence are recorded in
[`ppar_correctness_phase_1_implementation.md`](ppar_correctness_phase_1_implementation.md).
Phase 2 implementation and validation evidence are recorded in
[`ppar_correctness_phase_2_implementation.md`](ppar_correctness_phase_2_implementation.md).
Phase 3 implementation and validation evidence are recorded in
[`ppar_correctness_phase_3_implementation.md`](ppar_correctness_phase_3_implementation.md).
Phase 4 implementation and validation evidence are recorded in
[`ppar_correctness_phase_4_implementation.md`](ppar_correctness_phase_4_implementation.md).
Phase 5 implementation and validation evidence are recorded in
[`ppar_correctness_phase_5_implementation.md`](ppar_correctness_phase_5_implementation.md).
Phase 6 implementation and validation evidence are recorded in
[`ppar_correctness_phase_6_implementation.md`](ppar_correctness_phase_6_implementation.md).
Phase 7 implementation and validation evidence are recorded in
[`ppar_correctness_phase_7_implementation.md`](ppar_correctness_phase_7_implementation.md).
Phase 8 implementation and validation evidence are recorded in
[`ppar_correctness_phase_8_implementation.md`](ppar_correctness_phase_8_implementation.md).
Phase 9 implementation and validation evidence are recorded in
[`ppar_correctness_phase_9_implementation.md`](ppar_correctness_phase_9_implementation.md).
Phase 10 implementation and validation evidence are recorded in
[`ppar_correctness_phase_10_implementation.md`](ppar_correctness_phase_10_implementation.md).
Phase 11 implementation and validation evidence are recorded in
[`ppar_correctness_phase_11_implementation.md`](ppar_correctness_phase_11_implementation.md).
Phase 12 implementation and validation evidence are recorded in
[`ppar_correctness_phase_12_implementation.md`](ppar_correctness_phase_12_implementation.md).
Phase 13 implementation and validation evidence are recorded in
[`ppar_correctness_phase_13_implementation.md`](ppar_correctness_phase_13_implementation.md).
Phase 14 implementation and validation evidence are recorded in
[`ppar_correctness_phase_14_implementation.md`](ppar_correctness_phase_14_implementation.md).

## Objective

Add regression tests and fixes for the findings from the original mathematical and
logic review, correct the attribution description in `docs/methodology.md`, and
remediate the additional correctness gaps found after the cleanup roadmap was
completed.

The work should favor explicit failures over plausible but unsupported analytics.
In particular, a report must not be published when portfolio and benchmark returns
cover different dates, an Axys/APX period is silently missing, or source data does
not support the weights used in attribution.

## Codex execution protocol

Before executing any phase, Codex must display this prompt with that phase's
recommendation substituted for the placeholders:

> Recommended Codex setting for Phase `<N>`: GPT-5.6 Sol `<reasoning level>`.
> Please select that setting and confirm before I proceed.

Codex must wait for the user's confirmation before beginning the phase's assessment,
implementation, tests, or other repository work. This requirement applies before
every phase, including consecutive phases performed in the same Codex session. The
user may explicitly choose a higher level.

The recommendations use Medium for routine work, High for difficult cross-cutting
work, and Extra High for exceptionally difficult financial, numerical, or invariant
work with interacting edge cases. No phase in this roadmap currently warrants Ultra.

## Working rules

- Write a focused regression test that demonstrates each defect before changing its
  implementation.
- Do not weaken an existing tolerance, invariant, warning threshold, or release gate
  to make a test pass.
- Do not add columns to an output file.
- Preserve public behavior except where the reviewed behavior is the defect being
  corrected.
- Prefer a contextual `PparError` to silently changing, dropping, or inventing
  financial data.
- Run focused tests after each item, the complete test suite after each phase, and the
  500x scale check after the period-alignment and reconciliation phases and again in
  final validation.
- Keep generated fixtures small and deterministic. Use temporary copies for Axys/APX
  mutation tests.

## Phase map

| Review item | Summary | Phase |
| --- | --- | --- |
| 1 | Native-frequency period assigned outside its reporting boundary | 2 |
| 2 | Fixed-frequency comparison of unequal actual date ranges | 2 |
| 3 | Axys/APX silently drops unmatched interior periods | 2 |
| 4 | Axys/APX solver replaces or invents exposures | 3 |
| 5 | `NaN` Axys/APX portfolio return bypasses reconciliation | 1 |
| 6 | Signed residuals cancel in aggregate reconciliation | 3 |
| 7 | Gapped histories understate overall weights | 4 |
| 8 | Zero-net mapped long/short group cannot be attributed | 4 |
| 9 | Valid low-volatility beta is reported as `NaN` | 5 |
| 10 | NumPy risk inputs underflow or violate the compounding domain | 5 |
| 11 | `Performance.df_overall()` contribution does not foot | 4 |
| 12 | Heatmap merges later classifications with duplicate names | 6 |
| 13 | Numeric-looking Axys/APX identifiers are not preserved | 1 |
| 14 | Lower-impact input, naming, duplicate-row, and classification checks | 1, 3, 4 |
| 15 | Long-history scale gate does not exercise the expanded reporting horizon | 7 |
| Documentation | Methodology describes a separate interaction effect that is not reported | 6 |
| 16 | Vendor-neutral CSV inference corrupts numeric-looking identifiers | 9 |
| 17 | Generic performance and mapping identities accept blank or padded values | 9 |
| 18 | Risk-ratio zero handling is not scale-aware and can reverse Treynor sign | 10 |
| 19 | Zero-net classifications are omitted or misstated in heatmaps | 11 |
| 20 | Axys/APX portfolio display names depend on physical source-row order | 12 |
| 21 | Caller-supplied contribution can override ppar's weight-times-return contract | 14 |
| 22 | Excluded history can determine inferred names or create false conflicts | 14 |
| 23 | Finite periodic returns can overflow to an infinite annualized result | 14 |
| Contract reassessment | Generic surrounding whitespace is normalized consistently | 14 |

## Phase 0: Confirm contracts and establish the baseline

Recommended Codex level: **GPT-5.6 Sol High**

This assessment phase should happen before any production change. Its purpose is to
turn the intended behavior into explicit contracts, especially where the current
implementation encodes an unsafe policy rather than an accidental calculation error.

### Decisions to record

1. Portfolio and benchmark observations must cover the same actual inclusive dates
   before their returns can be compared.
2. Interior gaps or unmatched Axys/APX `portperf` and `secperf` periods should be
   errors. Any intentionally permitted incomplete terminal period must be defined
   separately and tested explicitly.
3. Portfolio codes, security identifiers, and classification codes are identities,
   not numbers; leading zeroes must be preserved.
4. Nonfinite source returns, weights, and contributions should be rejected at the
   ingestion boundary with source and row context.
5. Axys/APX reconciliation must not invent exposures from an underdetermined system.
   Signed weights should either be supported consistently with the core model or
   rejected explicitly before any alteration. The recommended direction is to
   preserve signed weights supported by valid source evidence and reject insufficient
   or contradictory evidence.
6. Overall weights for an accepted irregular history should average over observed
   performance periods and continue to foot to 1.0. If a gap makes that interpretation
   invalid, reject the history instead of publishing weights below 1.0.
7. A zero-net mapped group with nonzero contribution needs an attribution treatment
   that preserves contribution and total-effect reconciliation without fabricating a
   finite group return.

### Baseline evidence

- Run and record the complete unit-test result, static checks, package build, wheel
  smoke test, both generated demonstrations, and the 500x scale check.
- Record the current public output schemas so later phases can verify that no columns
  changed.
- Add no fixes in this phase.

## Phase 1: Strengthen input boundaries and identity handling

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (August 31, 2026)

These checks should precede calculation changes so later phases can assume that dates,
numeric values, and identifiers are valid.

### Item 5: Reject nonfinite Axys/APX portfolio returns

Tests:

- Parameterize `NaN`, positive infinity, and negative infinity for portfolio return.
- Cover nonfinite security return, weight, and contribution values as well.
- Assert a contextual `PparError` identifies the source, field, and affected period.
- Confirm that no `AxysPortfolio` or `Analytics` object is produced.

Fix direction:

- Validate and cast required numeric columns immediately after CSV loading.
- Require finite values where the field is mandatory; distinguish optional missing
  evidence from invalid nonfinite evidence.
- Retain a defensive finiteness check inside reconciliation so callers cannot bypass
  the loader contract.

Acceptance criterion: tolerance comparisons never receive a nonfinite target or
achieved return.

### Item 13: Preserve numeric-looking identifiers

Tests:

- Select portfolio code `001` through the public string API.
- Keep `001` and `1` distinct as portfolio, security, and classification identifiers.
- Cover identifiers containing leading zeroes, large digit strings, and mixed
  alphanumeric values.

Fix direction:

- Apply string schema overrides before CSV inference for every identity column, not
  only composite-security-ID components.
- Validate blank and null identity values after parsing.

Acceptance criterion: identity values round-trip exactly from CSV to analytics.

### Item 14a: Cast in-memory dates before applying bounds

Tests:

- Construct `Performance` from a Polars DataFrame containing ISO date strings and
  explicit `from_date` and `thru_date` bounds.
- Verify behavior matches the equivalent CSV input and a DataFrame already typed as
  `pl.Date`.
- Assert malformed dates raise `PparError`, not a raw Polars exception.

Fix direction: normalize and validate date columns before applying the requested
window.

### Item 14b: Make inferred display names independent of row order

Tests:

- Shuffle otherwise equivalent input rows and assert identical inferred names.
- Cover a name change over time and define whether the chronologically latest name or
  an inconsistency error is the contract.

Recommended fix direction: sort chronologically before selecting a name, while
rejecting conflicting names within the same effective period.

## Phase 2: Make period alignment exact

Recommended Codex level: **GPT-5.6 Sol Extra High**

Status: Complete (August 31, 2026)

This is the highest-priority implementation phase because the current behavior can
publish financially incorrect results while all downstream audits pass.

### Item 1: Bound native-frequency assignments

Tests:

- Reproduce portfolio January/February/March versus benchmark January/March.
- Assert February cannot be folded into the January reporting row.
- Add the symmetric benchmark-extra-period case.
- Cover partial overlaps, gaps, and adjacent periods.

Fix direction:

- Replace or constrain the backward as-of assignment so every source row must fall
  wholly inside exactly one reporting interval.
- Audit that every included source period is assigned once and that no assigned row
  extends beyond its reporting interval.

Acceptance criterion: an unmatched interior period raises a contextual error or is
handled by an explicitly documented intersection policy that cannot relabel or fold
its return into another period. The recommended behavior is an error.

### Item 2: Require equal actual coverage for fixed frequencies

Tests:

- Reproduce January 1-31 portfolio versus January 15-31 benchmark monthly returns.
- Reject a multi-month source observation presented as one monthly observation.
- Cover daily-to-monthly, monthly-to-quarterly, quarterly-to-annual, holiday-adjusted
  endpoints, leap years, and partial first and last buckets.
- Verify every consolidated portfolio and benchmark row has identical source coverage.

Fix direction:

- Validate both start and end coverage for every bucket.
- Do not synthesize matching dates until both sources have proven equal coverage.
- Track the source intervals used by each consolidated bucket long enough to audit the
  mapping before dates are replaced.

Acceptance criterion: no benchmark-relative calculation can be constructed from
returns covering unequal dates.

### Item 3: Require Axys/APX period completeness

Tests:

- Remove one interior `secperf` month while retaining `portperf`; repeat in reverse.
- Cover missing first, last, and interior periods for portfolio and benchmark.
- Assert the quarterly label cannot span an omitted month.
- Preserve the existing rejection of completely disjoint sources.

Fix direction:

- Compare expected `portperf`, available `secperf`, and retained period keys before
  filtering.
- Reject unmatched interior periods with the portfolio code and missing dates in the
  error context.
- If incomplete terminal data is intentionally supported, isolate that rule from the
  general common-period operation and test it separately.

Phase gate: run all tests, demonstrations, and the 500x scale check before proceeding.

## Phase 3: Make Axys/APX weight reconciliation evidence-based

Recommended Codex level: **GPT-5.6 Sol Extra High**

Status: Complete. See
[`ppar_correctness_phase_3_implementation.md`](ppar_correctness_phase_3_implementation.md)
for the selected
minimum-departure objective, test-first evidence, and validation results.

### Item 4a: Handle signed weights without silently replacing them

Tests:

- Reproduce `[1.2, -0.2, 0.0]` and verify the source-supported signed exposures and
  contributions are preserved.
- Cover long-only, long/short, zero-weight, leveraged, and infeasible targets.
- Add randomized conservation checks for weight sum, contribution, and achieved
  return.

Fix direction:

- Separate validation of source evidence from adjustment of imperfect evidence.
- Do not discard a valid negative implied or reported weight merely to make a
  nonnegative solver feasible.
- If a supported portfolio type remains intentionally long-only, reject negative
  evidence explicitly rather than transforming it.

### Item 4b: Reject underdetermined or unsupported weights

Tests:

- Reproduce the all-null weight/contribution example that currently yields
  `[0.4, 0.0, 0.6]`.
- Cover one usable anchor, contradictory anchors, equal security returns, and targets
  outside the feasible return range.
- Assert the same input order cannot influence the outcome.

Fix direction:

- Define the minimum source evidence required to derive weights.
- Reject underdetermined cases instead of defaulting missing anchors to equal
  participation and selecting one arbitrary exact-return solution.
- Retain adjustments only when they are uniquely defined or governed by an explicit,
  documented financial policy.

### Item 6: Use a non-cancelling aggregate reconciliation measure

Tests:

- Reproduce alternating positive and negative residuals whose simple sum is zero.
- Compare linked target and achieved multi-period returns independently.
- Cover same-sign residuals and benign floating-point noise.

Fix direction:

- Base the aggregate financial check on geometrically linked target and achieved
  returns, not signed sums of simple period returns.
- Report per-period residuals separately so cancellation cannot hide them.
- Keep the existing tolerance unchanged unless the user separately approves a
  documented change.

### Item 14c: Resolve duplicate Axys/APX security rows at the adapter boundary

Tests:

- Reproduce duplicate identifier rows for one portfolio period.
- Determine whether the source rows are true duplicates or legitimate lot-level rows.
- Assert either deterministic financial aggregation or an early contextual error; do
  not preserve rows that `Analytics` will reject later.

Recommended fix direction: reject ambiguous duplicates early. Aggregate only if the
source semantics provide a provably correct rule for combining weights, returns, and
contributions.

Phase gate: run all tests, Axys/APX demonstrations, reconciliation property tests, and
the 500x scale check.

## Phase 4: Restore aggregation and attribution invariants

Recommended Codex level: **GPT-5.6 Sol Extra High**

Status: Complete. See
[`ppar_correctness_phase_4_implementation.md`](ppar_correctness_phase_4_implementation.md)
for the selected
observed-period weighting, contribution-linking, zero-net mapped-group conventions,
and validation evidence.

### Item 7: Make overall weights foot for accepted gapped histories

Tests:

- Reproduce January and March observations with no February.
- Assert total portfolio and benchmark overall weights equal 1.0.
- Cover irregular periods of different lengths and continuous histories to prevent a
  regression in ordinary day weighting.

Fix direction:

- Calculate weight coefficients from the accepted observed-period coverage rather
  than the unobserved calendar span.
- Add an explicit overall-weight conservation audit.

### Item 8: Support zero-net mapped groups with nonzero contribution

Tests:

- Map offsetting long and short constituents into one group with differing portfolio
  and benchmark contributions.
- Assert simple and smoothed total effects foot to active return.
- Cover zero weight/zero contribution and near-zero weight cases separately.

Fix direction:

- Choose a representation that carries the group contribution into attribution
  directly without computing an artificial return by division through zero.
- Keep all existing contribution and total-effect audits enabled.
- Do not add an output column; any internal representation must map into the existing
  schema.

### Item 11: Link `Performance.df_overall()` contributions

Tests:

- Reproduce two 10% periods and require the overall contribution to reconcile to the
  21% linked total return for a fully invested single security.
- Cover multiple securities, negative returns, and a zero total return.
- Cross-check against an independent Carino-linking calculation.

Fix direction: use the same established multi-period contribution-linking convention
as the main analytics path rather than summing simple-period contributions.

### Item 14d: Validate the requested direct-attribution classification

Tests:

- Pass matching portfolio and benchmark classifications that differ from the
  requested classification name.
- Assert a contextual error rather than a mislabeled result.
- Preserve successful direct construction when all three names agree.

Fix direction: compare each source classification with the requested common
classification, not merely with the other source.

Phase gate: run all tests and both demonstrations, with explicit conservation checks
for weights, returns, contributions, and attribution effects.

## Phase 5: Harden risk-statistics domains

Recommended Codex level: **GPT-5.6 Sol Extra High**

Status: Complete. See
[`ppar_correctness_phase_5_implementation.md`](ppar_correctness_phase_5_implementation.md)
for the selected
floating-point normalization, scale-aware variance, compounding-domain conventions,
and validation evidence.

### Item 9: Make beta's zero-variance check scale-aware

Tests:

- Reproduce the low-volatility series with exact beta 2.
- Cover genuinely constant benchmarks, ordinary volatility, scaled versions of the
  same returns, and the minimum supported observation count.
- Compare beta with an independent covariance/variance calculation.

Fix direction:

- Treat variance as zero only when it is exactly zero or below a scale-aware numerical
  threshold derived from the input precision.
- Do not use the default absolute tolerance of `np.isclose()` on a squared quantity.

### Item 10a: Normalize or reject integer NumPy return arrays

Tests:

- Reproduce unsigned subtraction underflow and the incorrect information ratio.
- Cover signed integers, unsigned integers, `float32`, and `float64`.
- Assert all accepted arrays produce floating-point arithmetic.

Recommended fix direction: convert accepted real numeric arrays to `float64` at the
public boundary, then validate finiteness and shape.

### Item 10b: Validate the geometric-compounding domain

Tests:

- Reproduce twelve returns of -200%.
- Cover exactly -100%, below -100%, ordinary negative returns, and leveraged-return
  policy boundaries.
- Assert invalid sequences fail before annualized or linked results are calculated.

Fix direction: apply one consistent return-domain rule wherever geometric compounding
or logarithmic linking is required.

Phase gate: run the complete risk suite with independent numerical references, then
the complete project suite.

## Phase 6: Prevent reporting ambiguity and align the methodology

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_correctness_phase_6_implementation.md`](ppar_correctness_phase_6_implementation.md)
for the stable
heatmap identity contract, two-effect methodology correction, and validation results.

### Item 12: Keep duplicate heatmap names distinct

Tests:

- Introduce a second classification identifier with the same display name after the
  first date.
- Assert both series remain present and their values are not merged or discarded.
- Cover duplicates present on the first date and names that change over time.

Fix direction:

- Detect duplicate display names across the entire chart dataset.
- Use stable identifier-based disambiguation before pivoting.
- Replace `aggregate_function="first"` as a safety net for accidental label collisions;
  uniqueness should be proven before the pivot.

### Documentation inconsistency: explain the two-effect attribution model

Tests/checks:

- Add or update a documentation assertion if the project has suitable documentation
  checks.
- Cross-check the wording against the actual formulas and output column names.

Fix direction:

- Change `docs/methodology.md` to state that ppar reports allocation and a
  portfolio-weighted selection effect.
- Explain that this selection term incorporates what a three-effect presentation
  would identify separately as selection and interaction.
- Do not add an interaction output column merely to match the current prose.

Phase gate: run chart tests, documentation checks, and both generated demonstration
report bundles.

## Phase 7: Repair the genuine long-history scale gate

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_correctness_phase_7_implementation.md`](ppar_correctness_phase_7_implementation.md)
for the corrected
history construction, reporting-horizon assertions, profiling, and validation results.

### Item 15: Make the expanded history reach report calculations

Problem:

- The history harness expands the Axys/APX source files from 60 to 300 period keys.
- It attempts to extend the demonstration's `THRU_DATE` by replacing an obsolete,
  annotated source line. The current unannotated assignment does not match, so the
  replacement is silently a no-op.
- Later source periods are therefore loaded but filtered out before analytics and
  report generation. The scenario measures larger input files, not five times the
  reported history its name implies.

Tests:

- Assert that preparing the history workspace changes the executable reporting end
  date to the intended value; a missing source edit must fail explicitly.
- Require 300 consecutive source periods with valid fixed-frequency coverage and no
  gaps, overlaps, or period endpoints invalidated by calendar shifts.
- Assert the calculated output contains the expected fivefold reporting horizon, not
  merely that the input files contain five times as many rows or period keys.
- Cover leap years, weekend-adjusted endpoints, and the configured holiday calendar.
- Retain the existing checks for all 11 nonempty report artifacts.

Fix direction:

- Replace the brittle exact-text substitution with a checked configuration or source
  transformation that cannot silently leave `THRU_DATE` unchanged.
- Generate deterministic, consecutive source periods that satisfy Phase 2's exact
  fixed-frequency coverage contract for the full expanded horizon.
- Profile the genuine long-history run and optimize the implementation and report
  path before considering any threshold change.
- Keep the existing 1.58x warning and 1.65x failure boundaries unchanged during
  implementation. If the corrected workload still cannot meet them, present the
  existing value, measured evidence, proposed value, and tradeoff for explicit user
  approval. Do not relax the gate merely because the corrected scenario fails.

Baseline evidence discovered during Phase 2:

- A corrected exploratory workload containing 25 years of complete monthly source
  data and report output measured 1.87x versus the current 1.65x failure boundary.
- This result is diagnostic, not approval to alter the boundary.

Phase gate: run focused scale-harness tests, the corrected 5x long-history workload,
and the complete unchanged 500x scale workflow before proceeding.

## Phase 8: Integrated regression and release-candidate validation

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_correctness_phase_8_implementation.md`](ppar_correctness_phase_8_implementation.md)
for the integrated
contract audit, malformed-input publication test, and final validation results.

1. Run the complete unit and subtest suite.
2. Run formatting, lint, and type checking without suppressing new failures.
3. Run package build and wheel-install smoke tests in a clean temporary environment.
4. Generate and execute both generic and Axys/APX setup demonstrations.
5. Inspect report filenames, schemas, key totals, and chart series against the
   pre-change public contract.
6. Run the complete release-candidate workflow, including the 500x scale check.
7. Confirm that malformed inputs fail before output publication and that a failed run
   leaves the prior atomic report bundle intact.
8. Record any intentional behavior changes in maintenance and user documentation.

## Post-cleanup reassessment

The September 1, 2026 read-only reassessment reviewed the current working tree after
completion of the cleanup roadmap. The complete suite passed with 339 tests, and
`git diff --check` passed, but focused probes reproduced five remediable gaps not
covered by the suite:

1. A vendor-neutral performance CSV containing identifier `001` loads it as `1`.
   Supplying both `001` and `1` makes the two identities collide and produces a
   duplicate-row error.
2. Low-volatility returns with a mathematically valid Sharpe ratio of approximately
   `2.2360679775` produce `NaN`; multiplying every return by a constant makes the
   same ratio calculate correctly. A representable beta near `-1e-9` and positive
   excess return produces positive infinity instead of a finite negative Treynor
   ratio.
3. A zero-weight mapped group with nonzero portfolio contribution is removed from
   the portfolio-contribution heatmap. A mathematically undefined null active return
   is rendered as zero in the active-return heatmap.
4. Reversing Axys/APX `portperf.csv` rows can change the selected portfolio display
   name because the first surviving name is used without a deterministic name
   policy.
5. Generic performance identifiers and generic mapping identities can be blank or
   whitespace-padded even though the Axys/APX boundary rejects the equivalent input.

The reassessment found no new defect in the Brinson-Fachler equations, final-period
Carino reconciliation, native or fixed-frequency period alignment, observed-period-
day overall weights, Axys/APX evidence-based weight solving, per-period or linked
reconciliation, or the scale-aware beta and correlation variance decision.

## Phase 9: Complete generic identity preservation

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_correctness_phase_9_implementation.md`](ppar_correctness_phase_9_implementation.md)
for the generic CSV identity-preservation contract, shared identity validation, and
validation evidence.

### Item 16: Preserve numeric-looking vendor-neutral CSV identifiers

Problem:

- `Performance` allows Polars to infer the complete CSV schema and casts the
  identifier column to text only after collection.
- Numeric-looking values therefore lose textual identity information before ppar
  validates them. `001` becomes `1`, and distinct `001` and `1` rows collide.
- Phase 1 protected the Axys/APX loaders but did not close the default vendor-neutral
  CSV path, despite the roadmap's broader identity-preservation objective.

Tests:

- Require a single `001` identifier to round-trip unchanged through `Performance`
  and `Analytics`.
- Keep `001` and `1` distinct within the same reporting period.
- Cover a large digit string that cannot be represented exactly as an ordinary
  machine integer and a mixed alphanumeric identifier.
- Exercise both direct CSV loading and the setup-generated vendor-neutral demo
  structure.
- Confirm existing date and finite-number inference remains unchanged.

Fix direction:

- Apply a partial string schema override to the vendor-neutral CSV identifier column
  before Polars inference.
- Do not disable useful inference for date, return, or weight columns.
- Preserve exact source text rather than attempting to reconstruct identifiers after
  collection.

### Item 17: Reject invalid generic identities at the public boundary

Problem:

- Generic `Performance` accepts blank and surrounding-whitespace identifiers.
- Generic mapping inputs accept blank, null, or padded source and destination
  identities. A padded source can be silently treated as unmapped, while a blank
  destination can create a blank classification row.
- The corresponding Axys/APX identity fields already fail early with contextual
  errors.

Tests:

- Parameterize null, empty, whitespace-only, leading-space, and trailing-space
  identifiers for CSV and Polars performance inputs.
- Apply the same cases to both sides of CSV and Polars mapping inputs. Mapping
  destinations are classification identities and must follow the same rule.
- Confirm exact nonblank identifiers, including leading zeroes and intentional
  internal spaces, remain unchanged.
- Require an actionable `PparError` identifying the boundary and offending field.
- Verify malformed mappings cannot silently fall back to self-mapping.

Fix direction:

- Share the existing narrow invalid-identity predicate where it naturally applies,
  without exposing an Axys/APX implementation module through the public API.
- Reject surrounding whitespace rather than trimming it and silently changing the
  identifier.
- Keep display-name policy separate from identity policy unless a focused test proves
  that a display-name rule is also required.

Phase gate: run focused performance, mapping, classification, and data-source tests;
the complete suite; both generated demonstrations; and the unchanged 500x scale
check because identifiers determine aggregation and report lineage.

## Phase 10: Make every risk ratio scale-aware

Recommended Codex level: **GPT-5.6 Sol Extra High**

Status: Complete. See
[`ppar_correctness_phase_10_implementation.md`](ppar_correctness_phase_10_implementation.md)
for the scale-aware ratio-division contract, exact-zero handling, and validation
evidence.

### Item 18: Remove fixed absolute zero tests from risk-ratio division

Problem:

- `_ratio_with_zero_denominator()` uses default `np.isclose()` checks against zero
  for both operands. The default absolute tolerance classifies representable small
  values as mathematical zero.
- Sharpe, Sortino, information, and Treynor ratios can therefore change when the same
  return pattern is multiplied by a constant. Their annualized forms inherit the
  error, and M-squared inherits an invalid Sharpe result.
- Beta itself can be valid and negative but smaller than the fixed absolute cutoff.
  The current helper then returns infinity with the numerator's sign, ignoring the
  negative denominator and reversing the Treynor result.

Tests:

- Reproduce the low-volatility finite Sharpe result with an independent NumPy
  calculation and require invariance across several positive scale factors.
- Cover Sortino and information ratios with representable small denominators and
  independent references.
- Cover a small finite negative beta and require a finite negative Treynor ratio with
  the correct magnitude.
- Distinguish exact or numerically unresolvable zero risk from genuinely small,
  representable risk.
- Preserve the established results for zero numerator over zero denominator, nonzero
  numerator over zero nonnegative risk, nonfinite beta, ordinary volatility, and the
  minimum supported sample.
- Verify annualized ratios and M-squared propagate the corrected periodic result.

Fix direction:

- Remove the fixed absolute `np.isclose(..., 0.0)` decision from the generic division
  helper.
- Determine whether a volatility or tracking-error denominator is unresolvable from
  the scale and floating-point resolution of its source series, as beta and
  correlation already do, rather than from the denominator's absolute magnitude.
- Treat a representable finite beta as a valid signed divisor; do not replace a small
  negative beta with positive infinity.
- Preserve exact financial definitions and do not alter any unrelated tolerance or
  release threshold.

Phase gate: run focused independent-reference and scale-metamorphic risk tests, the
complete risk suite, the complete project suite, both demonstrations, and the
unchanged 500x scale check.

## Phase 11: Preserve zero-net semantics in heatmaps

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_correctness_phase_11_implementation.md`](ppar_correctness_phase_11_implementation.md)
for the measure-aware heatmap filtering, undefined-value masking, and validation
evidence.

### Item 19: Do not drop defined contribution or invent return values

Problem:

- The portfolio-contribution heatmap filters every zero-portfolio-weight row even
  though Phase 4 deliberately permits a zero-net mapped group to retain nonzero
  contribution.
- Heatmap pivot preparation fills every null with `0.0`. A null group return that the
  methodology defines as mathematically undefined is therefore displayed as a real
  zero return.

Tests:

- Build the heatmaps from an actual mapped `Attribution` containing offsetting long
  and short constituents, rather than only a hand-built chart frame.
- Require a zero-weight group with nonzero portfolio contribution to remain visible
  with its complete value.
- Require undefined portfolio and active returns to remain visibly unavailable or
  masked rather than annotated as zero.
- Distinguish an absent date/classification pivot cell from a source row whose value
  is explicitly null.
- Cover ordinary zero values, ordinary missing portfolio holdings, sorting, duplicate
  display names, and both the ordinary and large-heatmap annotation paths.
- Preserve PNG filenames and all tabular output schemas.

Fix direction:

- Apply row filtering according to the selected measure's mathematical availability,
  not portfolio weight alone.
- Preserve a mask for undefined return cells through pivoting and rendering. Fill
  only genuinely absent cells when the attribution model defines their value as zero.
- Do not fabricate a finite group return merely to simplify chart rendering.

Phase gate: run chart, mapped-classification, output-contract, and image-provenance
tests; both demonstration report bundles; and the complete suite.

## Phase 12: Make Axys/APX portfolio names deterministic

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_correctness_phase_12_implementation.md`](ppar_correctness_phase_12_implementation.md)
for the retained-window portfolio-name contract, source validation, and validation
evidence.

### Item 20: Validate and deterministically select portfolio display names

Problem:

- The normalized Axys/APX portfolio-performance source requires a portfolio-name
  column but does not validate that field for null, blank, or surrounding whitespace.
- Reconciliation selects row zero's value after period filtering. Physical source-row
  order can therefore change output titles and report metadata.

Recommended contract:

- Reject null, blank, and whitespace-padded portfolio names.
- Permit a genuine name change across reporting periods and use the chronologically
  latest retained period's name. This matches the generic inferred display-name
  convention and avoids rejecting a legitimate account rename.
- Continue prefixing the selected display name with the exact portfolio code.

Tests:

- Reverse otherwise identical `portperf.csv` rows and require the same portfolio
  name.
- Cover one stable name, a chronological rename, null, blank, padding, multiple
  portfolio codes, and date filtering that excludes the latest source period.
- Require the latest retained period, not the latest unselected source period, to
  determine the name.
- Confirm report titles use the deterministic result and financial output is
  unchanged.

Fix direction:

- Validate portfolio names alongside other normalized textual source fields.
- Sort or aggregate by the validated period key before selecting the latest retained
  name; never rely on physical file order.
- If implementation evidence contradicts the recommended rename contract, stop and
  obtain a user decision rather than silently choosing a different policy.

Phase gate: run Axys/APX loading, validation, output-title, and setup-demonstration
tests; the complete suite; and the unchanged 500x scale check.

## Phase 13: Post-cleanup integrated validation

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_correctness_phase_13_implementation.md`](ppar_correctness_phase_13_implementation.md)
for the final regression audit, atomic-publication identity test, and unchanged
release-candidate results.

1. Confirm every post-cleanup finding has a focused regression test that fails on
   the pre-fix implementation and passes after its phase.
2. Run the complete test and subtest suite, Mypy, Pyright, and the intended Pylint
   checks without suppressing new failures.
3. Run documentation and README-image provenance checks.
4. Build the package and run wheel metadata, isolated-install, and `pip check` smoke
   tests in temporary environments.
5. Generate and execute both installed setup demonstrations and verify their ordered
   11-report bundles, public schemas, titles, and key financial totals.
6. Run the complete unchanged release-candidate workflow, including the 500x scale
   check.
7. Confirm malformed generic and Axys/APX identities fail before atomic publication
   and leave the prior report bundle intact.
8. Record the final behavior, tests, and measurements in phase implementation notes
   and update this roadmap's status without erasing the original completion history.

## Phase 14: Post-`perfattr` boundary correction

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_correctness_phase_14_implementation.md`](ppar_correctness_phase_14_implementation.md)
for pre-fix evidence, the narrow boundary changes, and unchanged release-candidate
results.

This phase reassesses the roadmap after ppar delegated source preparation and
attribution calculation to `perfattr`. The migration remained broadly sound, but it
exposed three host-boundary gaps that could publish internally inconsistent or
nonfinite results.

### Item 21: Preserve ppar's weight-times-return contribution contract

Problem:

- Generic CSV and Polars inputs can contain an optional `contribution` column.
- Passing that column through to `perfattr` makes it authoritative, although ppar's
  established public contract derives simple contribution as `weight * return`.
- A disagreeing column can therefore change subperiod returns, period totals, and
  overall results without failing the existing conservation audits.

Implemented contract:

- Generic input contribution cannot override ppar's calculation. It does not cross
  the raw-input calculation boundary as authoritative financial data.
- Internal calculated contribution remains present after portable preparation; no
  public output column or schema changes.
- Regression coverage exercises both CSV and in-memory Polars inputs and reconciles
  subperiod return, contribution, period totals, and compounded overall return.

### Item 22: Infer names only from retained financial history

Problem:

- Optional display names were selected from all raw rows before requested date
  filtering and portfolio/benchmark alignment.
- An excluded later rename could label an earlier report incorrectly or create a
  false portfolio/benchmark classification conflict.

Implemented contract:

- Keep dated name metadata until portable preparation has selected and aligned the
  accepted history.
- For each retained identifier, choose the chronologically latest name within the
  prepared date interval.
- Excluded leading or trailing history cannot influence report names or conflicts.

### Item 23: Reject nonfinite annualized returns

Problem:

- A finite, very large periodic mean could overflow exponentiation and publish
  positive infinity with only a NumPy runtime warning.

Implemented contract:

- Continue returning undefined output for insufficient history or a deliberately
  undefined (`NaN`) input statistic.
- Reject nonfinite periodic inputs and any exponentiation overflow with a contextual
  `PparError` before report publication.
- Preserve the established greater-than-negative-100-percent compounding domain.

### Phase 9 identity-policy reconciliation

Phase 9 originally recommended rejecting surrounding whitespace for generic
identities. The current documented and tested public boundary instead trims
surrounding whitespace consistently across CSV and Polars inputs while rejecting
null, empty, or whitespace-only values. This normalized policy supersedes the Phase
9 recommendation. Leading zeroes and intentional internal spaces remain preserved,
so identity meaning is not lost. The historical Phase 9 text remains above to avoid
erasing the original decision trail.

Phase gate: run focused normalization and risk-validation tests, the complete suite,
Mypy, Pyright, both Pylint gates, README-image provenance, package and installed-demo
checks, and the unchanged release-candidate workflow including the 500x scale check.

## Completion criteria

- Every numbered review item has a regression test that fails on the original
  implementation and passes with the fix.
- Silent wrong-output cases either produce correct analytics from validated evidence
  or fail with a contextual `PparError`.
- Portfolio and benchmark returns are never compared unless their actual date coverage
  is equal.
- Overall weights, contributions, and attribution effects satisfy their established
  conservation checks.
- Axys/APX identities and source-supported exposures are not silently altered.
- Vendor-neutral identifiers preserve leading zeroes and intentional internal spaces;
  surrounding whitespace is normalized consistently, and blank generic identities
  fail before aggregation or mapping.
- Risk calculations use floating-point inputs and enforce the required numerical and
  financial domains.
- Risk ratios are invariant to a common positive scaling of their numerator and
  denominator inputs whenever the mathematical ratio is defined, and signed finite
  beta is never replaced by an infinity with the wrong sign.
- Heatmaps preserve nonzero zero-net contribution and do not display undefined
  returns as zero.
- Axys/APX portfolio display names are independent of source-row order.
- The methodology describes the implemented two-effect attribution model accurately.
- The long-history scale scenario proves that five times the source history reaches
  calculation and report generation rather than being filtered by the original date
  window.
- All existing gates, including the 500x scale check, pass without relaxation.
- Public output files contain no new columns.
