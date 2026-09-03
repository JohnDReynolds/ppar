# ppar Cleanup and Simplification Roadmap

Status: Complete; Phases 0–10 are finished  
Assessment date: September 1, 2026

Phase 0 decisions and baseline evidence are recorded in
[`ppar_cleanup_phase_0_assessment.md`](ppar_cleanup_phase_0_assessment.md).

## Objective

Simplify ppar using the principles "less is more" and "keep it simple." Remove dead
code, historical compatibility, misleading accepted inputs, hidden state, accidental
public APIs, duplicated validation, and maintenance machinery that no longer earns its
complexity.

The review found no new mathematical defect, no wholesale dead production module, and
no reason for a broad rewrite. The project is healthy. The highest-value work is to
make the behavior that remains explicit, deterministic, documented, and proportionate
to the product's actual supported workflow.

This roadmap records the complete repository review, including production code, the
public API, Axys/APX support, CLI and generated demonstrations, reports,
documentation, tests, packaging, CI, release gates, and repository assets.

## Relationship to the other roadmaps

- The completed correctness roadmap remains authoritative for financial formulas,
  period alignment, reconciliation, conservation, lineage, and numerical invariants.
- The optimization roadmap remains authoritative for measured execution-time changes.
  Cleanup work must not claim a performance benefit without measurement.
- The user-view roadmap remains authoritative for the broader first-run experience,
  report presentation, navigation, provenance, troubleshooting, accessibility, and
  licensing presentation.
- Several findings appear in more than one roadmap because they are both
  user-visible and simplification issues. Before beginning a phase, check whether the
  overlapping item has already been completed elsewhere and record that fact instead
  of implementing it twice.

## Codex execution protocol

Before executing any phase, Codex must display this prompt with that phase's
recommendation substituted for the placeholders:

> Recommended Codex setting for Phase `<N>`: GPT-5.6 Sol `<reasoning level>`.
> Please select that setting and confirm before I proceed.

Codex must wait for the user's confirmation before beginning the phase's assessment,
implementation, tests, or other repository work. This requirement applies before
every phase, including consecutive phases performed in the same Codex session. The
user may explicitly choose a higher level.

The recommendations use Medium for routine work, High for difficult cross-cutting
design or behavior work, and Extra High for exceptionally difficult financial,
numerical, or invariant work with interacting edge cases. No phase in this roadmap
currently warrants Extra High or Ultra because financial defects belong in the
correctness roadmap and threshold changes require separate approval.

## Working rules

- Prefer deletion, explicit behavior, and ordinary Python over new abstraction.
- Do not split a cohesive module merely because it is large.
- Do not turn small duplicate snippets into a general framework.
- Write or update focused tests before changing observable behavior.
- Do not weaken, raise, disable, or bypass a test, benchmark, tolerance, invariant,
  warning threshold, or release gate without the user's explicit approval.
- Do not add columns to output files.
- Treat report names, report order, machine-readable schemas, and financial results as
  stable unless the phase explicitly identifies and obtains approval for a contract
  change.
- Use `None` as the preferred omission sentinel at public Python boundaries.
- Prefer rejecting contradictory or ambiguous data over silently choosing one value.
- Preserve inexpensive production financial and reconciliation audits.
- Run focused tests after each item and the complete test and static-analysis suite
  after every implementation phase.
- Run both generated demonstrations after changes to setup, templates, publication,
  public APIs, or Axys/APX loading.
- Run the unchanged 500x scale check after cross-cutting core, Axys/APX, reporting,
  audit, safety-net, or performance changes.
- Do not alter the user's unrelated or pre-existing working-tree changes.

## Review baseline

The review covered the current working tree, including its uncommitted fixture and
Axys/APX cleanup. It found no entire tracked production file that was obviously dead.

The non-mutating validation baseline was:

- 323 tests and 317 subtests passed.
- Mypy reported no issues in `src/ppar` or `scripts`.
- Pyright reported no errors, warnings, or information messages in `src/ppar` or
  `tests`.
- The existing Pylint errors-only gate passed.
- A focused Pylint warning scan found one unused import, one unused variable, and
  substantial duplicate Axys/APX financial validation.
- `git diff --check` passed.

The complete build, README-image, wheel, demonstration, and release-candidate gates
were not rerun during the report-only review because some of them mutate generated
checkout artifacts. Phase 0 must establish a clean implementation baseline before
changes begin.

## Overall assessment

ppar's core calculation design, narrow root API, generated tutorial workflow, strict
input validation, financial audits, and scale protection are strengths. Cleanup
should concentrate on places where the project currently appears to support more
than it actually does or where old decisions remain encoded after their workflow was
removed.

The most consequential findings are:

1. Axys/APX source settings accept ten plausible analysis values that are ignored.
2. `from_date` is documented as a period-start bound but is implemented as a
   period-end selection bound.
3. Duplicate classification names and mappings are resolved inconsistently and can
   be arbitrary.
4. Direct risk-array reports expose sentinel dates.
5. HTML attribution has a poorly exposed 1,010-row limit.
6. Atomic publication is rollback-safe for ordinary exceptions but is not fully
   interruption- or crash-atomic.
7. Historical compatibility, hidden Axys attribution state, parameterized caching,
   and broad accidental APIs add complexity before users exist.

## Phase map

| Phase | Focus | Principal findings |
| --- | --- | --- |
| 0 | Confirm contracts and baseline | Scope, support boundary, thresholds, evidence |
| 1 | Make accepted inputs truthful | Ignored Axys keys, date-window semantics, duplicate policy |
| 2 | Remove dead and historical compatibility code | Dead functions, branches, sentinels, error-code residue |
| 3 | Simplify Axys attribution flow | Hidden attached sources and implicit defaults |
| 4 | Simplify attribution caching and orchestration | Content hashing, cache identity, frequency helper ownership |
| 5 | Consolidate Axys validation | Duplicated numeric and identity validation |
| 6 | Define and narrow the supported API | Axys configuration scope, exports, utilities, keyword-only APIs |
| 7 | Correct report and output boundaries | Risk dates, titles, HTML cap, atomic publication, bundle validation |
| 8 | Simplify tests and routine gates | Tombstones, path fallbacks, brittle source inspection, lint coverage |
| 9 | Simplify packaging, CI, and documentation assets | Wheel smoke, checkout mutation, compatibility duplication, images |
| 10 | Integrated validation and documentation | Full gates, demonstrations, API examples, final support contract |

