# ppar Cleanup and Simplification Roadmap

Status: Complete (September 4, 2026); Phases 0–9 complete
Original assessment date: September 2, 2026
Post-v0.3.1 reassessment date: September 4, 2026
Current assessment revision: `5d5d15682b49784c26b9a6aa53756de53f54f3e9`

The previously completed roadmap is preserved as
[`ppar_cleanup_roadmap_completed_2026-09-01.md`](ppar_cleanup_roadmap_completed_2026-09-01.md).
Its phase records remain useful history, but its code references, test counts, and
several product assumptions no longer describe the current project.

## Objective

Reassess ppar after the correctness, cleanup, optimization, and user-view work and
remove recent machinery that no longer earns its maintenance cost. Apply "less is
more" and "keep it simple" without reopening established financial behavior,
weakening validation, or discarding measured performance improvements.

This is deliberately a short implementation roadmap. It does not convert every large
module or repeated test fixture into a cleanup project. A feature earns its keep when
at least one of these statements is true:

1. It supports an actual public workflow or a user-approved presentation choice.
2. It prevents a demonstrated correctness, reconciliation, audit, or packaging defect.
3. It provides a measured material performance benefit on a supported workload.
4. It is required by an established release, compatibility, or safety gate.

Code that merely made a past investigation reproducible, independently reimplements a
dependency's behavior, or repeats coverage already supplied by a stronger test should
be removed or simplified.

## Codex execution protocol

Before executing each phase, Codex must display the following prompt with the phase
number and recommendation substituted:

> Recommended Codex setting for Phase `<N>`: GPT-5.6 Sol `<reasoning level>`.
> Please select that setting and confirm before I proceed.

Codex must wait for confirmation before starting that phase, even when consecutive
phases occur in the same session. Medium is appropriate for bounded mechanical
cleanup. High is appropriate where environment behavior, lazy query plans, or several
release contracts interact.

## Working rules

- Prefer deletion or direct library behavior over a new helper layer.
- Preserve public APIs, financial results, report names and order, output schemas, and
  the selected 11-report demonstration bundle.
- Treat the documented supported surface as the compatibility contract. Any reduction
  of an importable but undocumented interface still requires an explicit phase decision
  and complete boundary validation.
- Never weaken a tolerance, invariant, warning threshold, benchmark threshold, or
  release gate merely to make cleanup pass.
- Keep the 500x scale check in the release-candidate workflow.
- Keep inexpensive financial, conservation, lineage, and explanation-reconciliation
  invariants in production.
- Preserve surrounding-whitespace normalization as user-visible behavior; simplify
  its implementation rather than reverting to rejection.
- Measure before and after when a cleanup touches startup, source loading, or report
  rendering.
- Do not introduce shared report-production infrastructure back into the tutorial
  scripts. Their direct loops are intentional.
- Run focused tests after each change and the complete appropriate gate at the end.

## Reassessment baseline

The repository was clean at commit `44dd4d1`. No production file was changed during
this assessment.

Current non-mutating evidence:

- 395 tests and 474 subtests passed in 18.97 seconds.
- The selected Pylint unused-import, unused-variable, unused-argument, and unreachable
  checks reported no findings.
- A duplicate-code scan found mostly intentional small financial fixtures and explicit
  schema selections. The material recent duplication is the standard report inventory
  and complete demonstration execution across two test modules.
- From the completed cleanup baseline `64a12ec` through the current revision, the
  repository gained 2,823 lines and removed 1,155 lines across 58 files. Most of that
  growth is tests and measurement infrastructure, not the financial engine.

The slowest current tests also identify disproportionate maintenance work:

| Area | Observed test time | Assessment |
| --- | ---: | --- |
| Two malformed-demo preservation tests | 5.41 s | Rebuild prior bundles unnecessarily |
| Both normal setup demonstrations | 2.42 s | Retain as the principal source workflow test |
| Two extra full user-journey demonstrations | 2.28 s | Duplicate the principal workflow test |
| Three backend subprocess tests | 1.51 s | Can shrink with the cache module |

These values are observations, not new thresholds.

## September 4 post-v0.3.1 reassessment

