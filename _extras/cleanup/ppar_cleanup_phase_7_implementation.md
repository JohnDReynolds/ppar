# ppar Cleanup Phase 7 Implementation

Status: Complete
Date: September 4, 2026
Baseline revision: `5d5d15682b49784c26b9a6aa53756de53f54f3e9`

## Objective

Narrow importable but undocumented compatibility surfaces while preserving the
complete documented API, automatic financial checks, financial results, output
schemas, and supported generic and Axys/APX workflows.

## Decisions and changes

- Designated `Performance` as an internal prepared-data type behind `Analytics` and
  corrected the Python API guide so it describes supported table inputs without
  presenting `Performance` as public. Removing its direct source-loading constructor
  is coordinated with Phase 8, where the dependent algorithm tests can be mapped to
  `perfattr` before deletion; doing that here would create temporary private test
  plumbing with no product value.
- Removed the unsupported `Analytics.audit()` and
  `Attribution.audit_attributions()` methods. Retained constructor-time financial
  validation and made the remaining attribution audit helper private.
- Removed `AxysData`'s individual portfolio- and security-performance path keyword
  overrides. Paths now have one configuration route through `values["files"]`.
- Narrowed `AxysPortfolio.to_analytics()` to an optional reconciled `AxysPortfolio`
  benchmark and the supported frequency, holiday, portfolio-value, and risk options.
  Portfolio names, classifications, and source date windows now come from the loaded
  Axys portfolios rather than duplicate call-time overrides.
- Removed custom sorting parameters from `Attribution.to_chart()` and the heatmap
  renderer. Each chart retains its established standard order; table sorting remains
  available through `to_polars()`, `to_html()`, and `write_csv()`.
- Updated focused contracts, Axys validation fixtures, scale setup, and Python API
  documentation for the narrowed boundaries.

## Validation

- Focused Phase 7 tests: 139 tests and 108 subtests passed.
- Complete suite: 367 tests and 517 subtests passed in 28.58 seconds.
- Mypy: clean across 38 source files.
- Pyright: 0 errors and 0 warnings.
- Pylint errors-only and focused unused/deprecated/unreachable checks: clean.
- README images were regenerated after rendering-source changes; provenance check
  passed.
- Universal wheel build, Twine validation, isolated installation, dependency check,
  CLI version, generic setup, and Axys/APX setup all passed.
- Both installed demonstrations produced the ordered 11-report bundle.
- The unchanged 500x scale gate passed: the 6,063,000-row large-site workload
  completed at 1.060x baseline time, the selected workload at 1.960x, and the
  thresholded five-times-long-history workload at 1.075x versus warning and failure
  ratios of 1.58x and 1.65x.
- `git diff --check`: passed.