## Phase 0: Confirm contracts and establish the baseline

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 1, 2026)

This phase should contain no production changes. Record decisions that later phases
must not infer independently.

### Decisions to record

1. Decide whether `from_date` means the earliest period start or the earliest period
   end to retain. Record examples involving a bound inside a reporting period.
2. Confirm that an Axys/APX source dictionary should contain only source structure:
   files, columns, mappings, classifications, and security identity. The recommended
   direction is to keep portfolio, benchmark, dates, frequency, holidays, and risk
   assumptions as explicit analysis arguments.
3. Define the duplicate policy for classification names and mappings. The
   recommended rule is to allow identical duplicate pairs and reject conflicting
   values for the same identifier.
4. Decide whether the advanced Axys/APX classification language is an officially
   supported feature or implementation residue beyond the three-file demonstration
   contract.
5. Define the supported public Python surface. The recommended starting point is the
   documented root API plus deliberately documented types in `ppar.attribution`,
   `ppar.frequency`, `ppar.risk`, `ppar.publication`, and `ppar.axys_apx`.
6. Decide whether the 1,010-row HTML boundary remains a supported product limit. Do
   not change it without recording the current value, proposed value, performance
   evidence, and tradeoff and obtaining explicit user approval.
7. Decide whether output statistic-label corrections are allowed in the next release
   or must remain compatible.

### Baseline evidence

- Record `git status` without altering existing work.
- Run the complete test suite, Mypy, Pyright, and the intended Pylint checks.
- Run the routine product gate, both generated demonstrations, wheel smoke test, and
  unchanged 500x scale gate from an appropriate clean baseline.
- Record public imports, constructor signatures, report filenames, report order,
  output schemas, statistic labels, and standard demonstration artifacts.
- Record current Axys/APX accepted root keys and prove which are read.
- Record current date-bound examples and duplicate-resolution behavior.
- Add no fixes during this phase.

## Phase 1: Make accepted inputs truthful and deterministic

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 1, 2026)

### Item 1: Reject ignored Axys/APX root settings

The Axys specification currently accepts these top-level values without using them:

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

Tests:

- Parameterize every ignored key with a plausible nondefault value.
- Demonstrate that the current implementation accepts each key before the fix.
- After the fix, require a contextual `PparError` identifying unsupported keys.
- Confirm that documented source-only keys remain valid.

Fix direction:

- Remove ignored values from `_SUPPORTED_ROOT_KEYS`.
- Do not retain them as no-op compatibility settings because no users depend on them.
- If Phase 0 confirms a source-only dictionary, also remove the hidden root defaults
  `from_date`, `thru_date`, and `classification`; delete their properties and pass
  analysis choices explicitly.

Acceptance criterion: every accepted setting influences behavior, and every unknown
or retired setting fails early.

### Item 2: Align date-bound naming, documentation, and behavior

Current `Performance` and Axys/APX filtering compare both requested bounds with each
period's `thru_date`. For example, `from_date=2024-02-15` retains a February 1 through
February 29 period.

Tests:

- Cover a lower bound before, at, and inside a reporting period.
- Cover the equivalent generic CSV, Polars DataFrame, and Axys/APX paths.
- Cover native and fixed frequencies, partial terminal periods, and no-bound
  sentinels.
- Assert documentation and method docstrings use the selected contract's exact terms.

Fix direction:

- Implement the Phase 0 decision consistently in `Performance`, `AxysDateRange`,
  `Analytics`, `AxysData`, both generated scripts, and configuration documentation.
- Do not silently change financial reporting-window behavior under a documentation-
  only cleanup.

### Item 3: Reject conflicting duplicate names and mappings

Generic sources currently keep the last duplicate identifier. Axys/APX sources use
`keep="any"` both while loading and while combining portfolio and benchmark
classification sources.

Tests:

- Accept identical duplicate identifier/name and identifier/destination pairs.
- Reject conflicting display names and mapping destinations.
- Cover generic CSVs, generic Polars DataFrames, explicit Axys classifications,
  security-master mappings, and combined portfolio/benchmark sources.
- Shuffle source rows and require the same result or the same error.

Acceptance criterion: row order and Polars' arbitrary duplicate selection cannot
change a classification report.

Phase gate: run the complete suite, both demonstrations, and the 500x scale check
because date and mapping behavior can affect financial output.

### Phase 1 completion record

- Axys/APX source dictionaries now accept only `files`, `classifications`,
  `mappings`, and `security_id`. The ten ignored analysis settings and the hidden
  root `from_date`, `thru_date`, and `classification` defaults fail early as
  unsupported top-level keys. Analysis dates and classification selection remain
  explicit method arguments.
- The existing financial behavior is unchanged: both generic and Axys/APX inputs
  select complete source periods by inclusive `thru_date` bounds. Public API
  docstrings, both generated demonstrations, and configuration documentation now
  state that contract and illustrate a bound inside a source period.
- Generic CSV and Polars classification/mapping sources and Axys/APX supporting
  sources now collapse exact duplicate pairs and reject conflicting names or
  destinations with contextual `PparError` details. Combined portfolio/benchmark
  classification names receive the same validation, and physical row order no
  longer selects a result.
- Focused tests cover CSV, Polars, Axys/APX, reversed source rows, exact duplicates,
  conflicts, lower bounds before/at/inside a source period, no-bound sentinels,
  native frequency, fixed frequency, and the existing partial-terminal-period
  behavior.
- The complete release-candidate gate passed: 329 tests and 355 subtests; Mypy,
  Pyright, and Pylint passed; documentation provenance passed; wheel build and
  installed-wheel isolation passed; and both installed demonstrations produced the
  expected 11-report bundles.
- The unchanged 500x gate passed. Large-site scaling remained an established warning
  at 1.08x, below the unchanged 1.10x failure threshold; selected-workload scaling
  was 1.83x, and long-history scaling was 1.40x.
- No output columns, report names, report order, financial formulas, tolerances, or
  test and benchmark thresholds changed.

## Phase 2: Remove true dead code and historical compatibility

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: Complete (September 1, 2026)

### Confirmed dead production code

Remove after focused coverage confirms no behavior change:

- `Attribution._audit_view()`, which has no callers and duplicates construction-time
  attribution auditing.
- The unused `benchmark_stddev` local in risk calculation.
- The unused `Any` import in `ppar.axys_apx.data`.
- The unreachable non-`setup` CLI command branch; argparse already rejects unknown
  commands.
