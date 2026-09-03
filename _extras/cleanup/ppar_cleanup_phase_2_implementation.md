# ppar Cleanup Phase 2 Implementation

Status: Complete  
Implementation date: September 2, 2026  
Starting revision: `44dd4d1f74dd076a0004d5632ff2c9569fe45336` with Phase 1 uncommitted

## Outcome

Phase 2 returned all Matplotlib cache ownership to Matplotlib while retaining ppar's
small static-rendering policy.

Removed:

- `src/ppar/_chart_environment.py` — 112 lines; and
- `tests/test_chart_cache.py` — 216 lines.

`src/ppar/charts.py` now uses one pre-import
`os.environ.setdefault("MPLBACKEND", "Agg")` call. It neither selects nor creates a
cache directory. An explicitly configured environment backend and a backend selected
programmatically before importing ppar remain authoritative.

Two focused backend tests now live in `tests/test_charts.py`. They cover the ordinary
Agg default plus environment and programmatic SVG overrides. Phase 2 contains 58
inserted and 334 deleted text lines, a net reduction of 276 lines. Together, Phases 1
and 2 contain 58 insertions and 917 deletions, a net reduction of 859 lines.

## Native-cache evidence

A fresh writable simulated user directory demonstrated Matplotlib's native behavior:

- the first process built its native `.matplotlib` font cache in 9.13 seconds;
- the next process reused that cache in 0.12 seconds;
- importing `ppar.charts` used the same native directory and left `MPLCONFIGDIR`
  unset; and
- the selected backend was `Agg`.

Matplotlib also honored an explicit `MPLCONFIGDIR`. With an unusable simulated home,
it emitted its standard warning and created a valid temporary cache automatically.
This fallback remains functional but is deliberately process-local; callers running
repeated processes with a read-only home can supply a persistent `MPLCONFIGDIR`, as
Matplotlib recommends.

## Output and timing evidence

The complete generic output directory generated before and after the change compared
byte-for-byte equal. The warm before and after observations were 1.43 and 1.17
seconds, respectively; this is evidence of no material regression rather than a
claimed speed improvement.

The chart-source fingerprint embedded in all 12 README images necessarily changed.
The images were regenerated, and a decoded pixel comparison against every prior image
found no pixel, mode, or dimension difference.

The complete test suite using the warmed native cache passed 384 tests and 473
subtests in 18.81 seconds, consistent with the 18.97-second reassessment observation.

## Validation

The complete routine product gate passed:

- 384 tests and 473 subtests;
- Mypy, Pyright, Pylint errors-only, and selected unused-code checks;
- documentation and refreshed README-image validation;
- isolated wheel construction, inspection, and Twine validation; and
- installed CLI, dependency, generic demonstration, and Axys/APX demonstration
  checks.

The gate also passed in the assessment sandbox's intentionally unwritable home. Its
69-second elapsed time includes Matplotlib rebuilding a process-local fallback cache
for separate child processes and does not represent normal writable-home behavior.

The unchanged 500x scale command passed with an explicit already-warmed cache:

- large-site equivalence: 0.828x, observation only;
- selected workload: 1.895x against unchanged 2.10x warning and 2.20x failure
  boundaries; and
- long history: 1.473x against unchanged 1.58x warning and 1.65x failure boundaries.

`git diff --check` passed. No financial result, public API, report name, report order,
output schema, image pixel, or release threshold changed.
