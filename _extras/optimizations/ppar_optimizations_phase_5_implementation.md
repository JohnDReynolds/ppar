# ppar Optimization Roadmap: Phase 5 Implementation

Status: Complete  
Implementation date: September 2, 2026

## Outcome

The required 500x large-site check now separates deterministic correctness and
algorithmic scaling protection from machine-dependent elapsed-time observation.

The release-candidate workflow still creates the full 1x and 500x Axys/APX
workspaces and runs both complete demonstrations. It now runs each demonstration
once and requires every generated report file to be byte-for-byte equal. It prints
the two elapsed times and their ratio for review, but elapsed time alone cannot warn
or fail this scenario.

The selected-workload and long-history timing gates retain their established
workloads and warning and failure thresholds. The 500x check remains part of the core
release-candidate workflow.

This contract was explicitly approved by the user on September 2, 2026, after review
of the former gate, the initially proposed loader ratio, and the simpler deterministic
alternative.

## Deterministic scaling invariants

The Axys/APX tests now verify that a combined portfolio-and-benchmark request:

- creates exactly one lazy CSV scan for portfolio performance and one for security
  performance;
- materializes each of those two source queries exactly once;
- includes both requested account codes in the optimized selection pushed into each
  CSV scan; and
- partitions each selected multi-account source exactly once, as retained from Phase
  4 coverage.

A small private `_collect_performance_source()` boundary makes the two intended
source materializations explicit and inspectable without changing loader behavior.
The source query remains projected, requested-account filtered, and date filtered
before that boundary.

These invariants protect the controllable algorithmic behavior without encoding a
wall-clock expectation tied to one machine, filesystem cache, process schedule, or
dependency version.

## Large-site check simplification

Removed from the 500x large-site scenario:

- the untimed baseline and scaled warmups;
- five paired complete-demo timing samples;
- median paired-ratio calculation;
- the 1.05x warning boundary; and
- the 1.10x failure boundary.

Retained or strengthened:

- deterministic 1x and 500x fixture construction;
- one successful complete demo run for each fixture;
- source-row counts and observed elapsed-time reporting;
- the optional preparation, startup, and calculation diagnostics; and
- output equivalence, strengthened from HTML-only comparison to byte-for-byte
  comparison of every generated report file.

The ordinary 60-second child-process timeout remains a hang and runaway safety limit,
not a performance threshold.

## Validation evidence

The focused scale, Axys pipeline, and release-script selection passed with 58 tests
and 41 subtests. The complete release-candidate workflow then passed with:

- 381 tests and 462 subtests;
- Mypy clean across 40 source files;
- Pyright reporting 0 errors and 0 warnings;
- both Pylint checks clean;
- all 12 retained README images current;
- wheel build and Twine metadata validation passing;
- isolated wheel installation and `pip check` passing; and
- both installed setup demonstrations producing their unchanged ordered bundles of
  11 reports.

The complete release-candidate 500x results were:

```text
PASS Analytics large-site equivalence 500x
  rows: 12,126 -> 6,063,000 (500.00x)
  time (observation only): 1.31s -> 1.32s (1.009x); no performance threshold
PASS Analytics selected-workload 10x
  time: 0.20s -> 0.38s (1.881x); warning=>2.10x, failure=>2.20x
PASS Analytics long-history 5x
  time: 1.21s -> 1.75s (1.441x); warning=>1.58x, failure=>1.65x
```

An additional diagnostic 500x run passed byte-for-byte artifact equivalence while
reporting calculation-only time of 0.214 seconds for 1x and 0.659 seconds for 500x.
Its complete-demo pair happened to report 1.54 seconds for 1x and 1.38 seconds for
500x, directly illustrating why fixed-work timing was not a reliable source-scaling
release boundary.

No output schema, financial tolerance, selected-workload threshold, long-history
threshold, report content, PyPI state, or GitHub state was changed.

## Prepublication portability follow-up

Two consecutive GitHub release-candidate runs later measured the selected workload at
2.928x and 3.012x, above its 2.20x failure boundary, while all financial results and
the complete 500x bundles remained correct. The same revision repeatedly measured
about 1.87x to 1.89x on the 14-worker development machine.

Focused local reproduction established that the ratio primarily reflected available
Polars workers rather than a product regression:

| Polars workers | Selected-workload ratio |
| ---: | ---: |
| 1 | 5.221x |
| 2 | 3.523x |
| 4 | 2.956x |
| 8 | 2.207x |
| 14 | approximately 1.89x |

Repeated samples did not remove the systematic hardware dependency. With explicit
user approval, selected-workload timing therefore became observation-only. Its 10x
row-growth assertion, security-result growth, sector and risk equivalence checks, and
all deterministic source-loading invariants remain release requirements. The
long-history warning and failure thresholds remain unchanged.