- The unreachable string file-definition branch in
  `axys_apx.security_identity._source_file_columns()`; `AxysSpecification` rejects
  that shape first.
- The `prefix_portfolio_code` property if Phase 0 confirms that the one constant
  separator is the only supported behavior.
- The pure-forwarding `AxysData.from_values()` wrapper if the public constructor is
  selected as the sole construction path. Alternatively, keep `from_values()` as the
  sole documented factory and explain why direct construction remains public.

### Retire blank-string compatibility sentinels

The current API treats blank strings as omission for names, classifications,
benchmark paths, classification paths, mapping paths, labels, and sort columns. A
blank benchmark path can silently turn an analysis into portfolio-versus-itself.

Tests and fix direction:

- Use `None` as the sole omission sentinel.
- Reject blank paths and blank column names with actionable `PparError` messages.
- Decide whether blank optional display labels are invalid or normalized; apply one
  rule consistently.
- Remove `test_optional_value_contracts` cases characterized as legacy or sentinel
  compatibility, replacing them with the selected strict contract.

### Remove obsolete numeric error-code residue

- Rename the 22 remaining test methods ending in names such as
  `_raises_error_504` by the behavior under test.
- Remove `_error_code` from `_assert_axys_error()` and all 26 supplied arguments.
- Retain tests of actionable messages and structured context.
- Do not restore numeric error registries or numeric message prefixes.

Acceptance criterion: repository-wide reference and lint scans find no remaining
confirmed dead identifiers or retired numeric-error naming.

### Phase 2 completion record

- Removed all seven confirmed dead or pure-forwarding production constructs:
  `Attribution._audit_view()`, the unused risk `benchmark_stddev` local, the unused
  Axys `Any` import, the unreachable CLI and security-identity branches,
  `prefix_portfolio_code`, and `AxysData.from_values()`.
- `AxysData(...)` is now the one documented construction path for Python source
  values. The generated Axys/APX tutorial, documentation, tests, and scale tooling
  use that constructor directly.
- `None` is now the sole omission marker at public Python boundaries covered by this
  phase. Blank names, classifications, labels, sort columns, data-source paths,
  mapping paths, Axys paths, and Axys column definitions fail with actionable
  `PparError` messages instead of silently changing behavior.
- A repository-wide scan found and renamed 43 numeric-suffixed test methods, rather
  than only the 22 originally counted. The obsolete `_error_code` helper argument
  and every numeric call-site argument were removed while message and structured-
  context assertions were retained.
- Focused validation passed with 154 tests and 87 subtests. The complete product gate
  passed with 334 tests and 350 subtests; Mypy, Pyright, Pylint, documentation
  provenance, wheel build and installed-wheel isolation, and both generated
  demonstrations passed. Both installed demonstrations produced the expected
  11-report bundles.
- The unchanged 500x scale check passed in direct runs, including large-site results
  of 1.09x and 1.00x, selected-workload results of 1.80x–1.93x, and long-history
  results of 1.40x. It also showed intermittent large-site boundary failures of
  1.11x–1.12x during combined release-candidate runs and one rounded 1.10x direct
  run. Phase 2 adds only constant-time construction validation to that workflow;
  repository review found no new row-scaled calculation. The established 1.10x
  threshold and its implementation were not changed. Phase 8 records the required
  follow-up on measurement stability rather than allowing this signal to be lost.
- Repository-wide reference scans and lint scans find no remaining confirmed dead
  identifiers or retired numeric-error naming. `git diff --check` passes.
- No output columns, report names, report order, financial formulas, tolerances, or
  test and benchmark thresholds changed.

## Phase 3: Make Axys/APX attribution flow explicit

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 1, 2026)

### Current complexity

`AxysData.get_portfolios()` can load and attach classification sources to an
`AxysPortfolio`. `AxysPortfolio.to_analytics()` installs those sources as a hidden
`Analytics` default. A later parameterless `analytics.attribution()` consumes that
default.

This creates nonlocal state across four concepts: source loading, a portfolio data
container, analytics construction, and attribution selection.

### Recommended direction

Require every Axys/APX classification attribution to name its source explicitly:

```python
classification_attribution = analytics.attribution_for(
    source.get_classification_sources_for_pair(
        CLASSIFICATION,
        portfolio,
        benchmark,
    )
)
```

Assess removing:

- `classification_name` from `get_portfolio()` and `get_portfolios()`;
- attached `AxysPortfolio.classification_sources` state;
- `AxysPortfolio.required_classification_sources`;
- `default_attribution_sources` from `Analytics.__init__()`;
- `Analytics._default_attribution_sources` state and its implicit attribution branch;
- portfolio/benchmark conflict handling that exists only to combine attached hidden
  defaults.

Tests:

- Cover Security and every demonstrated classification using explicit paired sources.
- Cover portfolio-only and portfolio/benchmark workflows.
- Assert the two generated tutorials remain easy to compare and explain.
- Confirm calculations, report filenames, order, and schemas are unchanged.

Acceptance criterion: reading one attribution call is sufficient to know its
classification source without inspecting how the portfolio was loaded.

### Phase 3 completion record

- Removed `classification_name` from `AxysData.get_portfolio()` and
  `AxysData.get_portfolios()`. Portfolio loading now selects only accounts and period-
  end bounds; report classification is a separate explicit choice.
- Removed attached `AxysPortfolio.classification_sources` state,
  `required_classification_sources`, the portfolio/benchmark default-source combiner,
  `Analytics.__init__()`'s `default_attribution_sources` parameter,
  `_default_attribution_sources` state, and the implicit no-argument attribution
  branch that consumed it.
- The Axys/APX tutorial now names both report sources at their calculation sites:
  Security and the selected `CLASSIFICATION` each call
  `get_classification_sources_for_pair()` through `Analytics.attribution_for()`.
  The generic tutorial retains the equivalent explicit source arguments in its two
  attribution calls, keeping the tutorial structures easy to compare.
- Focused tests cover unmapped Security sources, mapped classifications,
  portfolio-only attribution through `get_classification_sources()`, paired
  portfolio/benchmark attribution through `get_classification_sources_for_pair()`,
  and multiple independently selected classifications from one loaded account pair.
  Tests also confirm that reconciled portfolios no longer carry classification state.
- Configuration, generated Axys/APX README, and Python API documentation now explain
  that portfolio loading and report-source selection are separate operations.
