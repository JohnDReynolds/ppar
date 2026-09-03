# ppar Optimization Roadmap

Status: Complete; all implementation phases and the Phase 5 validation follow-up are
complete  
Assessment date: September 1, 2026
Reassessment date: September 2, 2026

Phase 0 benchmark implementation and baseline evidence are recorded in
[`ppar_optimizations_phase_0_implementation.md`](ppar_optimizations_phase_0_implementation.md).
Phase 1 implementation and validation evidence are recorded in
[`ppar_optimizations_phase_1_implementation.md`](ppar_optimizations_phase_1_implementation.md).
Phase 2 implementation and validation evidence are recorded in
[`ppar_optimizations_phase_2_implementation.md`](ppar_optimizations_phase_2_implementation.md).
Phase 3 implementation and validation evidence are recorded in
[`ppar_optimizations_phase_3_implementation.md`](ppar_optimizations_phase_3_implementation.md).
Phase 4 implementation and validation evidence are recorded in
[`ppar_optimizations_phase_4_implementation.md`](ppar_optimizations_phase_4_implementation.md).
Phase 5 assessment evidence and the earlier unimplemented timed alternative are
recorded in
[`ppar_optimizations_phase_5_assessment.md`](ppar_optimizations_phase_5_assessment.md).
The approved simpler Phase 5 contract and validation evidence are recorded in
[`ppar_optimizations_phase_5_implementation.md`](ppar_optimizations_phase_5_implementation.md).

Cross-roadmap note: Cleanup Phase 9 set `MPLBACKEND=Agg` in CI for deterministic
headless validation. Optimization Phase 2 now supplies the same default in ordinary
ppar chart processes while preserving explicit caller choices.

## Objective

Reduce ppar's elapsed execution time through a small number of high-value,
low-complexity changes. The work should preserve the complete selected report bundle,
financial results, public output schemas, image quality, and existing correctness and
release gates.

This roadmap covers four code-level opportunities retained after reassessment:

1. Preserve Matplotlib's cache across runs.
2. Use Matplotlib's non-GUI Agg backend for PNG generation.
3. Skip fixed-frequency consolidation when source and reporting periods already match
   exactly.
4. Partition Axys/APX multi-account data once instead of repeatedly filtering it.

The previously proposed weight-solver fast path remains documented below but is
deferred. Its isolated upside does not justify financially sensitive solver changes
under the requested simple 80/20 scope.

Phase 5 is a validation follow-up, not a fifth code optimization. It was added after
Phases 3 and 4 demonstrated that the large-site ratio gate became sensitive to faster
fixed report-rendering work and does not isolate the CSV source-scan behavior it is
intended to protect.

Selecting fewer reports is deliberately outside this roadmap. Producing fewer PNG
files can greatly shorten a demonstration run, but it reduces the requested output
rather than making ppar's implementation more efficient.

## Codex execution protocol

Before executing any phase, Codex must display this prompt with that phase's
recommendation substituted for the placeholders:

> Recommended Codex setting for Phase `<N>`: GPT-5.6 Sol `<reasoning level>`.
> Please select that setting and confirm before I proceed.

Codex must wait for the user's confirmation before beginning the phase's assessment,
implementation, benchmarks, tests, or other repository work. This requirement applies
before every phase, including consecutive phases performed in the same Codex session.
The user may explicitly choose a higher level.

The recommendations use Medium for routine work and High for difficult cross-cutting
or invariant work. No retained phase in this roadmap currently warrants Extra High
or Ultra.

## Working rules

- Measure each optimization independently against a recorded baseline before combining
  changes.
- Preserve calculated values, report filenames, report ordering, output schemas, and
  supported input behavior.
- Do not reduce chart resolution, remove annotations, omit layout work, or otherwise
  trade report quality for speed.
- Do not weaken an invariant, tolerance, warning threshold, benchmark threshold, or
  release gate to obtain a passing or faster result.
- Add regression tests for every shortcut, including cases in which its preconditions
  are almost—but not completely—satisfied.
- Keep every optimization independently reviewable and reversible.
- Run focused tests after each phase and the complete local test and build sequence at
  the end.
- Run the 500x scale check after Phases 3 and 4, as required for cross-cutting core
  and bulk-loading changes.

## Profiling baseline

The original exploratory measurements were collected locally on September 1, 2026.
They motivated the roadmap but were not produced by a repeatable harness:

