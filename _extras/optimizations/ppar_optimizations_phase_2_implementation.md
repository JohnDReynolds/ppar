# ppar Optimization Roadmap: Phase 2 Implementation

Status: Complete  
Implementation date: September 2, 2026

## Outcome

Ordinary ppar chart processes now use Matplotlib's non-GUI Agg backend by default.
This avoids initializing the macOS GUI backend for a library that produces static PNG
bytes. A backend explicitly selected through `MPLBACKEND`, or selected
programmatically before importing `ppar.charts`, remains authoritative.

No chart layout, financial result, report filename, report ordering, output schema,
tolerance, warning boundary, or release gate changed.

## Test-first evidence

Before implementation, a clean subprocess importing `ppar.charts` selected the
`macosx` backend, so the new ordinary-import regression failed. Existing caller
control was then captured with two passing compatibility cases:

- `MPLBACKEND=svg` remains `svg`; and
- `matplotlib.use("svg")` before importing `ppar.charts` remains `svg`.

After implementation, the ordinary process selects `Agg`, and both compatibility
cases continue to pass. The chart regression suite iterates over every `Chart` enum
member, covering all 12 chart variants.

## Implementation

The internal chart-environment policy now sets `MPLBACKEND=Agg` only when the variable
is absent. `ppar.charts` invokes the policy before importing any Matplotlib module,
which ensures the default is effective without overwriting a caller's explicit
choice.

During restricted-environment validation, Phase 2 also exposed an existing Phase 1
edge case: an already-created persistent cache directory could reject file writes
even though `mkdir(..., exist_ok=True)` succeeded. The cache policy now verifies its
selected directory with an actual temporary-file write and falls back to temporary
storage on failure. This removed an unintended 8–9 second startup penalty in that
environment.

## Artifact validation

A complete pre-change bundle rendered with the macOS backend and a complete
post-change bundle rendered with Agg each contained the standard 11 reports. A
recursive byte comparison found no difference in any HTML or PNG artifact.

All 12 retained README images were regenerated and their provenance check reports
them current.

## Performance results

The repeatable Phase 0 harness was run with three samples after the change. Medians
are compared with the corresponding recorded baseline:

| Workload | Before | After | Change |
| --- | ---: | ---: | ---: |
| Generic 11-report bundle | 1.354 s | 1.141 s | 15.7% faster |
| Axys/APX 11-report bundle | 1.424 s | 1.201 s | 15.7% faster |
| Genuine 25-year bundle | 2.002 s | 1.741 s | 13.0% faster |
| Generic seven-PNG rendering | 0.617 s | 0.547 s | 11.3% faster |
| Axys/APX seven-PNG rendering | 0.627 s | 0.550 s | 12.3% faster |

The isolated cold-cache process remained approximately 9.73 seconds because
one-time font-cache construction dominates that scenario. A process reusing the same
isolated cache measured a 1.139-second median.

## Validation

Focused cache/backend tests passed with eight tests and three subtests. Focused chart
and output-contract tests passed with 22 tests and four subtests. Mypy, Pyright,
Pylint error checks, and the focused unused-code check passed.

The complete routine product gate passed with:

- 375 tests and 449 subtests;
- Mypy clean across 40 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- all 12 retained README images current;
- wheel build and Twine metadata validation passing;
- isolated wheel installation and `pip check` passing; and
- both installed setup demonstrations producing their unchanged ordered bundles of
  11 reports.

The 500x scale check is unchanged and remains scheduled after the cross-cutting core
and bulk-loading Phases 3 and 4, as specified by the roadmap.