The adoption of `perfattr` after the original assessment materially changed the cleanup
boundary. The project is already substantially smaller than revision `44dd4d1`, and a
production duplicate-code scan is clean. Broad module splitting, shared fixture
frameworks, dependency removal, or presentation rewrites would add churn without an
80/20 payoff.

The remaining worthwhile work is concentrated in four places:

1. Remove dead compatibility paths and tests that preserve only deletion history.
2. Decide whether importable but undocumented `Performance`, audit, Axys override, and
   chart-sorting interfaces still earn compatibility cost.
3. Retain ppar boundary, regression, financial, workflow, and scale tests while removing
   exhaustive algorithm matrices already owned by `perfattr`.
4. Run the complete release-candidate and 500x gates after those cross-cutting changes.

The reassessment used the current working tree, including the existing correctness work.
Before Phase 6, 378 tests and 524 subtests passed in 28.08 seconds; Mypy, Pyright, focused
unused/deprecated/unreachable Pylint checks, and the production duplicate-code scan were
clean.

## Findings and decisions

### Remove now

#### Completed optimization benchmark scaffolding

`scripts/benchmark_optimizations.py` contains 470 lines and its unit tests contain
another 100. The script enforces no release threshold. It was valuable while the
optimization roadmap was being implemented, but the workloads, medians, equivalence
rules, and conclusions are now recorded in the completed optimization roadmap and its
phase reports.

Retaining a substantial second workload-construction system beside
`scripts/check_scale.py` creates more fixture and demonstration coupling than ongoing
value. A future optimization should begin with the smallest benchmark needed for that
specific question rather than preserving this broad historical harness indefinitely.

Decision: remove the benchmark script, its unit test, and its maintenance command.
Retain the optimization roadmap records and every active release or scale gate.

### Simplify while preserving behavior

#### Matplotlib cache and backend configuration

`src/ppar/_chart_environment.py` and `tests/test_chart_cache.py` total 328 lines. Most
of that code reproduces Matplotlib's own platform cache selection, explicit
`MPLCONFIGDIR` handling, directory creation, and temporary fallback.

The nine-second cold-cache finding remains valid, but it was caused by ppar's former
policy of forcing every process toward temporary storage. Matplotlib already uses a
persistent user directory when writable and creates a temporary fallback when it is
not. ppar should stop overriding cache ownership instead of maintaining a parallel
cross-platform cache policy.

The measured static-rendering benefit is separate and should remain: select `Agg`
before Matplotlib import only when the caller has not selected a backend.

Preferred outcome: delete `_chart_environment.py`, stop setting `MPLCONFIGDIR`, retain
one minimal pre-import `Agg` default, and keep only focused tests proving the default
and caller override. Phase 2 must first verify native-cache reuse and complete output
equivalence on supported environments.

#### Single-pass source text normalization

The recent surrounding-whitespace change is friendly user behavior and should stay.
Its Axys/APX implementation, however, first performs an exact filtered collection and
then conditionally performs a second normalized collection when any requested
identifier was not found.

That fallback is particularly awkward for classification mappings because an
unmapped security is valid and remains its own group. A legitimately incomplete
mapping can therefore trigger the full normalized fallback even when the file has no
padded values.

Preferred outcome: normalize the relevant text expressions in one lazy source
pipeline before filtering and collect once. Preserve filtering before materialization,
the one-scan/one-materialization scale invariant, leading-zero identities, composite
security identifiers, incomplete mappings, and bulk-account performance. Consolidate
the padded-identity tests after the implementation becomes one path rather than two.

#### Redundant acceptance and prose gates

The current suite runs complete generic and Axys/APX demonstrations in the primary
template contract, then runs two more complete demonstrations in
`test_user_journeys.py`. The latter adds useful own-data and customized-account
coverage, but those specific assertions do not require two additional 11-report
renders.

The malformed-input tests also create four successful report bundles merely to obtain
files that a subsequent failed load must leave unchanged. Pre-seeded same-named
sentinel files can prove the no-write-on-load-failure contract directly and more
clearly.

`scripts/check_project.py` additionally freezes exact tutorial and methodology prose
such as "Repeated identical pairs are collapsed." Behavioral tests already establish
the rules; executable examples, active-file checks, local-link checks, and actual
workflow tests provide stronger documentation protection than arbitrary sentence
fragments.

