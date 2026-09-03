# ppar Cleanup Roadmap: Phase 0 Assessment

Status: Complete  
Assessment date: September 1, 2026  
Production code changed: No  
Tests changed: No

## Outcome

The current working tree passes the complete release-candidate gate. The review found
no new mathematical defect and no entire tracked production module that is obviously
dead.

The user approved all seven recommended contracts. They are now authoritative for the
cleanup roadmap's later phases. In particular, the established 1,010-row HTML limit
is provisional but remains unchanged; a later removal or replacement requires new
browser evidence and separate explicit approval.

## Baseline identity

- Git branch: `main`
- Git revision: `1e69cf213c476cd7a6c1c24b830a7efc6a1dbdef`
- Python: `3.12.1`
- Package version: `0.2.0`
- Declared Python requirement: `>=3.11.9`
- Constraints file: `constraints/ci.txt`
- Constraints SHA-256:
  `647e9a912b389bc60ebcf0176e5158ebb53b49e12a8fa3bea9b22f5bdb9266c2`
- Baseline command: `./.venv/bin/python scripts/check_release_candidate.py`
- Baseline working tree: dirty before and after validation, containing the existing
  user-approved Axys fixture flattening, inline-fixture cleanup, source cleanup,
  dependency/documentation updates, and README-image fingerprint changes.

The release gate's generated `build/` and `src/ppar.egg-info` paths are ignored. The
tracked and untracked user changes reported by `git status` were unchanged by the
assessment.

## Complete baseline validation

The release-candidate gate passed:

- Pytest: 323 tests and 317 subtests passed.
- Mypy: no issues in 37 source files.
- Pyright: no errors, warnings, or information messages.
- Existing Pylint errors-only gate: passed.
- README-image provenance and validation: passed.
- Universal wheel build: passed.
- Twine wheel validation: passed.
- Installed wheel origin and package-isolation smoke: passed.
- Installed CLI version: `ppar 0.2.0`.
- Installed vendor-neutral setup and 11-report demonstration: passed.
- Installed Axys/APX setup and 11-report demonstration: passed.
- 500x scale gate: passed.

The unchanged 500x results were:

| Workload | Small to large rows | Time scaling | Result |
| --- | ---: | ---: | --- |
| Large-site 500x | 12,126 to 6,063,000 | 1.48s to 1.61s; 1.08x | Warning, below 1.10x failure |
| Selected-workload 10x | 12,126 to 121,260 | 0.20s to 0.38s; 1.89x | Pass, below 2.20x failure |
| Long-history 5x | 12,246 to 61,230 | 1.45s to 2.00s; 1.38x | Pass, below 1.65x failure |

The large-site warning is established diagnostic behavior. No benchmark threshold was
changed or proposed during Phase 0.

## Contract 1: Meaning of `from_date`

### Current behavior

Both generic `Performance` filtering and Axys/APX `AxysDateRange` filtering compare
the lower and upper requested bounds with each source period's `thru_date`.

The diagnostic example:

```text
requested from_date: 2024-02-15
source period:        2024-02-01 through 2024-02-29
result:               period retained
```

The implementation therefore treats `from_date` as the earliest period end date to
retain, not the earliest source `from_date` permitted in output. The internal
`Performance._filter_date_range()` docstring already describes the lower bound as the
"Earliest period thru date to retain," while public constructor and demonstration
documentation use phrases such as "earliest from date" and "inclusive reporting
window."

### Recommendation

Preserve period-end selection and correct the public descriptions.

Rationale:

- A performance return is an indivisible observation associated with its reporting
  endpoint; ppar cannot calculate a partial-period return from a bound inside it.
- Generic and Axys/APX sources already use the same endpoint rule.
- Existing fixed-frequency and partial-period behavior was built around endpoint
  selection.
- Changing to source-start filtering would change selected financial history, while
  correcting the documentation removes the inconsistency without inventing a new
  partial-period policy.

The public contract should say that `from_date` is the earliest period `thru_date` to
retain and `thru_date` is the latest period `thru_date` to retain. Examples should
show what happens when a bound falls inside a source period.

Alternative requiring approval: change the lower bound to compare with each period's
actual `from_date`, which would omit a period beginning before the requested bound.

Decision: **Accepted. Preserve endpoint-based filtering and correct the public
documentation.**

## Contract 2: Axys/APX source dictionaries contain only source structure

### Current behavior

`AxysSpecification._SUPPORTED_ROOT_KEYS` accepts ten plausible analysis settings that
no Axys/APX implementation reads:

- `annual_minimum_acceptable_return`
- `annual_risk_free_rate`
- `benchmark`
- `confidence_level`
- `currency_symbol`
- `frequency`
- `holidays`
- `portfolio`
- `portfolio_value`
- `source`

