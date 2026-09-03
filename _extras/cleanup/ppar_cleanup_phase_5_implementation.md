# ppar cleanup Phase 5 implementation

Date: September 2, 2026

## Outcome

The cleanup roadmap is complete. The project is smaller and more direct, every
supported workflow and established gate passes unchanged, and the final review found
no additional recent machinery that warrants another cleanup phase.

The cumulative text change from the clean assessment baseline at `44dd4d1` is 191
insertions and 1,097 deletions, a net reduction of 906 lines:

| Area | Added | Removed | Net reduction |
| --- | ---: | ---: | ---: |
| Production package | 27 | 155 | 128 |
| Tests | 164 | 457 | 293 |
| Scripts and maintenance documentation | 0 | 485 | 485 |
| **Total** | **191** | **1,097** | **906** |

Four files were deleted: the completed optimization benchmark and its tests, and the
custom Matplotlib cache module and its tests. Twelve gallery images have refreshed
source fingerprints because the chart source changed; decoded comparisons confirm
that all 12 remain pixel-, mode-, and dimension-identical to the prior images. No
unexpected build or generated artifact remains in the working tree.

## Integrated release validation

The unchanged complete release-candidate command passed. Its routine product gate
reported:

```text
383 tests passed, 477 subtests passed
Mypy: success in 37 source files
Pyright: 0 errors, 0 warnings, 0 information messages
Pylint errors-only: passed
Pylint unused-import/unused-variable: 10.00/10
README image validation: passed
Universal wheel: ppar-0.2.0-py3-none-any.whl
Twine check: passed
Installed-wheel package and dependency checks: passed
Installed-wheel generic workflow: passed
Installed-wheel Axys/APX workflow: passed
```

The release run deliberately began with a new Matplotlib cache and its pytest step
took 20.68 seconds, including the one-time native font-cache construction. A second
complete pytest run using that native cache took 11.81 seconds, 37.7% below the
roadmap's original 18.97-second observation. These are observations only; no timing
threshold was added or changed.

The required unchanged 500x scale sequence passed:

| Workload | Data growth | Time ratio | Established boundary |
| --- | ---: | ---: | --- |
| Large-site equivalence | 500.00x | 1.103x | Observation only |
| Selected workload | 10.00x | 1.925x | Warn 2.10x; fail 2.20x |
| Long history | 5.00x | 1.461x | Warn 1.58x; fail 1.65x |

The 500x baseline and scaled report files were byte-for-byte equal.

A later prepublication portability investigation superseded only the selected row's
timing boundary. Two repeatable GitHub ratios near 3.0x were traced to available
Polars workers: the same workload ranged from 5.221x with one worker to approximately
1.89x with 14 workers while retaining identical financial results. With explicit
user approval, selected-workload timing is now observation-only; all row-growth,
financial-equivalence, and deterministic source-loading assertions remain. The
long-history timing boundary remains unchanged.

An additional independent run confirmed that both source variants print and create
the same ordered 11-report inventory:

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

`git diff --check` passed, and no removed module or benchmark name remains referenced
by the active repository.

## Performance accounting

The changes preserve or simplify the relevant measured behavior:

- Matplotlib now owns its native persistent cache. The Phase 2 evidence measured a
  fresh cache at 9.13 seconds and a second process at 0.12 seconds. A standard warm
  bundle showed no regression at 1.17 seconds versus 1.43 seconds before the change.
- The Phase 3 two-account Axys/APX load remained 0.027 seconds before and after. The
  40-account, 242,520-security-row load was 0.383 versus 0.384 seconds, ordinary
  measurement variation, while padded identifiers and incomplete mappings no longer
  cause fallback scans.
- Phase 4 removed six redundant complete report renders from the tests. The final
  warm suite observation is 11.81 seconds versus the 18.97-second assessment
  baseline.

## Final keep-list reassessment

The roadmap's keep list was reassessed against the final code and evidence. All items
still earn their maintenance cost:

- large-heatmap raster annotations protect the established long-history gate while
  retaining every annotation;
- exact-period consolidation and one-time account partitioning retain measured
  material benefits on supported workloads;
- the lightweight HTML and percentage presentation behavior is user-approved and
  directly tested;
- direct tutorial loops keep report selection visible without restoring report-bundle
  infrastructure;
- financial and reconciliation tests continue to protect distinct formulas and
  invariants; and
- the 12-image gallery and standard 11-report bundle remain explicit product choices.

No public API, financial result, output schema, report name or order, presentation
pixel, tolerance, warning boundary, failure boundary, or release workflow was changed
by this roadmap.