Preferred outcome: keep one complete source-workflow test for both setup variants,
execute each distinct Markdown Python example once, fold customized Axys account
selection into existing coverage without another full bundle, seed failure sentinels
instead of generating prior bundles, and remove editorial substring assertions.

### Keep; do not reopen without new evidence

The following recent code is comparatively large but earns its keep:

- **Large-heatmap raster annotations.** A genuine 25-year workflow exceeded the
  unchanged long-history timing boundary before this path was added. It preserves all
  annotations and helped reduce repeated ratios from as high as 1.84x to 1.41x–1.62x.
- **Exact-period consolidation shortcut.** It was approximately 46% faster on the
  measured 121,260-row already-monthly workload and has equivalence and edge-case
  tests.
- **One-time Axys/APX account partitioning.** Bulk-account usage is expected, and the
  isolated 40-account split improved from 0.545 seconds to 0.0054 seconds; complete
  loading improved about 10–14%.
- **Lightweight HTML rendering and presentation formatting.** Percentage display,
  risk assumptions, semantic table structure, responsive metadata, and removal of the
  former HTML row cap are approved user-visible behavior. Replacing the small renderer
  with a framework would add more complexity.
- **Direct demonstration loops.** The two tutorial scripts intentionally expose
  ordinary Python report selection and writing. Reintroducing a shared bundle writer
  would optimize source duplication at the expense of the user's primary tutorial.
- **Financial and reconciliation tests.** Similar fixture literals are acceptable
  when they independently protect different formulas or invariants. Do not centralize
  them merely to silence duplicate-code output.
- **The 12-image gallery and the standard 11-report bundle.** Both are explicit user
  choices.

## Phase map

| Phase | Focus | Reasoning |
| --- | --- | --- |
| 0 | Record the current reassessment and contracts | Sol High |
| 1 | Retire completed benchmark scaffolding | Sol Medium |
| 2 | Return cache ownership to Matplotlib | Sol High |
| 3 | Normalize Axys/APX source text in one lazy pass | Sol High |
| 4 | Remove redundant slow journeys and prose gates | Sol Medium |
| 5 | Integrated validation and final accounting | Sol High |
| 6 | Remove dead compatibility and archaeological residue | Sol Medium |
| 7 | Narrow undocumented compatibility surfaces | Sol High |
| 8 | Consolidate tests delegated to `perfattr` | Sol High |
| 9 | Integrated validation and final accounting | Sol High |

## Phase 0: Record the current reassessment

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 2, 2026)

This document is the Phase 0 result. It establishes commit `44dd4d1` as the immutable
assessment baseline, archives the completed prior roadmap, and records the removal,
simplification, and keep decisions above. No production or test code changed.

Acceptance criterion: later phases begin from the current project rather than stale
references to `ppar.publication`, the removed 1,010-row HTML cap, or the deleted
`docs/configuration.md`.

## Phase 1: Retire completed benchmark scaffolding

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: Complete (September 2, 2026)

Implementation evidence is recorded in
[`ppar_cleanup_phase_1_implementation.md`](ppar_cleanup_phase_1_implementation.md).

1. Confirm that no CI, release, or scale command imports or invokes
   `scripts/benchmark_optimizations.py`.
2. Remove that script and `tests/test_benchmark_optimizations.py`.
3. Remove the manual command from `docs/maintenance.md`.
4. Preserve the recorded measurements in the optimization roadmap and phase reports.
5. Run documentation checks, tests, static analysis, and `git diff --check`.

Acceptance criterion: the historical 570-line measurement harness is gone, while all
active product, release, and 500x gates are unchanged.

## Phase 2: Return cache ownership to Matplotlib

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 2, 2026)

Implementation evidence is recorded in
[`ppar_cleanup_phase_2_implementation.md`](ppar_cleanup_phase_2_implementation.md).

1. Measure a clean native Matplotlib cache run and a second process using the same
   cache on supported writable environments.
2. Verify native behavior with an explicit `MPLCONFIGDIR` and an unwritable home.
3. Replace `_chart_environment.py` with the smallest pre-import default needed to use
   `Agg` without overriding an explicit caller backend.
4. Reduce `test_chart_cache.py` to focused backend and integration behavior, or merge
   those tests into `test_charts.py` if the standalone module no longer has a subject.