A runtime diagnostic added each key with an arbitrary object value to the standard
Axys/APX settings. `AxysData.from_values()` accepted every one. A source scan found
each quoted key only in `axys_apx/specification.py`, proving that acceptance does not
affect loading or analytics.

Three additional root values are read as hidden defaults:

- `from_date`
- `thru_date`
- `classification`

The generated Axys/APX tutorial does not use these defaults. It passes its analysis
dates and classification explicitly.

### Recommendation

Make the Axys/APX dictionary source-only. Retain only settings that describe files,
columns, mappings, classifications within the supported source contract, and security
identity. Reject all ten ignored analysis keys. Also remove the hidden date and
classification defaults so portfolio, benchmark, dates, classification, frequency,
holidays, and risk assumptions remain visible in the executable Python workflow.

This aligns the behavior with the YAML-free design: source description lives in one
ordinary dictionary, and analysis choices live in ordinary Python arguments.

Decision: **Accepted. Axys/APX source dictionaries will be source-only.**

## Contract 3: Duplicate classification and mapping policy

### Current behavior

- Generic two-column classification and mapping sources use `keep="last"`.
- Inferred classification items use deterministic chronological and portfolio-first
  precedence.
- Axys/APX classification loading uses `keep="any"`.
- Combined Axys/APX portfolio/benchmark classification data uses `keep="any"`.

The generic diagnostic input:

```text
A, First
A, Second
```

silently resolved to `A, Second`. The Axys/APX `keep="any"` paths do not define which
conflicting row survives.

### Recommendation

- Accept exact duplicate pairs because they carry no contradictory information.
- Reject an identifier mapped to conflicting display names or destinations.
- Apply the same rule to CSV and Polars sources, generic and Axys/APX loading, and
  portfolio/benchmark source combination.
- Include identifiers and conflicting values in a contextual `PparError`.
- Do not use row-order precedence to resolve financially material mapping conflicts.

Decision: **Accepted. Identical pairs may repeat; conflicting values are errors.**

## Contract 4: Supported Axys/APX classification language

### Current documented contract

The generated workflow documents three configurable Axys/APX files:

- `portperf.csv`
- `secperf.csv`
- `secmast.csv`

It supports exact site-specific file paths and column mappings. The demonstrated
security identity combines security type and symbol. Classification mappings identify
the security-master columns containing a classification code and display name.

### Additional implemented behavior

The implementation and tests also support:

- separate classification files;
- classification filters;
- `source_path_overrides` outside the source dictionary;
- explicit security-master-backed classification definitions;
- external classifications joined through mappings;
- mapping-backed synthesized classifications;
- classification display-name overrides; and
- explicit global and per-dataset composite security-ID definitions.

These features are tested and are therefore not dead, but most have no user-facing
schema or example.

### Recommendation

Adopt the smallest source contract that accommodates real site differences:

- Retain `portperf.csv`, `secperf.csv`, and `secmast.csv` with configurable paths and
  exact column mappings.
- Retain classification code/display-name mappings sourced from `secmast.csv`.
- Retain configurable composite security identity, including per-dataset source
  columns, because sites can require something other than the demonstrated defaults.
- Retain mapping-backed synthesized classifications because that is how the focused
  three-file workflow obtains grouping names.
- Remove separate external classification files, classification filters,
  `source_path_overrides`, and parallel explicit classification definitions unless a
  concrete supported Axys/APX export requires them.

This recommendation keeps necessary site adaptation while eliminating the hidden
general-purpose classification configuration language. The generic `Analytics` API
remains available for users who need independent classification and mapping files.

Decision: **Accepted. Retain the focused three-file workflow and necessary site
adaptation; remove unsupported general-purpose classification branches.**

## Contract 5: Supported public Python surface

### Current baseline

The root package exports exactly:

```text
Analytics
__version__
```

`ppar.axys_apx` exports:

```text
AxysClassificationSources
AxysData
AxysPortfolio
AxysSpecification
```

The primary constructor currently allows every `Analytics` option to be positional.
The documented lower-level workflow also exposes report enums, risk arrays,
publication helpers, errors, and output-schema constants. Other importable modules
expose implementation classes and helpers without one explicit support boundary.

### Recommendation

Treat these as supported:

- Root: `Analytics`, `__version__`.
- `ppar.attribution`: `Attribution`, `Chart`, `View` and their documented output
  methods.
- `ppar.frequency`: `Frequency`. Calendar helpers remain package-internal unless a
  documented external use case is established.
