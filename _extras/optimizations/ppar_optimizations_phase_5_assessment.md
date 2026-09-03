# ppar Optimization Roadmap: Phase 5 Assessment

Status: Superseded by the approved simpler implementation  
Assessment date: September 2, 2026

The three-load timing contract evaluated below was not implemented. After reviewing
the assessment, the user approved a simpler contract: retain the required 500x
end-to-end correctness run, protect algorithmic scaling with deterministic source
query invariants, and report wall-clock timing without a warning or failure boundary.
The decision and validation evidence are recorded in
[`ppar_optimizations_phase_5_implementation.md`](ppar_optimizations_phase_5_implementation.md).

## Outcome

The current large-site timing gate should be replaced with a source-loading gate that
times the Axys/APX operation whose work actually grows when many unrequested accounts
are added. Complete report generation, financial equivalence, and HTML equivalence
should remain required, but should be checked independently of the source-loading
timing ratio.

No gate, threshold, sample count, workload, test, or production source was changed
during this assessment.

## Why the current gate is unstable

The current gate times an entire 11-report demonstration for a normal two-account
source and for the same requested accounts embedded in 500 account copies. That one
number combines:

- Python and library startup;
- Axys/APX CSV loading and requested-account filtering;
- reconciliation and financial calculations;
- HTML and PNG rendering; and
- atomic report publication.

Only the CSV scan grows with the 500x source. The other work is predominantly fixed.
Phase 2 made fixed chart work faster without making the scaled CSV scan slower. That
reduced absolute execution time while increasing the scaled-to-baseline ratio's
sensitivity to ordinary variation in unrelated fixed work.

Before the completed optimizations, the approved Phase 8 evidence measured complete
baseline demonstrations at approximately 1.30--1.43 seconds and scaled demonstrations
at approximately 1.43--1.55 seconds. Recent Phase 3 and Phase 4 observations crossed
the unchanged 1.10x failure boundary at 1.105x--1.108x. Three fresh five-pair batches
during this assessment produced:

| Batch | Baseline median | 500x median | Median paired ratio |
| ---: | ---: | ---: | ---: |
| 1 | 1.166 seconds | 1.287 seconds | 1.100x |
| 2 | 1.204 seconds | 1.312 seconds | 1.084x |
| 3 | 1.179 seconds | 1.300 seconds | 1.102x |

The absolute demonstrations are faster, but otherwise equivalent observations can
pass or fail the narrow end-to-end ratio according to chart, startup, and process
scheduling variation. Raising the existing 1.10x boundary would make that mixed
measurement less noisy, but would not make it more interpretable.

## Earlier proposed timing contract (not implemented)

Retain the existing 1x and 500x deterministic workspaces and the same two requested
portfolio codes. Replace only the large-site timing portion with this contract:

1. Run the complete baseline and scaled demonstrations once, outside the timed
   source-loading samples.
2. Require every file in their complete report bundles to remain byte-for-byte equal.
3. Load both requested portfolios from each workspace and require identical portfolio
   keys, display names, and reconciled security-performance frames.
4. Warm the baseline and scaled loader workloads once.
5. Collect five paired baseline-then-scaled samples.
6. Within each sample, time three consecutive operations. Each operation constructs a
   fresh `AxysData` instance and calls `get_portfolios()` for the portfolio and
   benchmark. Repeating the complete loader operation three times makes the median
   ratio substantially more stable without introducing product caching.
7. Apply the boundary to the median of the five paired 500x-to-1x ratios.

Proposed boundaries:

- warning above **5.50x**;
- failure above **5.75x**.

The selected-workload and long-history gates, including their workloads, sample
policies, and thresholds, would remain unchanged.

## Boundary evidence

Ten independent current-implementation batches used the proposed warmup, three-load
sample, and five-pair median policy. Their median ratios were:

```text
5.393x, 5.436x, 5.382x, 5.312x, 5.415x,
5.392x, 5.352x, 5.315x, 5.368x, 5.237x
```

The median across all individual pairs was 5.359x. Batch medians ranged from 5.237x
to 5.436x. The proposed warning boundary is above every current batch median; the
failure boundary provides 5.8% headroom over the highest observed current batch.

To test sensitivity to genuine extra source work, the loader was temporarily patched
in memory after its normal operation. No repository file was changed.

One redundant full pass over each source CSV produced five batch medians of:

```text
5.786x, 5.819x, 5.740x, 5.847x, 5.761x
```

Every batch would warn and four of five would fail. Two redundant full passes produced
three batch medians of 6.171x, 6.201x, and 6.149x; every batch would fail. This is the
regression class the large-site fixture is intended to expose: additional work that
scales with all source rows even though only two accounts are requested.

The proposed loader timing takes roughly 2.5 seconds after fixture preparation on the
assessment machine, compared with roughly 13 seconds for twelve complete demo
processes under the current warmup-and-five-pair policy. Complete baseline and scaled
reports would still be produced once each and compared byte-for-byte, so the gate
continues to exercise the full user workflow without using chart rendering as the
scaling metric. The current baseline and 500x bundles were byte-for-byte equal across
all 11 files during this assessment.

## Tradeoffs

Benefits:

- The measured ratio directly represents Axys/APX source loading, filtering,
  reconciliation, and bulk-account selection.
- Faster or slower chart rendering cannot make an unchanged CSV scan spuriously cross
  the large-site threshold.
- The gate detects redundant full-source work and is faster to execute.
- It strengthens end-to-end equivalence from HTML-only comparison to byte-for-byte
  comparison of every report file, while separately checking reconciled financial
  source frames.

Costs:

- This specific ratio no longer detects fixed-cost regressions in Python startup,
  chart rendering, or publication.
- Three operations per timed sample make the number a workload-specific ratio rather
  than a direct statement of one user invocation's elapsed time.
- The numerical boundaries are not comparable with the old 1.05x and 1.10x values
  because the timed workload changes.

Those fixed-cost stages remain exercised by the complete demonstrations, routine
tests, image checks, the selected-workload and long-history scenarios, and the
observation-only optimization benchmark. The proposed boundary is intentionally
limited to the source-size regression that the 500x fixture uniquely represents.

## Superseding decision

The user did not select either timed contract below:

- current: complete-demo timing, one warmup per side, five paired samples, warning
  above 1.05x, failure above 1.10x;
- proposed: three-operation fresh-loader timing, one warmup per side, five paired
  samples, warning above 5.50x, failure above 5.75x, with complete report-bundle and
  reconciled-financial-data equivalence retained outside timing.

Instead, the approved implementation keeps the full 500x workflow and complete bundle
equivalence, adds deterministic source-query invariants, and makes large-site timing
informational. This removes machine-specific elapsed boundaries rather than replacing
one calibrated ratio with another.
