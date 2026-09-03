# ppar Correctness Roadmap: Phase 9 Implementation

Status: Complete  
Implementation date: September 1, 2026

## Outcome

Phase 9 closes the remaining generic identity-handling gaps found by the post-cleanup
reassessment. Vendor-neutral CSV loading now preserves identifiers as exact text
before Polars can infer a numeric type, and generic performance and mapping inputs now
reject null, blank, or surrounding-whitespace identities at their public boundaries.

Intentional internal spaces remain valid identity content. The implementation shares
one narrow identity-validation predicate between generic and Axys/APX loading without
adding a public API, output column, or compatibility layer.

## Test-first evidence

Focused regression tests were added before production changes. The initial run failed
on the intended defects:

- `001` and `1` collided after CSV inference;
- a 20-digit identifier leaked a Polars integer-conversion error;
- generic performance accepted blank and padded identifiers or reported a generic
  null-value error; and
- malformed mapping identities were accepted or filtered out before validation.

The tests cover CSV and Polars DataFrame inputs, both mapping columns, null, empty,
whitespace-only, leading-space, and trailing-space values. They also preserve leading
zeroes, a large digit string, mixed alphanumeric text, and meaningful internal spaces.
The CSV preservation test passes identifiers through both `Performance` and the
public `Analytics` attribution path.

## Implementation

### Vendor-neutral performance input

The performance CSV scan now supplies a partial string schema override for the
identifier column. Date, return, and weight columns continue to use their established
inference and normalization paths.

After required columns are cast but before generic null validation, `Performance`
checks its identifier column and raises a contextual `PparError` when an identity is
null, blank, or has surrounding whitespace. Exact source text is retained; invalid
identities are rejected rather than silently trimmed.

### Generic mapping input

Mapping loading now validates both the source and destination identity columns before
filtering to the identifiers required by a calculation. This ordering prevents a
padded or otherwise malformed source identity from disappearing and falling back to
self-mapping.

The existing invalid-identity predicate was moved from the Axys/APX validation module
to the internal shared utilities module. Axys/APX performance and classification
loaders continue to use the same rule, so their behavior remains aligned with generic
inputs.

### Documentation

The generic setup README and configuration guide now state that performance and
mapping identities are exact textual values, leading zeroes are preserved, surrounding
whitespace is invalid, and internal spaces are retained.

## Validation

The focused performance, mapping, classification, and Axys/APX selections passed with
118 tests.

`./.venv/bin/python scripts/check_project.py` then passed with:

- 344 tests and 419 subtests;
- Mypy clean across 38 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- wheel build, Twine validation, isolated installation, and `pip check` passing; and
- both installed setup demonstrations producing their unchanged ordered bundles of
  11 reports.

The documentation images were regenerated to refresh the renderer provenance after
the source fingerprint changed. All 12 retained images remain in the documented
inventory; Phase 9 did not change report or image selection.

The unchanged 500x scale workflow also passed:

- large-site 500x median paired ratio: 1.071x, above the unchanged 1.05x warning
  boundary and below the unchanged 1.10x failure boundary;
- selected-workload 10x ratio: 1.873x, below the unchanged 2.10x warning and 2.20x
  failure boundaries; and
- genuine long-history 5x ratio: 1.322x, below the unchanged 1.58x warning and 1.65x
  failure boundaries.

No mathematical formula, financial tolerance, output schema, report inventory, test
threshold, or performance gate was changed.
