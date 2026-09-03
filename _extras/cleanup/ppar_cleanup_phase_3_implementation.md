# ppar Cleanup Phase 3 Implementation

Status: Complete  
Implementation date: September 2, 2026  
Starting revision: `44dd4d1f74dd076a0004d5632ff2c9569fe45336` with Phases 1–2 uncommitted

## Outcome

Axys/APX performance and security-master loading now normalize relevant text inside
one lazy source query. The former exact-filter collection followed by a conditional
normalized fallback collection is gone.

For performance sources, the normalized portfolio-code predicate remains pushed into
the CSV scan. Selected account codes, names, security identifiers, and composite-ID
components are then stripped in the same lazy pipeline before its single
materialization.

For classification and mapping sources, the security-identifier filter compares the
trimmed value and all selected identity and display-name text is normalized before the
single collection. A small named collection boundary mirrors the existing performance
source boundary and makes the one-materialization invariant directly testable.

Surrounding whitespace remains transparent to users. Null or whitespace-only values
are still rejected, meaningful internal spaces and leading zeroes are preserved, and
an identifier missing from a mapping still remains its own classification group.

## Test-first evidence

The new focused regressions failed against the prior implementation because:

- padded portfolio codes caused four performance collections—an empty exact query and
  a normalized fallback for each of `portperf.csv` and `secperf.csv`—instead of two;
- a padded mapping identifier caused two security-master collections instead of one;
  and
- an ordinary valid incomplete mapping also caused two collections because the former
  fallback could not distinguish a missing mapping from source padding.

The completed tests require:

- one collection for each of the two performance files even when account codes,
  display names, and security identifiers are padded;
- a normalized account selection inside each optimized CSV scan;
- one security-master collection for both padded and incomplete mapping cases; and
- the same normalized public portfolio, display name, security ID, and mapping rows.

The separate security-identifier and portfolio-code trimming fixtures were combined
because both now exercise the same source pipeline. Phase 3 changed 88 lines and
removed 92, including 14 fewer production lines and 10 additional focused test lines.
The cumulative result through Phase 3 is 146 insertions and 1,009 deletions, a net
reduction of 863 lines.

## Performance evidence

A five-sample same-machine comparison ran the identical workload against commit
`44dd4d1` and the Phase 3 implementation:

| Workload | Prior median | Phase 3 median |
| --- | ---: | ---: |
| Normal two-account Axys/APX load | 0.027 s | 0.027 s |
| 40 accounts, 242,520 security rows | 0.383 s | 0.384 s |

The one-millisecond bulk difference is ordinary timing variation. The change removes
an entire additional scan when source account codes are padded and removes the
unnecessary additional security-master scan for valid incomplete mappings.

## Validation

Focused Axys/APX, classification, mapping, normalization, reconciliation, and
scale-plan coverage passed with 167 tests and 336 subtests.

The complete routine product gate passed:

- 383 tests and 477 subtests in 17.50 seconds;
- Mypy reported no issues in 37 source files;
- Pyright reported 0 errors, warnings, or information messages;
- Pylint errors-only and selected unused-code checks passed;
- documentation and README-image checks passed;
- the isolated universal wheel passed construction, inspection, and Twine validation;
  and
- installed CLI, dependency, generic demonstration, and Axys/APX demonstration
  checks passed with the unchanged 11-report bundles.

The unchanged 500x scale check passed:

- large-site equivalence: 1.093x, observation only;
- selected workload: 1.990x against unchanged 2.10x warning and 2.20x failure
  boundaries; and
- long history: 1.466x against unchanged 1.58x warning and 1.65x failure boundaries.

`git diff --check` passed. No public API, financial result, report, output schema,
validation threshold, or release gate changed.