- The complete product gate passed with 334 tests and 350 subtests; Mypy, Pyright,
  Pylint, README-image provenance, wheel build and installed-wheel isolation, and
  both generated demonstrations passed. Both installed demonstrations retained the
  same ordered 11-report bundles.
- The unchanged 500x gate passed: large-site scaling was 1.02x, selected-workload
  scaling was 1.98x, and long-history scaling was 1.40x.
- No output columns, report names, report order, financial formulas, tolerances, or
  test and benchmark thresholds changed.

## Phase 4: Simplify attribution caching and core orchestration

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 1, 2026)

### Item 1: Remove the parameterized attribution cache unless evidence justifies it

The cache currently hashes complete source files and serializes complete Polars
DataFrames to construct a cache key. The standard demonstrations calculate each
requested attribution once. The cache therefore adds content hashing, invalidation
semantics, identity-reuse tests, and stored attribution state to optimize a workflow
that is not demonstrated.

Recommended direction:

- Construct and return a fresh `Attribution` for each explicit request.
- Remove `_AttributionCacheKey`, `_data_source_cache_token()`, the `_attributions`
  dictionary, and tests that require repeated calls to return the same object.
- Preserve `RiskStatistics` caching because it takes no request parameters and is
  naturally associated with one immutable `Analytics` instance.
- Retain construction-time audits on every fresh attribution.
- Update `Analytics.audit()` so its purpose remains explicit without relying on
  cached attribution objects.

Before implementing, measure a deliberately repeated attribution workflow. If a real
supported use case requires caching, record it and choose a simpler explicit cache
contract instead of preserving content-token machinery by default.

### Item 2: Give frequency algorithms one home

Move the fixed-frequency bucket-completion and coverage helpers near the existing
calendar and bucket semantics in `frequency.py`. Leave `Analytics` responsible for
orchestration rather than calendar algorithms.

Do not split `core.py`, `attribution.py`, or `risk.py` merely to reduce line counts.
Extract only cohesive responsibilities with a clearer owner.

Tests and validation:

- Preserve all period-alignment, holiday, partial-period, conservation, and
  metamorphic tests.
- Run both demonstrations and the unchanged 500x scale check.

Acceptance criterion: core orchestration becomes easier to follow without changing
financial behavior or creating a new abstraction layer.

### Phase 4 completion record

- Measured a deliberately repeated mapped attribution using the standard Axys/APX
  demonstration data before changing the cache. A cached repeat took approximately
  13 microseconds, while forced fresh construction took approximately 20.35
  milliseconds. Although the relative difference was large, the absolute cost was
  about 20 milliseconds and the documented workflows construct each requested
  attribution once, retain that object, and use it for all selected tables and charts.
  No demonstrated or documented workflow required repeated request caching.
- Removed `_AttributionCacheKey`, `_data_source_cache_token()`, complete-file hashing,
  Polars DataFrame serialization, the `_attributions` dictionary, cache lookup and
  invalidation behavior, and the test requiring repeated calls to return the same
  object. Each request now constructs a fresh independently audited `Attribution`.
- Preserved `RiskStatistics` caching because it remains one parameterless calculation
  associated with an immutable `Analytics` instance.
- `Analytics.audit()` now states and performs its remaining responsibility directly:
  auditing the aligned portfolio/benchmark `Performance` pair. Every returned
  `Attribution` continues to audit itself during construction.
- Moved fixed-frequency bucket completion and coverage-start validation from
  `core.py` to `frequency.py`, beside the bucket, endpoint, holiday, and coverage
  semantics they use. The moved helpers now accept validated date tuples rather than
  Polars DataFrames, while `Analytics` retains only alignment orchestration and user-
  facing warnings.
- Focused financial, calendar, conservation, and metamorphic validation passed with
  75 tests and 46 subtests. The complete product gate passed with 335 tests and 350
  subtests; Mypy, Pyright, Pylint, README-image provenance, wheel build and installed-
  wheel isolation, and both generated demonstrations passed. Both demonstrations
  retained the same ordered 11-report bundles.
- The first unchanged 500x run encountered the already-recorded large-site timing
  instability at a rounded 1.10x result. The identical rerun passed: large-site
  scaling was 1.05x, selected-workload scaling was 1.94x, and long-history scaling
  was 1.45x. No threshold, sample policy, workload, or gate implementation changed;
  Phase 8 retains the measurement-stability follow-up.
- No output columns, report names, report order, financial formulas, tolerances, or
  test and benchmark thresholds changed.

## Phase 5: Consolidate Axys/APX validation

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 1, 2026)

Pylint identified substantial duplicate finite-number normalization, invalid-row
selection, sample-row formatting, and contextual error construction between
`axys_apx.performance_sources` and `axys_apx.reconciliation`. Smaller identity-field
validation duplication exists between performance and classification loading.

### Implementation direction

- Extract one narrow internal helper for financial-field normalization and
  validation.
- Preserve the caller's contextual error callback and exact source/field/period
  evidence.
- Share sample-row formatting rather than maintaining parallel versions.
- Consolidate identity validation only if the same small helper naturally covers the
  cases; do not build a validation framework for a few repeated expressions.
- Keep defensive reconciliation checks even when the loader validates first. Those
  checks protect direct internal callers and financial boundaries.

Tests:

- Parameterize null, malformed, `NaN`, positive infinity, and negative infinity for
  every required and optional financial field.
- Assert the loader and defensive reconciliation boundary produce equally actionable
  context.
- Cover blank, null, and whitespace-padded identities in performance,
  classification, mapping, and security-master sources.

Acceptance criterion: there is one obvious implementation of each normalization rule
without reducing boundary defense.

### Phase 5 completion record

- Added one narrow internal `source_validation` module. Financial normalization and
  required/optional finite-value rules now have one implementation shared by source
  loading and reconciliation, while callers retain their dataset-specific error
  wording and source/field/period evidence.
- Preserved reconciliation's defensive financial validation for direct internal
  callers. Optional null weights and contributions remain accepted; null required
  returns and malformed, `NaN`, positive-infinite, and negative-infinite values remain
  rejected at both boundaries.
- Consolidated sample-row formatting, diagnostic-column selection, and the common
  null/blank/padded identity predicate. Performance and classification loaders retain
  their distinct field requirements and contextual messages, and composite security
  identity validation remains separate because its multi-column semantics differ.
