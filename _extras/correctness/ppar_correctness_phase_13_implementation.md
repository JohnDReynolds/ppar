# ppar Correctness Roadmap: Phase 13 Implementation

Status: Complete  
Implementation date: September 1, 2026

## Outcome

Phase 13 closes the post-cleanup correctness reassessment. Every finding added in
Phases 9 through 12 has focused regression coverage and recorded pre-fix failure
evidence. The final integration gap is also closed: malformed identities in both
generated setup variants now have an end-to-end test proving that validation fails
before publication and leaves an existing report bundle byte-for-byte intact.

No additional mathematical, financial, or production-code defect was found during
the integrated audit. No public output schema, report filename, tolerance, test
threshold, warning boundary, or release gate was changed.

## Regression audit

### Phase 9: generic identities

The regression suite preserves numeric-looking CSV identifiers such as `001`, keeps
`001` distinct from `1`, retains very large numeric text and mixed alphanumeric
identities, and rejects null, blank, or padded identities at both generic performance
and mapping boundaries. Intentional internal spaces remain valid.

The Phase 9 implementation record contains the pre-fix failures: Polars inference
had already changed `001` to `1`, and invalid generic identities had passed through
the public boundaries.

### Phase 10: scale-aware risk ratios

Independent-reference and metamorphic tests cover representable low-volatility
Sharpe, Sortino, and information ratios across positive scales, annualized results,
M-squared, minimum sample size, genuinely unresolvable risk, exact zero-over-zero,
and a small finite negative beta used by Treynor ratio.

The Phase 10 implementation record contains the pre-fix failures: small valid risk
was classified as zero, and a finite negative beta could produce positive infinity.

### Phase 11: zero-net heatmap semantics

Tests constructed from a real mapped attribution retain nonzero contribution for an
offsetting zero-net group. Undefined portfolio and active returns remain masked, and
explicit null cells remain distinct from absent pivot cells through both ordinary
and large-heatmap annotation paths. Existing duplicate-name and sorting protections
remain covered.

The Phase 11 implementation record contains the pre-fix failures: a valid zero-net
contribution disappeared, and undefined returns were rendered as numeric zeroes.

### Phase 12: deterministic Axys/APX names

Tests require null, blank, and padded portfolio names to fail; choose the latest
retained chronological name; remain independent of physical source-row order; apply
the policy independently to multiple portfolio codes; respect date filtering; and
verify both unchanged financial output and report titles.

The Phase 12 implementation record contains the pre-fix failures: malformed names
were accepted and reversing source rows changed the selected display name.

## Atomic-publication integration test

`test_malformed_identities_preserve_prior_atomic_report_bundles` now exercises both
generated workspaces after a successful report run:

- the generic portfolio CSV is rewritten with surrounding whitespace on every
  security identifier;
- the Axys/APX `secperf.csv` is rewritten with surrounding whitespace on every
  security-symbol identity;
- each subsequent demonstration exits unsuccessfully with a contextual `PparError`;
  and
- all 11 prior artifacts and an added sentinel file remain byte-for-byte unchanged.

This complements the existing end-to-end malformed-required-column rollback test
and the focused loader tests for all invalid identity forms.

## Public report contract

The final test and installed-wheel workflows verify both setup variants produce the
same ordered bundle of 11 reports. Existing regression and invariant tests retain
the public table schemas, deterministic titles, report filenames, portfolio and
benchmark totals, weight and contribution conservation, attribution-effect
reconciliation, and risk-statistics expectations. README-image provenance remained
current, and all 12 documented gallery images remain unchanged.

## Validation

The focused malformed-identity publication test passed for both setup variants.

The complete unchanged release-candidate command
`./.venv/bin/python scripts/check_release_candidate.py` passed with:

- 362 tests and 446 subtests;
- Mypy clean across 38 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- README-image provenance current;
- wheel build and Twine metadata validation passing;
- isolated wheel installation, import-origin validation, and `pip check` passing;
- both installed setup demonstrations producing their ordered 11-report bundles;
  and
- the complete unchanged 500x scale workflow passing.

The final scale measurements were:

- large-site 500x median paired ratio: 1.087x, above the unchanged 1.05x warning
  boundary and below the unchanged 1.10x failure boundary;
- selected-workload 10x ratio: 1.938x, below the unchanged 2.10x warning and 2.20x
  failure boundaries; and
- genuine long-history 5x ratio: 1.411x, below the unchanged 1.58x warning and 1.65x
  failure boundaries.

The large-site warning is retained as designed. It was not suppressed, reclassified,
or used to justify any threshold change.
