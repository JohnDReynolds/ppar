# ppar Correctness Roadmap: Phase 12 Implementation

Status: Complete  
Implementation date: September 1, 2026

## Outcome

Phase 12 makes Axys/APX portfolio display names deterministic. A genuine account
rename across source periods is permitted, and the name from the chronologically
latest retained period is selected regardless of physical `portperf.csv` row order.
The exact portfolio code continues to prefix the selected name.

Selected portfolio names must now be non-null, nonblank, and free of surrounding
whitespace. Validation occurs after portfolio-code and requested-date filtering, so a
later source period outside the retained window cannot determine the current report
name.

## Test-first evidence

Three focused regression methods were added before production changes. The initial
Axys run demonstrated that:

- null, empty, whitespace-only, leading-space, and trailing-space portfolio names
  were all accepted;
- reversing otherwise identical source rows changed `P1` from the latest
  `Growth Current` name to the earlier `Growth Legacy` name; and
- the order-dependent name prevented the reversed-source financial and report-title
  comparison from completing.

The completed cases cover a stable name through existing tests, a two-period rename,
both source row orders, five invalid-name forms, two portfolio codes loaded together,
and a date window that excludes the latest source period. The row-order regression
also requires identical overall attribution output and verifies the selected name in
the HTML report title.

## Implementation

### Portfolio-name validation

The normalized portfolio-performance loader now validates `portfolio_name` alongside
the portfolio code. It uses the same narrow exact-text predicate as the established
identity checks: null, blank, and surrounding whitespace fail with source path,
field, selected portfolio, and date-window context. Names are rejected rather than
silently trimmed.

Security-performance validation remains limited to its portfolio and security
identities. The internal validation helper was renamed to reflect that it now checks
both identities and the portfolio display-name field.

### Deterministic retained-period selection

After portfolio and security sources have proven that their complete retained period
keys match and reconciliation succeeds, portfolio rows are sorted by period end and
start dates. The final row supplies the display name. This selects the latest retained
period rather than row zero or the latest unselected source period.

The resulting `AxysPortfolio.portfolio_name` remains:

```text
portfolio_code + " - " + latest_retained_name
```

### Documentation

The generated Axys/APX README, configuration guide, Python API guide, loader
docstrings, and `AxysPortfolio` attribute documentation now explain exact-text name
validation, chronological renames, date-window behavior, and code prefixing.

## Validation

The focused Axys/APX loading and validation suites passed with 65 tests. Their
combined selection with public output-contract tests passed with 76 tests.

`./.venv/bin/python scripts/check_project.py` passed with:

- 361 tests and 446 subtests;
- Mypy clean across 38 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- all documentation-image and provenance checks current;
- wheel build, Twine validation, isolated installation, and `pip check` passing; and
- both installed setup demonstrations producing their unchanged ordered bundles of
  11 reports.

The documentation gallery was regenerated for the corrected source fingerprint. All
12 retained images remain in the documented inventory; no image or report selection
changed.

The unchanged 500x scale workflow passed:

- large-site 500x median paired ratio: 1.089x, above the unchanged 1.05x warning
  boundary and below the unchanged 1.10x failure boundary;
- selected-workload 10x ratio: 1.921x, below the unchanged 2.10x warning and 2.20x
  failure boundaries; and
- genuine long-history 5x ratio: 1.375x, below the unchanged 1.58x warning and 1.65x
  failure boundaries.

No public output column, PNG filename, report inventory, financial calculation,
established tolerance, test threshold, or performance gate was changed or relaxed.