- Focused Axys/APX validation passed with 92 tests and 271 subtests. The complete
  product gate passed with 338 tests and 370 subtests; Mypy reported no issues in 38
  source files, Pyright and Pylint were clean, README images were current, the wheel
  built and passed metadata and isolation checks, and both installed-wheel
  demonstrations retained the same ordered 11-report bundles.
- The unchanged 500x scale gate passed. Large-site scaling was 1.08x, within its
  existing warning band and below the unchanged 1.10x failure threshold; selected-
  workload scaling was 1.69x and long-history scaling was 1.37x.
- No output columns, report names, report order, financial formulas, accepted null
  semantics, tolerances, or test and benchmark thresholds changed.

## Phase 6: Define and narrow the supported API and Axys/APX scope

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 1, 2026)

### Item 1: Choose the official Axys/APX configuration language

The generated tutorial documents the focused three-file workflow:

- `portperf.csv`
- `secperf.csv`
- `secmast.csv`

The implementation additionally supports separate classification files,
classification filters, source-path overrides, security-master-backed and external
classifications, mapping-backed synthesized classifications, display-name overrides,
and per-dataset composite security IDs.

These branches are tested and therefore not dead, but most are undiscoverable to a
user. Choose one direction:

1. Officially support the complete language and provide a schema/reference plus
   focused examples; or
2. Standardize on the documented three-file contract and remove advanced branches
   that are not needed by actual Axys/APX exports in scope.

The recommended KISS direction is the smallest contract that accommodates known
site-to-site column and security-identity differences. Do not remove a capability
merely because it is advanced; first establish whether a real source format requires
it.

### Item 2: Narrow accidental public APIs

Assess and document or internalize:

- `AxysSpecification`, currently exported from `ppar.axys_apx` but used as an
  implementation object;
- the lazy `ppar.axys_apx.__getattr__` import machinery, which refers to optional
  imports even though the adapter has no optional dependency boundary;
- `Performance.reset_narrow_df()`, used only in tests outside production internals;
- `Analytics.classification_names()`, used by tests but absent from user guidance;
- the broad `ppar.utilities.__all__`, which declares path, tolerance, loading, and
  linking internals public;
- `Attribution.to_table()` and `RiskStatistics.to_table()`, which expose
  `ppar.tables.HtmlTable` even though `ppar.tables` is not documented as a supported
  lower-level module.

Do not reduce the deliberately small root API of `Analytics` and `__version__`.

### Item 3: Make constructor options keyword-only

- Keep the portfolio and, if desired, benchmark positional.
- Make names, classifications, dates, frequency, hidden hooks, holidays, and risk
  assumptions keyword-only in `Analytics` and `AxysPortfolio.to_analytics()`.
- Update examples and type tests.

Acceptance criterion: the public support boundary can be listed concisely, every
supported object is documented, and valid-but-misordered constructor calls are no
longer possible.

### Phase 6 completion record

- Standardized the Axys/APX configuration language on the approved focused contract.
  Its only supported top-level keys are `files`, `mappings`, and `security_id`;
  `files` is limited to portfolio performance, security performance, and security
  master data. Security-master classification mappings and global or per-dataset
  composite security IDs remain supported.
- Removed separate classification files, classification filters,
  `source_path_overrides`, explicit classification definitions, classification
  display-name overrides, and `is_security_master` configuration. The committed
  external-classification fixture was removed. The focused classification loader is
  now 349 lines, down from the 776-line baseline implementation.
- Removed `AxysSpecification` from the package surface, renamed it as an internal
  implementation object, and replaced unnecessary lazy package imports with three
  direct supported exports: `AxysClassificationSources`, `AxysData`, and
  `AxysPortfolio`.
- Removed the accidental `Performance.reset_narrow_df()`,
  `Analytics.classification_names()`, `Attribution.to_table()`, and
  `RiskStatistics.to_table()` APIs. `ppar.tables` and `ppar.utilities` are explicitly
  internal; supported public signatures use ordinary `str`, `Path`, and Polars types.
  `ppar.schema.__all__` now exposes column-name strings rather than internal grouping
  tuples and display helpers.
- Added explicit `__all__` contracts and user documentation for the supported root,
  attribution, Axys/APX, error, frequency, publication, risk, and schema surfaces.
  The root API remains exactly `Analytics` and `__version__`.
- Made every `Analytics` option after portfolio and optional benchmark keyword-only.
  `AxysPortfolio.to_analytics()` likewise keeps only its optional benchmark
  positional. Signature tests protect both contracts and the focused `AxysData`
  constructor.
- Focused validation passed with 141 tests and 105 subtests. The complete product gate
  passed with 334 tests and 397 subtests; Mypy reported no issues in 38 source files,
  Pyright and Pylint were clean, the governed README images were regenerated and
  validated, the wheel passed metadata and isolation checks, and both installed-wheel
  demonstrations retained the same ordered 11-report bundles.
- The unchanged 500x scale gate passed: large-site scaling was 1.02x, selected-
  workload scaling was 1.92x, and long-history scaling was 1.44x.
- No output columns, report names, report order, financial formulas, calculation
  behavior, tolerances, or test and benchmark thresholds changed.

## Phase 7: Correct report, title, and publication boundaries

Recommended Codex level: **GPT-5.6 Sol High**

This phase overlaps with Phases 2, 4, 6, and 7 of the user-view roadmap. Coordinate
implementation and record completed work rather than duplicating it.

### Item 1: Direct risk-array presentation

- Represent unavailable dates as absent rather than `date.min` and `date.max`.
- Omit the date clause when direct arrays do not supply dates.
- Decide whether direct arrays should accept optional names and dates.
- Document minimum sample requirements and use an example long enough for the
  advertised annualized statistics.

### Item 2: Missing-name title fallbacks

- Prevent unnamed DataFrame inputs from producing the title `" vs "`.
- Use clear `Portfolio` and `Benchmark` fallbacks or deliberately omit an empty title.
- Apply the same naming policy to attribution and risk output.

### Item 3: HTML row boundary

- If the 1,010-row limit remains, document it and make the error state the view, row
  count, limit, and alternatives such as Polars or CSV.
- If changing or removing the limit is proposed, obtain explicit approval with
  performance evidence before changing its established test.

### Item 4: Publication guarantees and interruption cleanup

- Clean staging paths on `KeyboardInterrupt`, `SystemExit`, and ordinary exceptions.
- Test failure before publication, failure while publishing, rollback, interruption,
  and successful replacement.
- Describe the implementation as rollback-safe or transactional unless process-crash
  atomicity is actually guaranteed.