5. Compare all standard PNG and HTML artifacts and rerun standard and long-history
   timings.
6. Run the unchanged 500x scale workflow because this affects report startup and
   rendering.

Stop and report before implementation if Matplotlib's native cache cannot reproduce
the current warm-process benefit in a normal writable user environment.

Acceptance criterion: ppar owns the static-output choice, Matplotlib owns its cache,
caller overrides still work, and no output or material timing regression appears.

## Phase 3: Normalize Axys/APX source text in one lazy pass

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 2, 2026)

Implementation evidence is recorded in
[`ppar_cleanup_phase_3_implementation.md`](ppar_cleanup_phase_3_implementation.md).

1. Add focused tests that count scans and collections for padded account codes,
   padded security identifiers, and a valid incomplete classification mapping.
2. Establish that normalization can remain in the optimized lazy query before account
   or security filtering.
3. Remove the exact-then-normalized fallback collections from performance and
   classification loading.
4. Retain one shared normalization helper only where it eliminates repeated behavior;
   do not create a generalized source-transformation framework.
5. Consolidate repetitive trimming tests while preserving each distinct source
   boundary and error case.
6. Benchmark the normal two-account and expected bulk-account workloads.
7. Run Axys/APX, identity, mapping, reconciliation, scale-plan, and 500x checks.

Acceptance criterion: source whitespace remains transparent to users, every source is
materialized once, incomplete mappings do not cause a second scan, and bulk-account
behavior and financial results are unchanged.

## Phase 4: Remove redundant slow journeys and prose gates

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: Complete (September 2, 2026)

Implementation evidence is recorded in
[`ppar_cleanup_phase_4_implementation.md`](ppar_cleanup_phase_4_implementation.md).

1. Retain the existing complete generic and Axys/APX setup-variant workflow as the
   authoritative 11-report template test.
2. Keep execution of the root introductory Python example and the distinct direct-risk
   example, but do not append an unnecessary full demo to either example test.
3. Cover customized Axys account codes within an existing Axys workflow or through a
   focused analytics construction rather than another full report render.
4. Replace prior-bundle construction in malformed-input tests with explicit sentinel
   artifacts and assert that source validation changes none of them.
5. Remove duplicated standard-report inventories where doing so cannot let an
   incorrect product inventory validate itself.
6. In `scripts/check_project.py`, retain active-document, local-link, executable-command,
   build, wheel, installed-workflow, and methodology behavior checks. Remove checks
   whose only contract is an exact prose fragment already backed by behavior tests.
7. Remove exact editorial-sentence assertions elsewhere when they establish no public
   behavior.
8. Compare suite duration with the 18.97-second observation; record the result without
   introducing a timing threshold.

Acceptance criterion: every distinct public journey and failure boundary remains
covered, but the suite no longer renders complete bundles merely to create test setup
or duplicate another test.

## Phase 5: Integrated validation and final accounting

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 2, 2026)

Implementation evidence is recorded in
[`ppar_cleanup_phase_5_implementation.md`](ppar_cleanup_phase_5_implementation.md).

Run and record:

- the complete test suite and subtest count;
- Mypy, Pyright, Pylint errors-only, and the selected unused-code checks;
- both generated demonstrations and their ordered 11-report inventories;
- README image validation;
- isolated universal-wheel construction, inspection, Twine check, and installed-wheel
  workflows;
- the complete unchanged release-candidate and 500x scale sequence; and
- `git diff --check` plus a clean generated-artifact review.

Report production/test lines removed, lines added, net line reduction, suite duration,
and any measured startup or source-loading changes. Reassess the keep list once, but
do not invent another cleanup phase for code that still satisfies the earning-its-keep
rubric.

Acceptance criterion: the project is materially smaller or more direct, every
supported workflow and gate passes unchanged, and the roadmap can be marked complete.

## Phase 6: Remove dead compatibility and archaeological residue

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: Complete (September 4, 2026)

Implementation evidence is recorded in
[`ppar_cleanup_phase_6_implementation.md`](ppar_cleanup_phase_6_implementation.md).

1. Remove the unused standalone `Performance` overall-result calculation, its cache,
   and its test-only adapter path.