| Workflow | Observed elapsed time |
| --- | ---: |
| Standard generic 11-report bundle, warm chart cache | 1.285 seconds median |
| Standard generic tables and risk report without PNG charts | 0.243 seconds median |
| Genuine 25-year, 99-quarter complete bundle | 1.978 seconds median |
| Standard analytics construction and two attribution objects | 0.072 seconds |
| Long-history analytics construction and two attribution objects | 0.179 seconds |
| Standard Axys/APX analytics construction | approximately 0.14–0.16 seconds |
| Standard bundle with a newly created temporary Matplotlib cache | 10.50 seconds |
| Immediate second bundle using that cache | 1.33 seconds |

The main general observation is that the financial calculation engine is already
fast for the standard workflows. PNG startup and rendering dominate normal report
bundle execution. The remaining large opportunities are conditional shortcuts for
already-periodic data and larger Axys/APX workloads.

Phase 0 added `scripts/benchmark_optimizations.py` and reproduced the workload
boundaries with three-sample medians. Fixture preparation was excluded, complete
published bundles were compared byte-for-byte, and financial tables were compared at
the project's established `1e-12` numerical tolerance. The completed informational
harness was retired during the September 2 cleanup reassessment; the measurements
below remain the durable record. These observations are not release gates:

| Repeatable Phase 0 workload | Median elapsed time |
| --- | ---: |
| Empty Python child process | 0.013 seconds |
| Standard generic 11-report bundle, warm process | 1.330 seconds |
| Generic analytics and two attribution objects | 0.070 seconds |
| Generic risk-statistics construction | 0.009 seconds |
| Generic HTML serialization | 0.007 seconds |
| Generic warm rendering of seven PNG charts | 0.606 seconds |
| Generic bundle with an isolated empty Matplotlib cache | 9.731 seconds |
| Generic bundle reusing that isolated cache | 1.390 seconds |
| Standard Axys/APX 11-report bundle, warm process | 1.424 seconds |
| Axys/APX analytics and two attribution objects | 0.113 seconds |
| Genuine 25-year, 99-quarter complete bundle | 2.002 seconds |
| Already-monthly workload, 121,260 rows per source | 0.212 seconds |
| Bulk Axys/APX load, 40 accounts and 242,520 security rows | 0.448 seconds |

## Phase map

| Phase | Change | Applies to | Expected result |
| --- | --- | --- | --- |
| 0 | Establish repeatable baselines | All workflows | Evidence and regression protection |
| 1 | Persistent chart cache | Reports | Avoid about nine seconds on uncached runs |
| 2 | Agg backend | Reports | Approximately 8–15% faster bundles |
| 3 | Skip no-op consolidation | Core analytics | About 46% faster measured workload |
| 4 | Partition accounts once | Axys/APX bulk loading | 10–14% faster at 40 accounts |
| 5 | Resolve large-site scale gate | Release validation | Reliable, interpretable gate |

