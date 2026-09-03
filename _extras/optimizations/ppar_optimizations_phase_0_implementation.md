# ppar Optimization Roadmap: Phase 0 Implementation

Status: Complete  
Implementation date: September 1, 2026

## Outcome

Phase 0 establishes a repeatable, informational baseline before production
optimization begins. The retained implementation scope is:

1. preserve Matplotlib's cache across ordinary processes;
2. use the non-GUI Agg backend for static PNG reports;
3. skip fixed-frequency consolidation only when source and reporting period pairs
   match exactly; and
4. partition shared Axys/APX frames once when loading many requested accounts.

Bulk-account usage is expected, so the fourth change remains in scope. The previously
proposed weight-solver fast path is deferred: despite strong isolated synthetic
timings, it changes financially sensitive optimization logic and does not meet the
requested simple 80/20 standard.

No production calculation, report renderer, source loader, output schema, tolerance,
test threshold, warning boundary, or release gate changed in this phase.

## Benchmark harness

`scripts/benchmark_optimizations.py` now provides repeatable measurements using:

```bash
./.venv/bin/python scripts/benchmark_optimizations.py --samples 3
```

A repeated `--scenario` option selects focused workloads. The available scenarios
are `startup`, `generic`, `axys`, `history`, `monthly`, and `bulk`.

The harness:

- creates all workspaces in a temporary directory and excludes fixture preparation
  from timed operations;
- retains and reports each observation and its median;
- measures empty Python startup separately;
- separates analytics/attribution construction, risk-statistics construction, HTML
  serialization, warm PNG rendering, and complete child-process execution;
- measures an intentionally empty isolated Matplotlib cache separately from later
  processes reusing that same cache;
- runs the complete generic and Axys/APX demonstrations and the genuine 25-year
  reporting workload;
- creates an exact-monthly workload containing 121,260 rows in each performance
  source;
- creates a bulk Axys/APX workload containing 40 requested accounts and 242,520
  security-performance rows; and
- verifies repeatability independently of time.

Complete published report bundles are compared byte-for-byte. Financial tables are
compared using the project's established `1e-12` relative and absolute tolerance,
because parallel grouping can produce immaterial binary-order differences below
display precision. This benchmark comparison does not alter any existing test or
release tolerance.

Five focused tests cover argument selection, positive sample counts, observation
retention, output verification, file-only artifact snapshots, and financially neutral
monthly fixture expansion.

## Baseline results

The complete three-sample run produced:

| Workload | Samples | Median |
| --- | --- | ---: |
| Empty Python child process | 0.012s, 0.015s, 0.013s | 0.013s |
| Generic complete warm process | 1.330s, 1.329s, 1.335s | 1.330s |
| Generic analytics and attribution | 0.077s, 0.067s, 0.070s | 0.070s |
| Generic risk-statistics construction | 0.008s, 0.009s, 0.009s | 0.009s |
| Generic HTML serialization | 0.008s, 0.007s, 0.007s | 0.007s |
| Generic warm rendering of seven PNGs | 0.598s, 0.606s, 0.612s | 0.606s |
| Generic isolated cold-cache process | 9.731s | 9.731s |
| Generic process reusing isolated cache | 1.380s, 1.468s, 1.390s | 1.390s |
| Axys/APX complete warm process | 1.453s, 1.419s, 1.424s | 1.424s |
| Axys/APX analytics and attribution | 0.120s, 0.112s, 0.113s | 0.113s |
| Axys/APX risk-statistics construction | 0.009s, 0.008s, 0.008s | 0.008s |
| Axys/APX HTML serialization | 0.007s, 0.008s, 0.007s | 0.007s |
| Axys/APX warm rendering of seven PNGs | 0.626s, 0.631s, 0.627s | 0.627s |
| Genuine 25-year complete bundle | 2.002s, 2.003s, 1.990s | 2.002s |
| Exact-monthly analytics, attribution, risk | 0.214s, 0.212s, 0.206s | 0.212s |
| Bulk 40-account Axys/APX load | 0.457s, 0.448s, 0.442s | 0.448s |

These results confirm the earlier prioritization. Ordinary financial construction is
small, chart work dominates the standard complete bundle, a discarded font cache
creates the largest latency event, and the monthly and bulk-account workloads are
large enough to measure the two conditional optimizations reliably.

## Validation

The benchmark completed all six scenarios and explicitly reported that it applied no
gates. Focused benchmark tests passed. Mypy, Pyright, Pylint error checks, and
`git diff --check` passed for the new harness and tests.

The complete routine product gate also passed with 367 tests and 446 subtests, all
static checks, current README-image provenance, wheel build and metadata validation,
isolated installation and `pip check`, and both installed 11-report demonstrations.

The benchmark command is documented in `docs/maintenance.md` as an informational
diagnostic, separate from `check_project.py`, `check_scale.py`, and the unchanged
release-candidate thresholds.