- Continue to state clearly that the context replaces the entire output directory.
- Preserve the option to write reports directly without the publication context.

### Item 5: Report-bundle input validation

- Reject or deduplicate repeated `View` and `Chart` selections before writing the same
  filename twice.
- Validate iterable members and raise contextual `PparError` instead of incidental
  `AttributeError`.
- Preserve selected report order and existing filenames.

### Item 6: Small public inconsistencies

- Correct the `Attribution` docstring's repeated `HTML` and `charts` wording.
- Correct the duplicated article in the `Mapping` data-source docstring.
- Align `classification_label` documentation with its actual override semantics.
- Replace first-dot basename splitting with the Phase 0 filename contract; normally
  `Path.stem` should turn `portfolio.v2.csv` into `portfolio.v2`.
- Decide whether to correct `M_Squared`, `Jensens Alpha`, and
  `Annualized Jensens Alpha`. Treat these as established report-label changes rather
  than harmless spelling edits.
- Prevent the hardcoded development fallback version from drifting from
  `pyproject.toml`; prefer a clearly unknown development fallback such as
  `0+unknown`.

Acceptance criterion: supported presentation paths never expose implementation
sentinels or empty titles, errors identify their remedy, and publication guarantees
match the implementation.

### Phase 7 completion record

- Direct NumPy risk inputs now store unavailable dates as `None`; their HTML uses the
  explicit `Portfolio` and `Benchmark` fallbacks and omits the date clause. The
  values-only array API remains intentionally small rather than adding optional name
  and date metadata; callers use `Performance` inputs when they need that metadata.
  The API documentation now states the two-observation minimum, full-year
  annualization gates, and a complete 12-month example.
- Attribution and risk titles now use consistent `Portfolio` and `Benchmark`
  fallbacks for unnamed DataFrame inputs, preventing empty titles such as `" vs "`.
- Preserved the established 1,010-row HTML boundary without changing its test or
  threshold. Its error now identifies the requested view, actual row count, limit,
  `to_polars()` and `write_csv()` remedies, and structured diagnostic context. The
  limit and alternatives are documented in the Python API guide.
- Strengthened report-directory publication cleanup for ordinary exceptions,
  `KeyboardInterrupt`, and `SystemExit`, including rollback when publication has
  already moved the prior directory. Documentation now calls the behavior
  transactional and rollback-safe for Python failures rather than process-crash
  atomic, states that the entire destination is replaced on success, and preserves
  direct report writing as the nonreplacement option.
- `write_report_bundle()` now rejects repeated selections and wrong enum members with
  contextual `PparError` before creating output. Valid selection order, filenames,
  and the standard report bundle remain unchanged.
- Corrected the Mapping article, `classification_label` override documentation,
  multi-dot filename stems, risk labels (`M-Squared` and `Jensen's Alpha`), and the
  uninstalled development version fallback (`0+unknown`). The approved risk-label
  changes affect presentation labels only, not values or columns.
- Added focused title, row-boundary, report-selection, publication failure,
  interruption, rollback, filename, label, and version-fallback tests. The complete
  product gate passed with 343 tests and 399 subtests; static analysis, governed
  images, wheel validation, and both installed demonstrations passed with the same
  ordered 11-report bundles.
- The unchanged 500x scale gate passed twice. The confirmation run measured 1.03x
  large-site scaling, 1.95x selected-workload scaling, and 1.42x long-history
  scaling. An initial timing run produced a nonfailing 1.09x large-site warning;
  no warning or failure threshold was changed.
- No output columns, report filenames, report order, financial formulas, calculated
  values, tolerances, or test and benchmark thresholds changed.

## Phase 8: Simplify tests and routine quality gates

Recommended Codex level: **GPT-5.6 Sol High**

### Item 1: Remove historical tombstones

The project no longer needs to prove the exact pre-split state. Remove tests and
documentation checks whose sole purpose is to assert the absence of old combined
namespaces, split records, removed fixtures, retired directory names, or
`docs/reference`.

Retain the useful current-product boundary that runtime source must not import
`perfaud`.

### Item 2: Anchor test paths once

- Replace searches through `tests/data`, `../tests/data`, and `data` with paths based
  on `Path(__file__)`.
- Do the same for `tests/expected_results` and the holiday fixture.
- Move reusable builders and fixture-path functions from `tests/test_utilities.py` to
  a plainly named helper module such as `tests/helpers.py`.
- Leave tests of actual utility behavior in `test_utilities.py`.

### Item 3: Do not skip mandatory chart dependencies

Matplotlib, Seaborn, and Pillow are runtime dependencies. Missing them is a broken
installation, not an optional test condition. Remove chart-dependency skips from the
normal installed test surface.

### Item 4: Replace brittle source-string tests

Tests currently inspect function source for literals such as `pytest`, `shutil.rmtree`,
`--wheel`, and `check_scale.py`. Replace these with behavior-level helper tests and a
small explicit workflow-composition contract.

### Item 5: Make intended Pylint warnings real gates

The routine gate invokes Pylint with `--errors-only`, so configured warnings such as
duplicate code and unused arguments do not run.

Recommended direction:

- Clean or explicitly suppress intentional current warnings.
- Add a small selected warning set such as unused imports, unused variables, and
  production duplicate code.
- Do not make every Pylint refactor or design opinion release-blocking.
- Do not relax existing lint or type-checking behavior to accommodate failures.

### Item 6: Consolidate documentation policy checks

`check_project.py` and `test_package_metadata.py` duplicate active-document lists,
retired terminology, methodology phrases, and removed-directory checks. Keep one
source of truth and test it behaviorally.

### Item 7: Assess large-site timing measurement stability

Phase 2 exposed intermittent results around the unchanged large-site 500x boundary:
the same implementation produced direct results from 1.00x to a rounded 1.10x and
combined release-candidate results of 1.11x–1.12x. The scaled workload time was
comparatively stable while subprocess baseline time varied enough to determine the
outcome.

- Reproduce the distribution on an otherwise idle system and retain raw per-sample
  timings rather than only the median ratio.
- Separate workload preparation, Python/process startup, report rendering, and the
  row-scaled calculation being protected so the gate's claim is explicit.
- Determine whether the current sample count and baseline/scaled sequencing provide
  a stable measurement without weakening the product-performance requirement.
- Do not change the established 1.10x failure threshold, sample policy, workload, or
  release-candidate composition without first presenting the current and proposed
  contracts, evidence, and tradeoff and obtaining the user's explicit approval.