## Phase 0: Establish repeatable performance baselines

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_optimizations_phase_0_implementation.md`](ppar_optimizations_phase_0_implementation.md)
for the repeatable harness, equivalence contracts, and baseline results.

Before changing production code, create a small benchmark harness that separates:

- Python and chart-library startup;
- analytics construction;
- attribution and risk calculation;
- HTML generation;
- PNG generation;
- Axys/APX source loading and reconciliation; and
- complete demonstration execution.

Record warm-cache and intentionally cold-cache runs separately. Use repeated runs and
report medians so process scheduling and one-time imports do not masquerade as product
changes. Include at least these workloads:

1. The standard generic demonstration.
2. The standard Axys/APX demonstration.
3. The existing genuine 25-year reporting workload.
4. An already-monthly input requested at monthly frequency.
5. A deterministic bulk Axys/APX fixture containing many portfolio codes.

The harness should confirm output equality independently of elapsed time. Performance
results should initially remain informational; any proposal to establish or change a
release threshold should be reviewed separately with its value, evidence, and
tradeoffs.

Acceptance criteria:

- Another local run can reproduce the same workload boundaries and stage timings.
- Cold and warm chart-cache measurements cannot be confused.
- Benchmark preparation time is excluded from the operation being measured.
- The working tree remains unchanged after benchmarks complete.

## Phase 1: Preserve Matplotlib's cache across runs

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: Complete. See
[`ppar_optimizations_phase_1_implementation.md`](ppar_optimizations_phase_1_implementation.md)
for the persistent platform-cache policy, fallback behavior, artifact comparison,
and timing evidence.

The custom ppar cache policy described below was retired during the September 2
cleanup reassessment. Matplotlib now owns its native persistent cache and temporary
fallback directly; ppar retains only the Phase 2 static-backend default. The original
measurements and decision record remain here as historical evidence.

### Current behavior

`src/ppar/charts.py` redirects `MPLCONFIGDIR` and `XDG_CACHE_HOME` to
`ppar_chart_cache` under the operating system's temporary directory. When that
directory is missing, Matplotlib rebuilds its font cache. The measured first run took
10.50 seconds, compared with 1.33 seconds for the immediately repeated run.

Because the cache is temporary, a user can pay this cost again after temporary-file
cleanup, a reboot, or execution in a fresh environment.

### Implementation direction

- Prefer Matplotlib's normal persistent per-user cache behavior.
- If ppar needs an explicit cache location, use an appropriate persistent user cache
  directory rather than the installation directory or operating system temporary
  directory.
- Continue to respect explicit environment settings supplied by the user or execution
  environment.
- Keep any isolated temporary-cache requirement in the test or CI harness rather than
  imposing it during ordinary library import.

### Tests and validation

- Run a demonstration with a clean cache, then run it again in a new Python process.
- Verify the second process reuses the completed cache.
- Verify an explicitly supplied `MPLCONFIGDIR` remains authoritative.
- Confirm imports and chart creation succeed in supported headless environments.
- Compare every standard PNG and report artifact with the established visual and
  calculated-output baselines.

Acceptance criterion: routine later processes do not rebuild the font cache, and the
change produces no report-content or image-quality regression.

## Phase 2: Use Matplotlib's non-GUI Agg backend

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: Complete. See
[`ppar_optimizations_phase_2_implementation.md`](ppar_optimizations_phase_2_implementation.md)
for the backend policy, artifact comparisons, performance results, and validation
evidence.

### Current behavior

ppar returns static PNG bytes, but `src/ppar/charts.py` imports `matplotlib.pyplot`
without first selecting a non-GUI backend. On macOS, Matplotlib consequently performs
native GUI-backend initialization that the report workflow does not use.

Using Agg in the profiling runs reduced the standard complete bundle by approximately
8–15%. A direct comparison of the current standard output bundle and its Agg-rendered
counterpart was byte-for-byte identical.

### Implementation direction

- Select Agg before importing `matplotlib.pyplot` or any module that can initialize a
  backend.
- Prefer a mechanism that does not overwrite an explicit backend selected by the
  caller unless ppar's static-output contract requires otherwise.
- Do not combine this phase with chart-layout or rendering changes, so any output
  difference has one identifiable cause.

### Tests and validation

- Run all chart tests and image-regression tests.
- Generate every `Chart` variant, including ordinary and large heatmaps.
- Verify operation in a process without a graphical display.
- Compare complete generic and Axys/APX demonstration bundles.
- Re-run the standard and long-history performance measurements.

Acceptance criterion: ppar avoids unnecessary GUI initialization, all charts retain
their established appearance, and calculated and tabular outputs remain unchanged.

## Phase 3: Skip consolidation when periods already match exactly

Recommended Codex level: **GPT-5.6 Sol High**

Status: Implementation complete; the financial, artifact, routine-product, and
targeted performance criteria pass. The final 500x gate exposed a large-site
validation issue now assigned to Phase 5. See
[`ppar_optimizations_phase_3_implementation.md`](ppar_optimizations_phase_3_implementation.md)
for complete evidence, including all passing and failing scale samples.

### Current behavior

`Analytics._consolidate_all_subperiods()` consolidates every fixed-frequency
performance stream even when the source periods already exactly equal the requested
reporting periods. The unnecessary path performs joins, grouping, linking, and row
replacement without changing the intended period structure.

For an already-monthly 121,260-row portfolio and benchmark workload, bypassing the
redundant consolidation reduced analytics-plus-attribution time from 100.6
milliseconds to 54.5 milliseconds, approximately 46%. All attribution views, risk
results, and audits matched in the measurement.

### Implementation direction

- Compare each performance stream's ordered, unique `(from_date, thru_date)` pairs
  with the calculated reporting-period pairs.
- Skip consolidation only when the two sequences match exactly.
- Retain the current consolidation path whenever boundaries, ordering, quantity,
  coverage, or frequency differ.
- Avoid a shortcut based only on equal row counts or equal end dates.

### Tests and validation

- Cover monthly-to-monthly and quarterly-to-quarterly exact matches.
- Cover equal period counts with different start dates, end dates, gaps, ordering, and
  partial boundaries; every such case must retain validation or consolidation.
- Cover multiple identifiers and classifications within each period.
- Compare all attribution views, risk statistics, and audit results with the current
  path at established tolerances.
- Run period-alignment, conservation, lineage, and financial metamorphic tests.
- Run both demonstrations, the complete suite, and the 500x scale check.

Acceptance criterion: only a demonstrable no-op consolidation is skipped, and every
calculated result and validation outcome remains equivalent.

## Phase 4: Partition Axys/APX accounts once

Recommended Codex level: **GPT-5.6 Sol High**

Status: Implementation complete. See
[`ppar_optimizations_phase_4_implementation.md`](ppar_optimizations_phase_4_implementation.md)
for test-first evidence, exact output comparisons, time and memory measurements, and
the unresolved unchanged 500x gate.

### Current behavior

`AxysPortfolioLoader.load()` filters the complete portfolio-performance and
security-performance frames separately for every requested account. Work therefore
grows with both source size and the number of requested portfolios.

In an isolated benchmark with 40 accounts and 242,520 security rows, repeated
full-frame filtering took 0.545 seconds. Partitioning both frames once took 0.0054
seconds for the equivalent splitting operation. The standard two-account
portfolio-and-benchmark workflow is already fast and would receive little benefit.

Phase 3 initially identified this work as the likely way to restore reliable
large-site headroom. The unchanged 1.10x gate passed once at 1.092x, then failed at
1.108x and 1.105x. Direct alternating measurements found no Phase 3 calculation
regression.

Phase 4 showed that the initial attribution of the remaining gate issue to repeated
in-memory filtering was too broad. Partitioning improves the intended many-account
workload, but the 500x scenario requests only two accounts and remains dominated by
scanning a large CSV for those accounts. Phase 5 retains this as an explicit
remediable validation issue.

### Implementation direction

- Partition each loaded frame once by the exact portfolio-code identity.
- Build lookups for the requested codes and reuse each partition during portfolio
  construction.
- Preserve input identity strings, including leading zeroes.
- Preserve requested portfolio order, missing-code errors, validation context, and
  existing row ordering where it is part of calculation behavior.
- Avoid retaining unnecessary partitions when the source contains many unrequested
  accounts; measure the memory tradeoff before choosing the final Polars operation.

### Tests and validation

- Cover one code, the normal portfolio/benchmark pair, many codes, repeated requests,
  absent codes, and numeric-looking codes such as `001`.
- Verify results match the existing per-account filtering path.
- Measure both elapsed time and peak memory on the deterministic bulk fixture.
- Confirm no regression for the ordinary two-account workflow.
- Run the Axys/APX pipeline, reconciliation, identity, and demonstration tests.

Acceptance criterion: bulk loading avoids repeated full-frame scans while preserving
all account-selection and financial behavior.

## Phase 5: Resolve the large-site scale gate

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete. See
[`ppar_optimizations_phase_5_implementation.md`](ppar_optimizations_phase_5_implementation.md)
for the approved deterministic contract and validation evidence. The earlier
assessment and unimplemented timed alternative remain in
[`ppar_optimizations_phase_5_assessment.md`](ppar_optimizations_phase_5_assessment.md).

### Finding

The large-site gate compares complete report-bundle execution for a normal two-account
source with the same two requested accounts embedded in a CSV containing 500 account
copies. It therefore combines Python and chart startup, financial calculations,
report rendering, publication, and a scaled CSV scan into one ratio.

Agg made the large fixed-cost portion faster without changing the scaled CSV scan.
The absolute 500x process also became faster, but the scaled-to-baseline ratio moved
across its narrow 1.10x boundary. Phase 4 cannot materially change that scenario
because partitioning applies after the loader has selected only two accounts.

### Approved implementation

- Run one complete 1x demonstration and one complete 500x demonstration.
- Require byte-for-byte equality across every generated report file.
- Print elapsed times and their ratio as observations without a machine-dependent
  warning or failure boundary.
- Deterministically require one lazy scan and one materialization per performance
  source, with requested-account selection pushed into both source queries.
- Retain the Phase 4 one-partition-per-source invariant.
- Retain the selected-workload row-growth and financial-equivalence assertions, but
  report its elapsed-time ratio without a machine-dependent threshold.
- Keep the long-history timed gate unchanged.
- Keep the required 500x check in the release-candidate workflow.

### Validation

- A deliberately slow but equivalent large-site pair remains successful and reports
  its timing.
- Any HTML or PNG artifact difference fails the complete-bundle equivalence check.
- Optimized source-query plans contain both requested account codes before their two
  intended materialization boundaries.
- A deliberately slow but equivalent selected workload remains successful and
  reports its timing.
- The routine product gate and complete release-candidate workflow pass.

Acceptance criterion: complete 500x outputs remain exact, controllable source-loading
complexity and selected-workload results are protected by deterministic assertions,
and machine-dependent timing is visible without making CPU availability a release
failure. The established long-history timing boundary remains intact.

## Deferred: Fast-path a feasible interior weight solution

Status: Deferred after the 80/20 reassessment; not part of the approved implementation
sequence.

### Current behavior

The Axys/APX active-set weight solver searches one- and two-security combinations for
a feasible starting point. That search is quadratic in the number of holdings. In
periods where the existing unconstrained equality solution already satisfies all sign
constraints, the search is unnecessary because that solution is also the constrained
optimum.

Isolated synthetic timings for feasible interior cases were:

| Holdings | Current projection path | Feasible interior solution check |
| ---: | ---: | ---: |
| 50 | 0.0235 seconds | 0.000030 seconds |
| 100 | 0.0854 seconds | 0.000031 seconds |
| 200 | 0.3355 seconds | 0.000037 seconds |
| 500 | 2.2349 seconds | 0.000073 seconds |

The measured solutions matched. The end-to-end benefit depends on how frequently real
Axys/APX exports require adjustment and how often the unconstrained solution is
feasible. The standard demonstration does not exercise this expensive path.

### Implementation direction

- Calculate the existing unconstrained equality solution first.
- Return it early only when every sign, equality, finiteness, and established
  tolerance requirement is satisfied.
- Fall back without modification to the current active-set algorithm whenever any
  precondition fails.
- Keep this phase separate from changes to the objective, constraints, tolerances, or
  infeasibility policy.

### Tests and validation

- Add direct equivalence tests between the fast path and the existing solver for
  feasible interior cases.
- Add randomized property tests spanning long-only, long/short, leveraged, zero-weight,
  boundary, near-boundary, infeasible, and ill-conditioned inputs.
- Confirm weight sum, contribution, achieved return, sign preservation, and the
  minimum-departure objective at existing tolerances.
- Assert that rejected or boundary cases use the established fallback path.
- Run all reconciliation and calculation-invariant tests, both demonstrations, the
  complete suite, package build, and the 500x scale check.

Acceptance criterion: the fast path is mathematically equivalent whenever selected,
the existing solver remains the fallback everywhere else, and no financial tolerance
or invariant changes.

## Deferred or rejected opportunities

The following findings do not currently meet the requested 80/20 standard:

- Removing selected reports: large runtime reduction, but less output rather than a
  faster implementation.
- Replacing Seaborn: approximately 0.17 seconds of potential startup savings, with
  disproportionate visual-regression work.
- Parallel chart rendering: Matplotlib global state and process startup make a simple,
  reliable implementation unlikely.
- Removing `tight_layout()`: faster in experiments, but clipped labels and legends.
- Changing heatmap thresholds, PNG compression, or chart resolution: small gains that
  alter established output or quality.
- Optimizing HTML generation, atomic publication, attribution-view construction, or
  small Polars collections: measured costs are too small to matter materially.
- Caching `Performance.period_totals()`, pre-bucketing long-history validation, or
  deduplicating minor calculations: approximately 4–11% within already-small core
  stages, not substantial end-to-end wins.

## Recommended implementation order

Proceed in phase order. Phases 1 and 2 are broad reporting improvements with little
financial risk. Phase 3 is a narrowly guarded core shortcut. Phase 4 addresses bulk
Axys/APX scalability without changing financial logic. Bulk-account use is expected,
so Phase 4 is retained rather than treated as an optional site-specific improvement.
The solver fast path is not included in this sequence.

After each phase, record the implementation, test results, before-and-after timings,
artifact comparisons, and any observed platform differences in a corresponding
`ppar_optimizations_phase_<N>_implementation.md` file.
