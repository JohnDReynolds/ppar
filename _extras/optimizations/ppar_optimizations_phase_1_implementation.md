# ppar Optimization Roadmap: Phase 1 Implementation

Status: Complete  
Implementation date: September 2, 2026

## Outcome

Ordinary chart processes now store Matplotlib's font and configuration cache in a
persistent per-user location instead of the operating system's temporary directory.
A completed font cache therefore survives routine temporary-directory cleanup and
does not need to be rebuilt by a later ppar process.

The policy retains two important boundaries:

- a caller-supplied `MPLCONFIGDIR` remains authoritative; and
- when the persistent user cache cannot be created, ppar falls back to its former
  writable `ppar_chart_cache/matplotlib` location under the operating system's
  temporary directory.

ppar no longer assigns `XDG_CACHE_HOME` globally. If the caller supplies that
standard cache root but does not supply `MPLCONFIGDIR`, ppar places its persistent
Matplotlib state beneath `XDG_CACHE_HOME/ppar/matplotlib`.

No chart layout, renderer, financial result, report filename, output schema,
tolerance, warning boundary, or release gate changed.

## Test-first evidence

Before the production change, focused subprocess regressions failed for both the
ordinary platform cache and an explicit XDG cache root. Both resolved instead to
`ppar_chart_cache/matplotlib` beneath the operating system's temporary directory.
The existing explicit-`MPLCONFIGDIR` case passed and was retained as a compatibility
contract.

The completed focused suite covers:

- default macOS, Linux, and Windows cache locations;
- an explicit XDG cache root;
- an explicit `MPLCONFIGDIR` taking precedence over every default; and
- fallback to writable temporary storage when the selected user cache cannot be
  created.

The cache-policy tests are isolated from Matplotlib imports, so they validate path
selection and filesystem behavior without repeatedly building font caches during the
normal test suite. Existing chart and output-contract tests continue to exercise
actual rendering.

## Implementation

The new internal `_chart_environment` module selects:

- `~/Library/Caches/ppar/matplotlib` on macOS;
- `$XDG_CACHE_HOME/ppar/matplotlib`, or `~/.cache/ppar/matplotlib`, on Linux and
  other Unix-like systems; and
- `%LOCALAPPDATA%/ppar/Cache/matplotlib`, with a home-directory fallback, on
  Windows.

`ppar.charts` invokes this policy before importing any Matplotlib module. Directory
creation is idempotent and safe when several ordinary processes start against the
same completed cache.

## Artifact and timing validation

A clean isolated persistent home produced its font cache at:

```text
~/Library/Caches/ppar/matplotlib/fontlist-v390.json
```

The first process took 9.73 seconds while building that cache; the immediately
following process took 1.45 seconds and reused the file. A three-sample warm run then
measured 1.348, 1.354, and 1.357 seconds, for a 1.354-second median. The Phase 0 warm
median was 1.330 seconds, so the persistent location introduced no material warm-run
regression.

For comparison, a process using an explicitly isolated recreation of the former
temporary-cache policy took 9.79 seconds. All 11 reports from that run were
byte-for-byte identical to the reports produced through the new persistent default.

The benchmark's explicit isolated-cache scenario continued to work and measured a
9.829-second cold process followed by a 1.366-second median for processes reusing the
same cache. This also confirms that caller-supplied cache isolation remains available
for diagnostics and CI.

## Validation

The focused cache, chart, and output-contract selection passed with 26 tests and 7
subtests. Mypy, Pyright, Pylint error checks, and the focused unused-code check passed.

The complete routine product gate passed with:

- 371 tests and 449 subtests;
- Mypy clean across 40 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- refreshed and current provenance for all 12 retained README images;
- wheel build and Twine metadata validation passing;
- isolated wheel installation and `pip check` passing; and
- both installed setup demonstrations producing their unchanged ordered bundles of
  11 reports.

The 500x scale check is unchanged and remains scheduled after the cross-cutting core
and bulk-loading Phases 3 and 4, as specified by the roadmap.

## Phase 2 follow-up

Phase 2 exposed one additional cache edge case: an existing persistent directory can
allow an idempotent `mkdir` while still rejecting file creation. The cache policy now
performs a real temporary-file write probe before selecting a directory and falls
back to temporary storage when that probe fails. A focused regression covers this
case. In the restricted local environment used for validation, the fix reduced chart
import startup from approximately 8–9 seconds to 0.47 seconds.