- `ppar.risk`: `RiskStatistics` and its documented output methods.
- `ppar.publication`: `atomic_output_directory`, `write_report_bundle`.
- `ppar.axys_apx`: `AxysData`, `AxysPortfolio`, and
  `AxysClassificationSources` where it is the explicit bridge to attribution.
- `ppar.errors`: `PparError`.
- `ppar.schema`: documented output column constants needed to select and inspect
  public Polars results.

Treat these as internal or remove them when no production use remains:

- `AxysSpecification`;
- `Performance`, `Classification`, and `Mapping` construction;
- `Performance.reset_narrow_df()`;
- `Analytics.classification_names()` if no supported workflow needs it;
- `ppar.tables.HtmlTable` unless `to_table()` is retained and documented;
- `ppar.utilities` path, normalization, tolerance, and linking helpers;
- internal chart-rendering functions; and
- CLI setup implementation functions beyond the installed command.

Keep only the portfolio and optionally benchmark positional in `Analytics`; make
names, classifications, dates, frequency, holidays, and risk assumptions keyword-only.

Decision: **Accepted. Adopt the listed explicit support boundary and internalize the
remaining accidental surface when later phases prove it unused.**

## Contract 6: The 1,010-row HTML boundary

### Current behavior

`Attribution.to_html()` and `Attribution.to_table()` reject 1,011 or more rows. The
error reports only the view and row count. The test calls 1,010 the documented limit,
but normal user documentation does not state it or explain alternatives.

The current threshold is low enough that a monthly one-year security report can fail
at roughly 85 holdings.

### Local generation evidence

The current table renderer was measured directly with the established subperiod-
attribution layout. Each row contains the normal 16-column report shape.

| Rows | Median HTML generation | UTF-8 output size |
| ---: | ---: | ---: |
| 100 | 0.0014 seconds | 0.11 MB |
| 1,010 | 0.0139 seconds | 1.08 MB |
| 1,011 | 0.0138 seconds | 1.08 MB |
| 2,000 | 0.0271 seconds | 2.13 MB |
| 5,000 | 0.0686 seconds | 5.31 MB |
| 10,000 | 0.1379 seconds | 10.62 MB |

These are diagnostic measurements, not a permanent performance gate. They measure
server-side string generation, not browser layout, navigation, memory, printing, or
accessibility.

### Recommendation

Treat 1,010 as a provisional implementation limit rather than a confirmed long-term
product contract. Preserve it unchanged while Phase 7 gathers browser-level evidence.
The preferred KISS outcome is no arbitrary product cap if representative large tables
remain usable. If browser evidence supports a genuine bound, propose an evidence-based
limit and an actionable error naming the limit and Polars or CSV alternatives.

This is an established threshold. Phase 0 does not authorize changing it. Any later
proposal to remove it or substitute another value must state the current value,
proposed value, browser evidence, and tradeoff and receive separate explicit user
approval.

Decision: **Accepted as provisional. No threshold change is authorized. Phase 7 must
collect browser evidence and request separate explicit approval.**

## Contract 7: Risk-statistic labels

### Current output

The standard risk table contains 26 statistic labels. Three contain inconsistent or
incorrect terminology:

```text
Quarterly M_Squared
Quarterly Jensens Alpha
Annualized Jensens Alpha
```

These are row values rather than added output columns, but they are still observable
report and CSV content.

### Recommendation

Because the project has no users, correct the labels in the next release:

```text
Quarterly M-Squared
Quarterly Jensen's Alpha
Annualized Jensen's Alpha
```

Use ASCII `M-Squared` rather than `M²` for consistent HTML, terminal, and CSV output.
Update regression baselines and documentation deliberately. Do not characterize the
change as purely internal.

Decision: **Accepted. Correct the three statistic labels in the next release.**

## Public report choices baseline

### Views

```text
CUMULATIVE_ATTRIBUTION = Cumulative Attribution
OVERALL_ATTRIBUTION = Overall Attribution
SUBPERIOD_ATTRIBUTION = Sub-Period Attribution
SUBPERIOD_SUMMARY = Sub-Period Summary
```

### Charts

```text
CUMULATIVE_ATTRIBUTION = Cumulative Attribution Effects
CUMULATIVE_CONTRIBUTION = Cumulative Contribution
CUMULATIVE_RETURN = Cumulative Returns
HEATMAP_ACTIVE_CONTRIBUTION = Active Contributions
HEATMAP_ACTIVE_RETURN = Active Returns
HEATMAP_ATTRIBUTION = Total Attribution Effects
HEATMAP_PORTFOLIO_CONTRIBUTION = Portfolio Contributions
HEATMAP_PORTFOLIO_RETURN = Portfolio Returns
OVERALL_ATTRIBUTION = Overall Attribution
OVERALL_CONTRIBUTION = Overall Contribution
SUBPERIOD_ATTRIBUTION = Sub-Period Attribution Effects
SUBPERIOD_RETURN = Sub-Period Returns
```