2. Remove the unused date-formatting helper and redundant internal data-source aliases.
3. Remove tests whose only purpose is to prove that previously deleted conversion and
   mutation APIs remain absent.
4. Remove obsolete output-policy prose assertions that protect historical wording
   rather than current behavior.
5. Keep chart archaeology comments because changing `charts.py` solely for prose churn
   does not earn another generated-image change.
6. Preserve automatic financial audits, public results, schemas, report inventories,
   and every active release threshold.

Acceptance result: 67 production lines and 180 test lines were removed net. The focused
suite, complete 368-test/522-subtest suite, static analysis, README image provenance,
wheel checks, and both installed 11-report demonstrations passed.

## Phase 7: Narrow undocumented compatibility surfaces

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 4, 2026)

Implementation evidence is recorded in
[`ppar_cleanup_phase_7_implementation.md`](ppar_cleanup_phase_7_implementation.md).

1. Designate `Performance` as an internal prepared-data type behind `Analytics`. Its
   direct source-loading constructor and dependent algorithm tests were removed
   together in Phase 8, avoiding temporary private test plumbing between phases.
2. Describe the supported `Analytics` inputs directly in the Python API guide instead
   of implying that `Performance` is part of the supported surface.
3. Keep automatic inexpensive audits while removing `Analytics.audit()` and
   `Attribution.audit_attributions()` and making the remaining attribution audit
   entry point private.
4. Remove the individual `AxysData` performance-path overrides in favor of the existing
   `values["files"]` configuration.
5. Narrow `AxysPortfolio.to_analytics()` to an optional `AxysPortfolio` benchmark plus
   the frequency, holiday, and risk options exercised by the supported workflow.
6. Remove custom sorting from `Attribution.to_chart()` and the underlying heatmap
   renderer. Preserve each standard chart's established ordering and retain sorting
   on tabular Polars, HTML, and CSV output.
7. Preserve the complete documented API, automatic financial checks, financial
   results, and output schemas.

Acceptance result: the supported surface is internally consistent, normal generic and
Axys workflows are more direct, and the complete project gate passed with 367 tests and
517 subtests. The required 500x result is recorded in the implementation report.

## Phase 8: Consolidate tests delegated to perfattr

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 4, 2026)

Implementation evidence and the test-ownership map are recorded in
[`ppar_cleanup_phase_8_implementation.md`](ppar_cleanup_phase_8_implementation.md).

1. Mapped ppar normalization, alignment, consolidation, mapping, and attribution
   edge-case tests to named `perfattr` tests before removing their duplicates.
2. Retained CSV and Polars translation, error translation, representative frequency
   and mapping integration, output schema, regression, metamorphic, user-workflow, and
   scale coverage in ppar.
3. Removed the single-source `Performance` loader and direct constructor alongside
   tests of that internal compatibility route. `Performance` containers are now
   created only from the aligned portable result used by `Analytics`.
4. Reduced the broad performance-normalization module to seven ppar-owned source and
   presentation boundary tests and removed direct internal-container tests elsewhere.
5. Left small independent financial fixtures in place where they protect distinct
   public invariants.

Acceptance result: the current `perfattr` suite passed all 240 tests, ppar's complete
product gate passed with 330 tests and 501 subtests, and the unchanged 500x scale gate
passed. The 37-test and 16-subtest net reduction is confined to mapped dependency
algorithms and unsupported internal-container contracts.

## Phase 9: Integrated validation and final accounting

Recommended Codex level: **GPT-5.6 Sol High**

Status: Complete (September 4, 2026)

Implementation evidence is recorded in
[`ppar_cleanup_phase_9_implementation.md`](ppar_cleanup_phase_9_implementation.md).

The complete release-candidate command and its composed product and 500x scale gates
passed. From revision `5d5d156` to the final integrated working tree, production,
scripts, and tests added 466 lines and removed 1,424, for a net reduction of 958 lines.
The complete suite passed 330 tests and 501 subtests; both installed workflows produced
the ordered 11-report inventory.

Acceptance result: every retained contract and unchanged gate passes, generated images
are pixel-identical to the baseline apart from refreshed provenance, the documented
supported surface matches runtime behavior, and no further cleanup phase has an
evidence-backed 80/20 case. This roadmap is complete.