Acceptance criterion: tests protect current contracts rather than project history or
specific implementation text, routine lint detects simple dead code, and the 500x
gate produces a reproducible measurement of its stated performance contract.

### Phase 8 completion record

- Removed pre-split namespace, split-record, removed-fixture, retired-directory,
  retired-term, and removed-configuration tombstone tests. Retained the current
  runtime boundary that ppar must not import or package perfaud.
- Moved reusable fixture paths and DataFrame builders from `test_utilities.py` to
  `tests/helpers.py`. All data, expected-result, and holiday paths are anchored to
  `Path(__file__)`; representative regression and frequency tests pass when launched
  from `/tmp` rather than the repository.
- Removed the chart-dependency skip. Matplotlib, Seaborn, and Pillow remain mandatory
  runtime dependencies, so missing chart support now fails normally.
- Replaced `inspect.getsource()` assertions with explicit command-composition helpers,
  behavioral wheel inspection, and executable documentation-policy validation.
- Added a routine Pylint warning gate for unused imports and unused variables while
  retaining the existing Pylint error gate. Broad design opinions and existing
  intentional column-order similarities were not promoted to release blockers.
- Consolidated the active-document spine, executable examples, methodology phrases,
  and local-link validation in `check_project.py`; package tests no longer duplicate
  those policy strings or removed-directory checks.
- The large-site gate prints every raw timing sample and ratio using three decimal
  places. An opt-in `--diagnostics` mode separately reports fixture preparation,
  Python startup, and calculation-only time without changing the release result.
- The previous timing policy produced ratios from 1.035x to 1.149x on the same idle
  system, including one genuine gate failure. Five paired diagnostic samples after
  one warm-up per workspace produced medians of 1.088x and 1.093x. The complete
  evidence and proposed policy are recorded in
  [`ppar_cleanup_phase_8_timing_assessment.md`](ppar_cleanup_phase_8_timing_assessment.md).
- After reviewing the evidence and runtime tradeoff, the user explicitly approved
  changing only large-site sampling to one warm-up per workspace followed by five
  baseline-then-scaled pairs. The gate applies its unchanged 1.05x warning and 1.10x
  failure boundaries to the median paired ratio. The 500x workload, HTML equality,
  other scale scenarios, and release composition remain unchanged.
- All non-policy Phase 8 work passed the complete product gate: 335 tests and 386
  subtests, Mypy, Pyright, both Pylint levels, governed images, wheel inspection, and
  both installed 11-report demonstrations. No financial formula, output column,
  report filename, calculated result, tolerance, workload, or threshold changed.
- The final release-candidate gate passed 337 tests and 386 subtests, all static and
  packaging checks, both installed demonstrations, and the 500x scale sequence. Its
  five large-site paired ratios were 1.103x, 1.093x, 1.070x, 1.102x, and 1.091x;
  their 1.093x median correctly produced a warning under the unchanged boundaries.

## Phase 9: Simplify packaging, CI, and documentation assets

Recommended Codex level: **GPT-5.6 Sol High**

Any reduction to an established release gate requires explicit user approval after
the current and proposed coverage are stated. This phase should favor clearer claims
and removing duplicate work, not weaker validation.

### Item 1: Build without mutating the checkout

The routine wheel gate deletes root `build/` and `src/ppar.egg-info`. Build and inspect
the wheel entirely in a temporary tree or otherwise avoid changing generated paths in
the checkout.

### Item 2: Make the installed-wheel smoke claim accurate

The current smoke environment installs the wheel with `--no-deps` and injects the
development environment's site-packages through `PYTHONPATH`. It validates installed
wheel origin, package isolation, CLI setup, and both demonstrations, but it is not an
independent dependency-installation test.

Choose one:

- Install the wheel and its dependencies normally in the temporary environment; or
- Keep the injected dependency environment and describe the check narrowly as an
  installed-package workflow smoke test.

### Item 3: Assess compatibility and release duplication

The complete product gate runs on Python 3.11.9 and 3.12.1, and the release-candidate
gate repeats the complete product gate before the 500x check. Publishing then rebuilds
a wheel rather than publishing the exact artifact validated earlier.

Assess, with explicit approval before changing gates:

- running unit and type compatibility on each supported Python version;
- running image, packaging, and full demonstration acceptance once on the primary
  version;
- passing the validated universal wheel to publishing rather than rebuilding it; and
- retaining the unchanged 500x check in the release-candidate workflow.

### Item 4: Make the Python support claim testable

`requires-python = ">=3.11.9"` promises an open-ended set of newer Python versions,
while CI currently tests 3.11.9 and 3.12.1. Test additional supported versions or
state the tested/support policy more precisely.

### Item 5: Narrow README-image provenance

The renderer fingerprints every Python, CSV, Markdown, YAML, and `py.typed` file under
`src/ppar`. Unrelated Axys/APX or documentation changes therefore mark all 12 images
stale even when their pixels do not change.

Recommended direction:

- Fingerprint only the renderer's actual transitive code, data, template, dependency,
  and layout inputs, or use an explicit render-schema version that is bumped when
  needed.
- Preserve pixel and provenance validation for inputs that can actually affect an
  image.
- Do not regenerate binary assets merely to update an unrelated source fingerprint.

### Item 6: Reduce gallery rigidity and weight

- The gallery is approximately 7 MB.
- `OverallAttributionBySecurity.jpg` is approximately 4.2 MB and 8,199 pixels tall.
- Tests hardcode an exact inventory of 12 images.
- README image URLs target `main`, so an older release can display images generated by
  newer code.

Assess a representative four-to-six-image gallery, compressed or linked secondary
examples, release-matched image URLs, and tests of declared inventory rather than an
arbitrary permanent count.

Acceptance criterion: packaging and documentation checks remain strong while avoiding
checkout mutation, duplicate claims, and unrelated binary churn. The user explicitly
chose to retain the complete 12-image README gallery.

### Phase 9 progress record

- Wheel construction now uses a temporary minimal source copy and no longer deletes
  or recreates checkout `build/` or `src/ppar.egg-info`. The complete product gate
  passed, and both paths remained absent afterward.
- The installed-wheel check is now accurately named and documented as an
  installed-package workflow smoke test that reuses the verified development
  dependencies rather than independently resolving them.
- A fresh Python 3.13.1 environment passed the complete product gate with the standard
  headless Matplotlib backend: 338 tests, 386 subtests, all static checks, wheel
  inspection, and both installed demonstrations.