### Frequencies

```text
AS_OFTEN_AS_POSSIBLE = Periodic
MONTHLY = Monthly
QUARTERLY = Quarterly
YEARLY = Yearly
```

## Standard demonstration artifact baseline

Both installed demonstrations produced these 11 files in this order:

```text
security_overall_attribution.html
classification_cumulative_attribution.html
classification_overall_attribution.html
classification_overall_contribution.png
classification_overall_attribution.png
classification_subperiod_attribution.png
classification_heatmap_active_contribution.png
classification_heatmap_attribution.png
classification_cumulative_attribution.png
classification_cumulative_return.png
risk_statistics.html
```

## Public output schema baseline

Security and selected-classification attribution use the same schema for a given
view. Generic and Axys/APX demonstrations produce the same report schemas.

### `View.CUMULATIVE_ATTRIBUTION`

```text
from_date
thru_date
Portfolio_Return
Benchmark_Return
Active_Return
Cumulative_Portfolio_Return
Cumulative_Benchmark_Return
Cumulative_Active_Return
Portfolio_Contribution_Smoothed
Benchmark_Contribution_Smoothed
Active_Contribution_Smoothed
Cumulative_Portfolio_Contribution
Cumulative_Benchmark_Contribution
Cumulative_Active_Contribution
Allocation_Effect_Smoothed
Selection_Effect_Smoothed
Total_Effect_Smoothed
Cumulative_Allocation_Effect
Cumulative_Selection_Effect
Cumulative_Total_Effect
```

### `View.OVERALL_ATTRIBUTION`

```text
Classification_Identifier
Classification_Name
Portfolio_Weight
Portfolio_Return
Portfolio_Contribution_Smoothed
Benchmark_Weight
Benchmark_Return
Benchmark_Contribution_Smoothed
Active_Weight
Active_Return
Active_Contribution_Smoothed
Allocation_Effect_Smoothed
Selection_Effect_Smoothed
Total_Effect_Smoothed
```

### `View.SUBPERIOD_ATTRIBUTION`

```text
from_date
thru_date
Classification_Identifier
Classification_Name
Portfolio_Weight
Portfolio_Return
Portfolio_Contribution_Simple
Benchmark_Weight
Benchmark_Return
Benchmark_Contribution_Simple
Active_Weight
Active_Return
Active_Contribution_Simple
Allocation_Effect_Simple
Selection_Effect_Simple
Total_Effect_Simple
```

### `View.SUBPERIOD_SUMMARY`

```text
from_date
thru_date
Portfolio_Return
Benchmark_Return
Active_Return
Portfolio_Contribution_Simple
Benchmark_Contribution_Simple
Active_Contribution_Simple
Allocation_Effect_Simple
Selection_Effect_Simple
Total_Effect_Simple
```

### Risk statistics

```text
column
Portfolio
Benchmark
Difference
Category
```

No cleanup phase may add output columns. Approved label corrections affect values in
the existing `column` field, not its schema.

## Static cleanup evidence to carry into later phases

The focused warning and repository-reference scans found:

- `Attribution._audit_view()` has no callers.
- `risk.py` assigns an unused `benchmark_stddev` local.
- `axys_apx/data.py` imports unused `Any`.
- the CLI contains an unreachable non-`setup` branch;
- security-identity parsing contains an unreachable string file-definition branch;
- financial normalization and sample-row formatting are substantially duplicated
  between Axys/APX performance loading and reconciliation;
- smaller identity validation is duplicated between Axys/APX performance and
  classification loading; and
- the existing routine Pylint `--errors-only` invocation does not run the configured
  warning-level checks that identify these issues.

These findings are implementation inputs for later phases. Phase 0 makes no changes.

## Confirmed decision checklist

1. Preserve period-end selection and document `from_date` as the earliest period
   `thru_date` to retain.
2. Make Axys/APX source dictionaries source-only and remove ignored and hidden
   analysis defaults.
3. Accept identical duplicate pairs but reject conflicting names and mappings.
4. Narrow Axys/APX classification support to the focused three-file contract plus
   necessary site column, mapping, and composite-security-identity configuration.
5. Adopt the explicit supported public surface listed above and internalize the rest
   when later phases prove it unused.
6. Treat the 1,010-row HTML limit as provisional, gather browser-level evidence in
   Phase 7, and require a separate explicit approval before removing or changing it.
7. Correct `M_Squared` and `Jensens Alpha` labels in the next release.

The user confirmed all seven decisions on September 1, 2026. Phase 0 is complete.
