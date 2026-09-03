# ppar Correctness Roadmap: Phase 1 Implementation

Status: Complete  
Implementation date: August 31, 2026  
Starting revision: `718f5054dc34cb88490cc92ffffa825e8448abdc`

## Outcome

Phase 1 now enforces the input contracts needed by the later calculation phases:

- Axys/APX portfolio and security returns must be finite numbers.
- Axys/APX weight and contribution evidence may remain null for the Phase 3
  reconciliation policy, but any supplied value must be finite and numeric.
- Reconciliation repeats the financial-value checks defensively so direct callers
  cannot bypass the CSV loader.
- Portfolio codes, security identifiers, and classification codes are read as text
  before CSV inference and retain leading zeroes, very large digit strings, and mixed
  alphanumeric values.
- Null, blank, and whitespace-padded security and classification identities raise a
  contextual `PparError`.
- In-memory `Performance` dates are cast before requested date bounds are applied.
- Inferred display names use the chronologically latest row and no longer depend on
  physical input order.

No calculation formula, tolerance, release threshold, public output column, or
standard demonstration artifact was changed.

## Test-first evidence

The initial focused regression run against unchanged production code failed as
expected. It exposed all four Phase 1 boundaries:

- string date bounds leaked a Polars conversion error;
- inferred names depended on row order;
- nonfinite Axys/APX financial values reached reconciliation;
- numeric-looking portfolio, security, and classification identities were inferred
  as numbers or could not be selected through the public string API.

After implementation, the focused command passed:

```text
./.venv/bin/python -m pytest -q \
  tests/test_performance_normalization.py \
  tests/test_axys_validation.py \
  tests/test_axys_reconciliation.py

67 passed, 18 subtests passed
```

The coverage includes `NaN`, positive infinity, negative infinity, invalid numeric
text, required null returns, optional null evidence, `001` versus `1`, a 20-digit
identifier, an alphanumeric identifier, and invalid direct identities. Error checks
verify the normalized field, source file, and affected ISO-formatted period.

## Implementation details

### Financial input validation

`AxysPerformanceSourceLoader` now converts selected financial fields to `Float64`
and rejects values that cannot be represented as finite numbers. Required returns
also reject null. Optional weights and contributions retain genuine nulls for the
evidence-based reconciliation work planned for Phase 3.

`derive_security_performance_for_all_periods()` applies the same contract before it
invokes the weight solver. This closes the direct-call path that previously allowed a
nonfinite target or security value to bypass source validation.

### Identity preservation

Performance and classification loaders now supply partial Polars CSV schema overrides
for identity-bearing source columns before inference. Composite Axys/APX security-ID
overrides remain intact and are merged with the direct-identity overrides.

The public path preserves and distinguishes:

```text
001
1
99999999999999999999
A01
```

Supporting-source validation also rejects null, blank, and surrounding-whitespace
identity corruption instead of silently normalizing it.

### Date and display-name normalization

`Performance` now performs these operations in a deterministic order:

1. load rows;
2. retain and cast supported columns;
3. apply the requested date window;
4. validate and chronologically sort periods;
5. select the latest display name for each identifier;
6. calculate performance rows.

Malformed in-memory date text therefore raises `PparError`, and date filtering no
longer compares a Python date to an unnormalized string column.

## Complete validation

The routine product gate passed:

- Tests: 264 passed; 89 subtests passed.
- Mypy: no issues in 37 source files.
- Pyright: 0 errors, 0 warnings, 0 information messages.
- Pylint error checks: passed.
- README image provenance: passed after regeneration.
- Wheel build and Twine validation: passed.
- Isolated wheel installation and `pip check`: passed.
- Installed generic demonstration: passed and wrote 11 artifacts.
- Installed Axys/APX demonstration: passed and wrote 11 artifacts.

The README image files changed only because their required source fingerprints were
refreshed. A pixel-by-pixel comparison against the starting images found no visual
differences.

The unchanged scale gate also passed:

- Analytics large-site 500x: warning only; 12,126 to 6,063,000 rows; timing ratio
  1.08x against the unchanged 1.05x warning and 1.10x failure boundaries.
- Analytics selected-workload 10x: pass; 12,126 to 121,260 rows; timing ratio 1.84x
  against the unchanged 2.10x warning and 2.20x failure boundaries.
- Analytics long-history 5x: pass; 12,246 to 61,230 rows; timing ratio 0.99x against
  the unchanged 1.58x warning and 1.65x failure boundaries.

## Phase 1 conclusion

Phase 1 is complete. Phase 2 can now address exact period alignment using inputs whose
dates, numeric values, and identities have explicit validated contracts.