- The user approved the compatibility/support, validated-wheel handoff, and narrowed
  image-provenance proposals. Python support is now explicitly 3.11.9 through 3.14;
  the existing full 3.11.9 and 3.12.1 gates remain, and Python 3.13 and 3.14 gain
  runtime test jobs.
- Release candidates can retain the wheel that passed build, inspection, Twine,
  installation, and workflow checks. GitHub uploads that artifact, and publishing
  downloads the exact wheel instead of rebuilding it.
- Image fingerprints now cover the renderer, dependency declarations, top-level
  calculation/reporting modules, and generic rendering inputs rather than unrelated
  Axys/APX, CLI, tutorial-prose, and typing-marker files.
- The user rejected gallery reduction. All 12 tracked images, all 12 README references,
  the exact declared inventory gate, and the current image URLs remain unchanged.
- The final release-candidate gate passed 339 tests and 386 subtests, every static,
  image, package, and installed-workflow check, retained the validated wheel, and
  passed the unchanged 500x sequence. Root `build/` and `src/ppar.egg-info` remained
  absent after completion.

## Phase 10: Integrated validation and final documentation

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 1, 2026)

### Validation

- Run all focused and complete tests.
- Run Mypy, Pyright, and the selected Pylint warning/error policy.
- Run the routine product gate.
- Run both setup-generated demonstrations from outside the checkout.
- Build and inspect the universal wheel and execute its installed workflow.
- Run the unchanged 500x scale check.
- Verify report filenames, report order, machine-readable schemas, financial values,
  and image quality against the approved contracts.
- Verify no runtime source imports `perfaud`.
- Run repository-wide reference, dead-code, duplicate-code, and obsolete-terminology
  scans and assess each result rather than suppressing it wholesale.

### Documentation

- State the exact public Python support boundary.
- Document the selected Axys/APX source contract and remove descriptions of rejected
  behavior.
- Document date-window semantics with concrete examples.
- Document duplicate classification and mapping rules.
- Document the HTML row policy and alternatives.
- Describe publication guarantees accurately.
- Update generated tutorials and READMEs only where their supported workflows changed.
- Cross-check this roadmap against the correctness, optimization, and user-view
  roadmaps and mark overlapping items complete in one authoritative location.

### Phase 10 completion record

- The active documentation now states the exact Python 3.11.9–3.14 boundary, selected
  Axys/APX three-file contract, inclusive period-end date-window behavior with an
  inside-period example, deterministic duplicate classification and mapping rules,
  1,010-row HTML policy and Polars/CSV alternatives, and accurate transactional
  publication guarantees.
- The generated tutorials and READMEs were not changed because Phase 10 introduced no
  workflow change. The focused configuration reference is the authoritative location
  for the newly documented duplicate rules, and the product gate now protects them.
- Focused validation passed 29 tests and 6 subtests for duplicate/documentation
  behavior, then 122 tests and 243 subtests for output contracts, financial values,
  schemas, filenames, ordering, publication, images, packaging, and both workflows.
- Fresh generic and Axys/APX setup directories outside the checkout each produced the
  approved ordered 11-report bundle. The installed universal wheel repeated both
  workflows outside the checkout and contained no `perfaud` package.
- Repository-wide reference, obsolete-terminology, artifact, dead-code, and
  duplicate-code scans found no unaddressed obsolete production path. An ignored
  Finder metadata file was removed. The only duplicate-code signal was four explicit
  narrow-data column selections in the financial pipeline; these remain local and
  readable, and extracting them would introduce cross-module coupling for no useful
  simplification.
- The complete release-candidate gate passed 339 tests and 386 subtests, Mypy,
  Pyright, both selected Pylint policies, documentation and image validation, wheel
  inspection, Twine, dependency checks, and installed workflows. The retained
  validated artifact is `ppar-0.2.0-py3-none-any.whl`.
- The unchanged 500x sequence passed. The large-site ratio was 1.084x, an established
  warning below the unchanged 1.10x failure threshold; selected-workload and
  long-history ratios were 1.933x and 1.437x.
- Root `build/` and `src/ppar.egg-info` remained absent, `git diff --check` passed,
  and no output column, report name, report order, financial formula, tolerance, or
  gate threshold changed.
- The correctness roadmap remains complete and authoritative. The optimization
  roadmap remains unimplemented; CI's headless `Agg` setting is not the production
  backend optimization. The user-view roadmap now records only the automated subset
  of its integrated user-journey validation completed here.

## Findings deliberately not treated as refactoring targets

The review recommends retaining these choices unless separate evidence changes the
decision:

- The standard `src/ppar` package layout.
- The deliberately small root API.
- Self-contained, extensively commented generic and Axys/APX demonstration scripts.
- `write_report_bundle()` as the shared report-writing seam.
- Optional transactional output publication after its guarantees are clarified.
- Strict source validation and explicit `PparError` failures.
- Inexpensive financial, conservation, reconciliation, and lineage checks in normal
  production runs.
- The 500x scale gate.
- Separate vendor-neutral and Axys/APX demonstrations.
- Large but cohesive calculation modules where splitting would merely scatter logic.
- Repetition inside tutorial scripts when extracting it would make the tutorial
  harder to understand.

## Completion criteria

- Every accepted Axys/APX setting affects behavior; ignored and retired keys fail
  immediately.
- Date-bound names, documentation, tests, and filtering implement one explicit
  contract.
- Conflicting duplicate names and mappings cannot be selected arbitrarily.
- Confirmed dead functions, variables, imports, and branches are absent.
- Blank-string legacy sentinels and numeric error-code residue are removed from the
  selected public contract.
- Axys/APX attribution sources are explicit at the calculation call site.
- Attribution caching exists only if a measured supported workflow justifies it.
- Financial-field validation has one clear implementation with defensive boundary
  checks retained.
- The supported Axys/APX configuration language and public Python API are concise and
  fully documented.
- Direct-array risk output, unnamed input titles, HTML-limit errors, and publication
  guarantees are user-appropriate.
- Tests protect current behavior instead of project history or source-code spelling.
- Routine lint detects ordinary dead imports, variables, and meaningful production
  duplication.
- Build and smoke-test descriptions match what they actually validate.
- Documentation-image changes correspond to inputs that can affect the images.
- Public output schemas gain no columns, established thresholds remain unchanged
  unless separately approved, and all correctness and scale gates pass.
