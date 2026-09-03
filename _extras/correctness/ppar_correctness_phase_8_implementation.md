# ppar Correctness Roadmap: Phase 8 Implementation

Status: Complete  
Implementation date: September 1, 2026  
Starting revision: `718f5054dc34cb88490cc92ffffa825e8448abdc`

## Outcome

Phase 8 completes the integrated regression and release-candidate validation for the
correctness roadmap. The complete product and scale gates pass without changing a
public output schema or relaxing an established threshold.

The Phase 8 audit found one missing end-to-end acceptance case. The atomic publication
unit tests proved rollback behavior for the context manager, but no test exercised a
generated demonstration with malformed input after a prior successful report bundle.
A new test now covers that workflow for both the vendor-neutral and Axys/APX setups.

No production behavior changed during Phase 8.

## Integrated contract coverage

### Report filenames

`test_setup_variants_are_valid_and_run_complete_workflows` generates and executes both
setup variants and requires the exact established inventory of 11 report filenames.
The installed-wheel smoke test independently executes both variants and also requires
11 artifacts from each.

### Schemas, values, and key totals

The fixture-based regression suite compares every attribution CSV view for both
Security and Economic Sector classifications with the stored complete CSV baselines.
It also compares the risk-statistics output with its stored baseline. These comparisons
cover column names, column order, row order, row counts, and calculated values.

The focused calculation suites independently enforce weight, contribution, return,
attribution-effect, smoothing, and Axys/APX reconciliation identities. This provides
financial conservation evidence in addition to the serialized-output comparisons.

### Chart series

The regression suite renders every public `Chart` member. Focused chart tests verify
that stable classification identifiers, rather than potentially duplicated display
names, determine heatmap series and that every large-heatmap cell remains annotated.
The tracked documentation-image gate also confirms the complete canonical image
inventory and renderer fingerprint.

### Malformed input and atomic publication

`test_malformed_inputs_preserve_prior_atomic_report_bundles` now performs the following
steps for each generated setup variant:

1. Run the unmodified demonstration and retain the complete successful report bundle.
2. Add a marker to that prior output and remove a required column from an input CSV.
3. Run the demonstration again and require a nonzero exit containing `PparError`.
4. Verify the marker and every byte of every prior report remain unchanged.

The focused Phase 8 regression selection passed with 22 tests.

## Documentation audit

The intentional behavior changes from Phases 1 through 7 were already recorded in the
active documentation:

- `docs/methodology.md` describes date-coverage matching, observed-period weight
  averaging, contribution and attribution conservation, zero-net group behavior,
  floating-point risk inputs, and scale-aware beta and correlation handling.
- `docs/python_api.md` documents accepted risk domains, Axys/APX pairing, contextual
  `PparError` failures, report selection, and atomic publication.
- `docs/configuration.md` documents exact Axys/APX reconciliation behavior and the
  generated demonstration's atomic output contract.
- `docs/maintenance.md` documents the routine product gate, unchanged 500x scale gate,
  release-candidate command, wheel checks, and publishing boundary.

Because Phase 8 added validation rather than product behavior, no further user-facing
documentation change was necessary.

## Complete validation

`./.venv/bin/python scripts/check_release_candidate.py` passed with:

- 323 tests and 314 subtests;
- Mypy clean across 37 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error checks clean;
- active-documentation, terminology, local-link, methodology, and demonstration checks;
- all tracked documentation images current;
- a universal wheel built and accepted by Twine;
- a clean wheel installation with `pip check` passing;
- both installed setup demonstrations producing all 11 reports; and
- the complete unchanged 500x scale workflow passing.

The final scale results were:

- large-site 500x: 1.10x displayed ratio, warning only, with the unchanged 1.05x
  warning and 1.10x failure boundaries;
- selected-workload 10x: 1.91x, below the unchanged 2.10x warning and 2.20x failure
  boundaries; and
- genuine long-history 5x: 1.37x, below the unchanged 1.58x warning and 1.65x failure
  boundaries.

The displayed large-site ratio is rounded to two decimal places; the unrounded value
remained below the unchanged failure boundary.

## Conclusion

All 15 roadmap items have regression coverage and their fixes pass the integrated
release-candidate workflow. The public report inventory and schemas remain stable,
financial and source-evidence invariants remain enabled, malformed inputs do not
publish partial output, and no test or performance gate was weakened.
