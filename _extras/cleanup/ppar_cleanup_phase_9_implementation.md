# ppar Cleanup Phase 9 Implementation

Status: Complete
Date: September 4, 2026
Baseline revision: `5d5d15682b49784c26b9a6aa53756de53f54f3e9`

## Outcome

The cleanup roadmap is complete. The project has a smaller, clearer supported surface;
ppar tests the behavior it owns while `perfattr` tests portable algorithms; and every
documented workflow, financial check, output schema, report inventory, packaging gate,
and scale gate passes unchanged.

No additional cleanup candidate now has an evidence-backed 80/20 payoff. Further broad
module splitting, fixture centralization, presentation replacement, or dependency
restructuring would create more churn than simplification.

## Final accounting

The exact Python-code change from the clean post-v0.3.1 revision `5d5d156` to the final
integrated working tree is:

| Area | Added | Removed | Net change |
| --- | ---: | ---: | ---: |
| Production package | 155 | 403 | -248 |
| Tests | 299 | 1,015 | -716 |
| Scripts | 12 | 6 | +6 |
| **Total** | **466** | **1,424** | **-958** |

The test total includes the 203-line replacement
`tests/test_performance_sources.py`. Documentation, roadmap records, and binary image
metadata are excluded from Python-code accounting. The integrated working tree contains
9,396 production, 1,393 script, and 9,082 test lines, or 19,871 total Python lines
across those areas.

This final revision comparison includes the correctness and optimization changes that
were already in progress when the September 4 cleanup reassessment began. Phase-specific
reports identify cleanup-only decisions; this table describes the exact final product
tree relative to its clean Git baseline.

The suite changed from the Phase 6 reassessment observation of 378 tests and 524
subtests to 330 tests and 501 subtests. The net reduction of 48 tests and 23 subtests is
confined to removed compatibility behavior, deletion archaeology, duplicated
dependency algorithms, and redundant internal-container contracts.

## Release-candidate validation

The unchanged composed command
`./.venv/bin/python scripts/check_release_candidate.py` passed:

- 330 tests and 501 subtests passed in 32.15 seconds;
- Mypy passed across 38 source and script files;
- Pyright reported 0 errors and 0 warnings;
- Pylint errors-only and focused unused-import/unused-variable checks passed;
- README image inventory, formats, dimensions, decodability, and provenance passed;
- the universal `ppar-0.3.1-py3-none-any.whl` built and passed Twine validation;
- isolated wheel import, version, dependency, and CLI checks passed; and
- installed generic and Axys/APX workflows each produced the ordered 11-report bundle.

The installed report inventory remained:

1. `security_overall_attribution.html`
2. `classification_cumulative_attribution.html`
3. `classification_overall_attribution.html`
4. `classification_overall_contribution.png`
5. `classification_overall_attribution.png`
6. `classification_subperiod_attribution.png`
7. `classification_heatmap_active_contribution.png`
8. `classification_heatmap_attribution.png`
9. `classification_cumulative_attribution.png`
10. `classification_cumulative_return.png`
11. `risk_statistics.html`

## Scale validation

The unchanged release-candidate 500x gate passed:

| Workload | Data growth | Time ratio | Established boundary |
| --- | ---: | ---: | --- |
| Large-site equivalence | 500.00x | 1.045x | Observation only |
| Selected workload | 10.00x | 1.894x | Observation only |
| Long history | 5.00x | 1.068x | Warn 1.58x; fail 1.65x |

The large-site case processed 6,063,000 rows and required byte-for-byte equivalent
baseline and scaled reports. The selected workload retained its row-growth and
financial-equivalence assertions. No threshold or tolerance changed.

## Generated-artifact review

All 12 README gallery images carry the current source fingerprint. Decoded comparison
against revision `5d5d156` confirmed that every image is pixel-, mode-, and
dimension-identical; only provenance metadata changed. No wheel, source archive, or
temporary output was left in the repository, and `git diff --check` passed.

## Final supported surface

The supported Python surface remains exactly the one documented in `docs/python_api.md`:

- root imports are `Analytics` and `__version__`;
- attribution results expose `Attribution`, `Chart`, and `View`;
- Axys/APX exposes `AxysClassificationSources`, `AxysData`, and `AxysPortfolio`;
- errors, frequency, risk arrays, and schema names retain their focused modules; and
- `Performance`, `Classification`, tables, utilities, adapters, and audit helpers are
  implementation details.

Generic portfolio sources have one public path through `Analytics`. `Performance`
containers can be created only from aligned `perfattr` preparation. Financial audits
remain automatic and inexpensive; unsupported manual audit entry points are absent.
Axys/APX file paths have one configuration route through `values["files"]`, and
`AxysPortfolio.to_analytics()` accepts only the supported portfolio benchmark and
calculation options. Charts use their established order; custom sorting remains on
tabular Polars, HTML, and CSV outputs where it is useful.

## Keep-list conclusion

The retained large-heatmap path, exact-period consolidation, one-time Axys account
partitioning, lightweight HTML formatting, direct tutorial loops, independent
financial and reconciliation invariants, 12-image gallery, and 11-report bundle still
meet the roadmap's earning-its-keep test. They should not be reopened without new
correctness evidence, a measured material regression, or a changed product decision.
