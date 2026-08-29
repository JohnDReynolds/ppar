# ppar and perfaud Repository Split Implementation Plan

## Authority

This is the implementation authority for separating the current repository
into two independent products. It defines the final product contract, code ownership,
execution sequence, acceptance gates, and hosted cutover.

There are no users requiring backward compatibility. Do not add aliases, shims,
deprecated commands, legacy configuration discovery, or overlapping namespaces.

Use the official lowercase product names everywhere: `ppar` and `perfaud`.
Capitalization is allowed only where Python or platform conventions require it, such as
`PparError`, `PerfaudError`, `PPAR_*`, and `PERFAUD_*`.

At the product boundary, `ppar` means Analytics and `perfaud` means Audit.

Use `analytics` or `audit` in another identifier only when it describes a genuine
domain concept. Use `axys_apx` only for vendor-specific behavior and `generic` only for
ppar's vendor-neutral input format. Do not create names such as `ppar_analytics`,
`generic_analytics`, or `perfaud_audit`.

## Final Outcome

| Surface | ppar | perfaud |
| --- | --- | --- |
| Purpose | Portfolio performance analytics | Portfolio performance audit |
| GitHub repository | `JohnDReynolds/ppar` | `JohnDReynolds/perfaud` |
| Local directory | `ppar` | `perfaud` |
| PyPI distribution | `ppar` | `perfaud` |
| Python namespace | `ppar` | `perfaud` |
| Console command | `ppar` | `perfaud` |
| Configuration | `ppar.yaml` | `perfaud.yaml` |
| First split release | `0.2.0` | `0.1.0` |

The final local repositories are:

```text
/Users/johnreynolds/MyStuff/Projects/ppar
/Users/johnreynolds/MyStuff/Projects/perfaud
```

Existing `ppar` releases remain immutable historical combined-product artifacts on
PyPI. The `0.2.0` release notes must state that `ppar` is now the Analytics product.

## Non-Negotiable Constraints

- Neither product may depend on or import the other.
- Do not create a third shared repository or PyPI package.
- Do not redesign financial calculations during the split.
- Do not add, remove, or rename output-file columns.
- Preserve financial values, classifications, signs, rounding, explanations, and
  artifact semantics.
- Preserve production financial, conservation, lineage, safety, and explanation-
  reconciliation invariants.
- Preserve all tolerances, row limits, benchmark thresholds, warning thresholds, and
  failure thresholds.
- Preserve both established 500x release gates.
- An unexpected gate failure is a possible regression and must be investigated.
- The only authorized release-gate removal is the sdist and wheel-from-sdist path
  documented under Packaging.
- Neither repository may rely on a neighboring checkout, shared fixture directory, or
  shared build script.
- Source history is preserved without rewriting commits.

## Final Product Contract

### Installation and Commands

Each base installation provides its complete supported workflow, including Axys/APX:

```text
python -m pip install ppar
python -m pip install perfaud
```

There are no product, source, Analytics, or Audit extras.

The complete user command surface is:

```text
ppar setup WORKSPACE
ppar setup WORKSPACE --generic
ppar run [WORKSPACE]

perfaud setup WORKSPACE
perfaud run [WORKSPACE]
```

Bare setup means Axys/APX for both products. Only ppar accepts `--generic`, and only
during setup. Remove `--source`, `--axys-apx`, `--analytics`,
`--generic-analytics`, `ppar analytics`, and `perfaud audit`.

`run` defaults exactly to `.`. It inspects only the current directory for the product's
exact configuration filename. It does not search parents, scan alternatives, or infer
a product or source.

The run-time CLI accepts no behavior-changing option other than the optional workspace.
There are no title, report, format, date-range, output-location, policy, or verbosity
overrides. To change a run, edit the workspace configuration.

Both commands provide metadata-backed `--help` and `--version`. Exit codes are:

```text
0  success
1  expected execution, configuration, input, or validation failure
2  invalid command syntax
```

Expected product errors are concise, actionable, and traceback-free. Unexpected
programming errors are not caught and retain normal tracebacks. There is no
`--verbose` mode.

Successful setup prints only the workspace, selected source, configuration path, and
exact next command. Successful run prints only the workspace, fixed output directory,
written artifacts, and one validation-success statement.

### Workspace and Output

Setup requires an explicit destination and refuses to overwrite a nonempty or already
configured destination. It creates and validates a complete demonstration workspace
that runs successfully before users replace the inputs.

```text
my_ppar/
  README.md
  ppar.yaml
  input/
  output/

my_perfaud/
  README.md
  perfaud.yaml
  input/
    snapshot_a/
    snapshot_b/
  output/
```

No workspace contains a generated Python runner script.

Every run publishes only to `WORKSPACE/output`. Remove `output_directory` from YAML,
resolved settings, Python parameters, CLI options, templates, and documentation.
External input paths remain supported where already intentional; output is never
external or configurable.

Both products build the complete artifact set in an adjacent staging directory, run
all required checks, and replace `WORKSPACE/output` only after success. Failure removes
staging data and preserves the previous successful output byte-for-byte. Successful
replacement removes stale artifacts.

Retain descriptive artifact names such as `portfolio_audit.xlsx`,
`security_audit.html`, `source_detail.csv`, and `audit_support.zip`; here `audit`
describes the artifact. Do not change artifact schemas or columns.

### Configuration

Each product has one configuration pipeline:

```text
load YAML -> validate structure and policy -> resolve paths and settings -> run
```

YAML is loaded once. Setup, the workspace service, maintenance scripts, demos, and
tests use the same typed parsing and validation functions. CLI, calculation, and report
modules do not read YAML or apply competing defaults.

Remove the redundant top-level `analytics:` and `audit:` mappings. Configuration keys
live at the root.

The ppar shape is:

```yaml
source: axys_apx
portfolio: MEGA_ALPHA
benchmark: MEGA_BENCH
frequency: quarterly
holidays: input/holidays.csv
classification: Economic Sector

files:
  # source-specific files

mappings:
  # active mappings
```

Bare setup writes `source: axys_apx`; `setup --generic` writes `source: generic`.
Those are the only accepted source values.

The perfaud operational shape is:

```yaml
reports:
  - portfolio
  - security

outputs:
  - xlsx
  - html

snapshots:
  a:
    path: input/snapshot_a
  b:
    path: input/snapshot_b

files:
  # active input contracts

data_issues:
  # reviewed classifications
```

`ppar run` dispatches only from that field. It never infers the source from names,
columns, files, or the environment. The two source loaders retain their own validation
contracts behind the common workflow.

perfaud configuration remains fail-closed. Transaction treatment, return
reconstruction, tolerances, impact methods, suppressions, causal-attribution rules, and
other financially material policy remain explicit. Concision is not permission to
guess financial intent.

Generated YAML contains required choices and active non-default settings. Tutorials,
inactive examples, and exhaustive key documentation belong in the workspace README and
`docs/configuration.md`.

### Python API

The only root callable/type exports are:

```python
from ppar import Analytics, run
from perfaud import run
```

Both roots also expose metadata-backed `__version__`. Focused APIs are imported from
their owning modules rather than mirrored at the package root. This includes ppar's
`AxysData` and `RunResult`, and perfaud's comparison helpers, `Specification`,
`write_report_bundle`, and `RunResult`.

Each root `run(workspace=".")` is the only complete-workspace execution service. CLI
and Python execution call that service and produce the same artifact inventory.

Each product owns a frozen `RunResult` with exactly:

```text
workspace
output_directory
artifacts
```

`artifacts` is an immutable tuple in deterministic order. Returning a result means all
required validation and atomic publication completed. Do not repeat configuration,
policy, source, snapshots, or validation inventories in the result.

perfaud uses the concise focused names `Specification`, `ComparisonViews`, `settings`,
and `write_report_bundle`. Keep `audit` where it describes an actual financial audit,
artifact, finding, or validation action.

ppar keeps `Analytics` and `RiskStatistics`, but applies these idiomatic names:

```text
riskstatistics.py       -> risk.py
get_riskstatistics()    -> risk_statistics()
get_attribution()       -> attribution()
get_attribution_for()   -> attribution_for()
html_table.py           -> tables.py
format_chart.py and
_chart_rendering.py     -> charts.py
```

Polars is ppar's only public in-memory table model. Focused APIs accept CSV paths or
Polars objects and return Polars objects. Remove public dict and pandas inputs and
pandas, JSON, and XML result-conversion methods. Preserve the established workspace
HTML, PNG, and required CSV artifacts.

Refactor chart pivoting and serialization without pandas, PyArrow, or lxml. The final
ppar distribution does not depend on them. Remove each dependency only after existing
calculation, chart, table, artifact, financial, and direct-wheel gates pass. If an
unavoidable need appears, stop and revise this plan explicitly.

Replace the numeric exception registry and magic integer exception codes with:

```text
PparError(message, context=...)
PerfaudError(message, context=...)
```

Preserve actionable messages, useful context, and exception chaining. Do not remove or
change perfaud domain finding codes written into reports or evidence.

### Code Shape

Both repositories use a `src/` layout and automatic setuptools discovery. Tests use an
editable installation and never modify `sys.path` to reach checkout code.

ppar remains flat except for its CLI, Axys/APX adapter, and data-only templates:

```text
ppar/
  src/ppar/
    __init__.py
    attribution.py
    charts.py
    classification.py
    config.py
    core.py
    errors.py
    frequency.py
    mapping.py
    performance.py
    risk.py
    schema.py
    tables.py
    utilities.py
    workspace.py
    cli/{__init__.py,run.py,setup.py}
    axys_apx/
    templates/{axys_apx,generic}/
    py.typed
  docs/
  scripts/
  tests/
  pyproject.toml
```

There is no `ppar.analytics`, `common.py`, `source_files.py`, or `output.py`.

perfaud keeps only two internal package families, plus one review module:

```text
perfaud/
  src/perfaud/
    __init__.py
    config.py
    errors.py
    review.py
    specification.py
    workspace.py
    cli/{__init__.py,run.py,setup.py}
    comparison/
    workbook/
    data_issues/
    axys_apx/{__init__.py,security_identity.py,transaction_safety.py}
    templates/axys_apx/
    remaining audit domain modules at this root
    py.typed
  docs/
  scripts/
  tests/
  pyproject.toml
```

There is no `perfaud.audit`, review package, `common.py`, `source_files.py`,
`perfaud.cli.validate_config`, or `perfaud.cli.validate_bundle`.

The canonical configuration, bundle, and output-integrity functions remain callable by
the workspace service, tests, and repository scripts. Removing validator modules does
not remove automatic validation or any rule.

Template directories contain no `__init__.py`. Access them as data relative to the
top-level package through `importlib.resources`.

### Packaging

Each repository has one independent `pyproject.toml`, constraints file, CI workflow,
test runner, release-candidate runner, package-data inventory, and installed-wheel
smoke suite.

ppar metadata uses `name = "ppar"`, version `0.2.0`, an Analytics-only description,
and `ppar = "ppar.cli:main"`. perfaud uses `name = "perfaud"`, version `0.1.0`, an
Audit-only description, and `perfaud = "perfaud.cli:main"`. URLs and README metadata
point only to the owning canonical repository and product.

`pyproject.toml` is the complete build declaration. There is no explicit package list
and no `MANIFEST.in`. Runtime package data contains only `py.typed` and product-owned
workspace templates. Repository scripts, tests, deep documentation, generated output,
README images, and the other product are excluded.

Each release builds, validates, and publishes one `py3-none-any` wheel. It does not
build or upload an sdist and does not rebuild a wheel from an sdist.

The base ppar dependencies are Polars, PyYAML, NumPy, Matplotlib, Seaborn, and only
other dependencies proven necessary by the installed workflow. pandas, PyArrow, lxml,
and OpenPyXL are not ppar dependencies.

The base perfaud dependencies are Polars, OpenPyXL, PyYAML, and only other dependencies
proven necessary by the installed workflow.

The direct-wheel gate verifies exact contents, metadata, Twine validation, import
origins, dependencies, resources, setup, API, version, complete workflows, and
execution outside the checkout.

#### Authorized Gate Change

The user explicitly approved this release-gate change on 2026-08-28:

| Record | Decision |
| --- | --- |
| Current state | Build an sdist, rebuild a wheel from it, compare contents, and smoke-test both wheels. |
| New state | Build, inspect, Twine-check, install, and smoke-test one direct universal wheel; publish only that wheel. |
| Evidence | Both target packages are pure Python; wheel resources are inspected directly; all installed workflows run outside the checkout. |
| Tradeoff | Release mechanics become smaller; consumers requiring a source archive use the tagged Git repository. |

No other gate or threshold change is authorized.

### Documentation and README Images

Each repository has one documentation index, its root README, and this spine:

```text
README.md
docs/
  configuration.md
  methodology.md
  python_api.md
  maintenance.md
  images/
  reference/
```

The README owns installation, setup, run, input, output, and the shortest complete
example. The four standard documents own configuration reference, financial method,
Python API, and maintenance. Active deep design and Axys/APX evidence live under
`reference/` without becoming another index.

Remove tracked product PDFs and normal PDF-generation gates. If a printable artifact
is later required, generate it from canonical documentation without tracking an
independently maintained copy.

Delete `docs/README.md`, superseded archives, `_old` trees, handoff prompts, frozen
roadmaps, and historical duplicates after moving any still-authoritative requirement
or evidence into an active document. Git history is the archive.

Every shell and Python documentation example is executable against an installed wheel.
Configuration tables are generated or checked from canonical definitions for keys,
types, required status, defaults, and allowed values. Financial meaning and policy
rationale remain curated prose.

README marketing images are retained. Each repository has:

- only README-referenced images under `docs/images/`;
- one `scripts/render_readme_images.py`;
- product-owned packaged demonstration inputs;
- committed rendered files for GitHub and PyPI; and
- one source-fingerprint freshness check.

The README is the image inventory; there is no separate manifest or image index.
Generated images embed a fingerprint of the renderer, relevant package sources,
demonstration inputs, and pinned dependencies. The check validates that fingerprint,
image decodability and dimensions, rejects missing or unreferenced files, and verifies
canonical absolute GitHub raw URLs that render on both GitHub and PyPI. README images
are not wheel runtime data unless an installed workflow independently requires one.

## Ownership and Migration Rules

### Product Boundary

ppar owns:

- the current Analytics calculations and public `Analytics` object;
- the portfolio/benchmark Axys/APX adapter;
- vendor-neutral and Axys/APX workspaces;
- performance, classification, mapping, chart, table, and risk tests and fixtures; and
- its charts, README images, demos, and documentation.

perfaud owns:

- the current Audit calculations, comparisons, reports, workbooks, bundles, and
  integrity checks;
- snapshot loading, transaction safety, security identity, and Axys/APX contracts;
- transaction, holding, reconstruction, currency, conservation, lineage, safety, and
  explanation-reconciliation tests and fixtures;
- the full Audit evidence and Axys/APX reference corpus; and
- its report image, operational demos, and documentation.

Neither product imports the other's implementation. The small
`security_identity.py` boundary is duplicated with equivalent focused contract tests.
Do not introduce a dependency to avoid that duplication.

perfaud's operational demo generator must stop reading ppar's Generic template. Copy
the required canonical seed rows into `scripts/operational_demo_data/seeds/` and prove
the generated tracked data is unchanged.

### Non-Obvious Source Moves

Routine Analytics modules move from `ppar/analytics/<name>.py` to
`src/ppar/<name>.py`. Routine Audit modules move from `ppar/audit/<name>.py` to
`src/perfaud/<name>.py`. Apply these exceptions:

| Current source | Final source |
| --- | --- |
| `ppar/analytics/cli.py` | `ppar.config`, `ppar.workspace`, and thin CLI modules |
| `ppar/analytics/riskstatistics.py` | `ppar/risk.py` |
| `ppar/analytics/html_table.py` | `ppar/tables.py` |
| `ppar/analytics/format_chart.py`, `_chart_rendering.py` | `ppar/charts.py` |
| ppar output conversions | Owning table, chart, or workspace module; delete `output.py` |
| `ppar/audit/cli/site_report.py` | `perfaud.workspace` and thin CLI `run.py` |
| Audit configuration validation and run settings | `perfaud.config` |
| `ppar/audit/performance_comparison/` and runner views | `perfaud/comparison/` |
| `ppar/audit/review_glossary.py`, `review_keys.py`, `review_model.py` | one `perfaud/review.py` |
| `ppar/audit/workbook.py`, `workbook_*.py` | `perfaud/workbook/` |
| Audit validator CLI modules | delete after callers use canonical functions |
| `common.py`, `source_files.py` behavior | focused configuration, workspace, loader, or domain owner |

Keep `ppar/utilities.py` only for cohesive financial utilities; do not turn it into a
miscellaneous replacement for removed catch-all modules.

### Tests and Fixtures

Move a focused test or fixture with the product behavior it verifies. Split mixed tests
instead of copying them whole. Each repository owns its metadata, CLI, setup, package,
project-runner, release-runner, scale-runner, documentation, and README-image tests.

Small Axys/APX fixtures may be duplicated when both products need them. No test imports
from or opens a neighboring checkout. Every patch target, resource path, command,
workspace name, and module import uses the final owning namespace.

## Five-Phase Execution

### Phase 1: Baseline and Create the Second Lineage

1. Commit this plan and begin from a clean worktree.
2. Record the current commit, versions, public exports, CLI behavior, YAML shapes,
   workspace contents, package contents, and dependency inventory.
3. Generate representative ppar and perfaud artifacts. Record schemas, file names,
   financial values, and rendered outputs needed for regression comparison.
4. Run the complete current project and release-candidate gates, including both 500x
   checks. Document any pre-existing failure.
5. Build and retain the current wheel for negative namespace and coexistence tests.
6. Clone the full repository history to
   `/Users/johnreynolds/MyStuff/Projects/perfaud`.
7. Remove the inherited origin from the perfaud clone before making external changes.

Exit: both lineages share a known baseline, perfaud cannot push to the ppar remote, and
all behavior and release evidence needed for comparison is recorded.

### Phase 2: Complete perfaud Locally

1. Move Audit code into the final `src/perfaud` shape and remove ppar runtime, tests,
   templates, assets, and metadata.
2. Establish the canonical configuration pipeline, fixed workspace contract,
   `perfaud.run()`, minimal `RunResult`, atomic publication, and thin CLI.
3. Merge review modules, simplify exceptions, remove catch-all and validator modules,
   and apply focused public renames.
4. Move templates to data-only package resources and create a valid-by-construction
   Axys/APX setup workspace without a runner script.
5. Decouple operational demo inputs from ppar.
6. Move and simplify perfaud tests, fixtures, documentation, README images, packaging,
   project gates, release gates, scale runner, and CI.
7. Build and inspect the universal wheel and run the complete perfaud acceptance gate
   with the ppar checkout unavailable.

Exit: perfaud independently satisfies every applicable final-product and acceptance
contract using an editable install and its direct wheel.

### Phase 3: Complete ppar Locally

1. Remove perfaud code, tests, templates, assets, and metadata from the current
   lineage.
2. Move Analytics code into the final flat `src/ppar` shape and apply the approved
   idiomatic module and method names.
3. Establish one configuration pipeline and workspace service for both explicit source
   values, fixed output, minimal `RunResult`, atomic publication, and thin CLI.
4. Implement bare Axys/APX setup and the single `--generic` alternative; remove every
   other source or product command form.
5. Normalize focused table APIs on Polars, refactor charts and serialization, remove
   catch-all modules and unused dependencies, and simplify exceptions.
6. Move templates to data-only resources and make both setup variants valid by
   construction without runner scripts.
7. Move and simplify ppar tests, fixtures, documentation, README images, packaging,
   project gates, release gates, scale runner, and CI.
8. Build and inspect the universal wheel and run the complete ppar acceptance gate with
   the perfaud checkout unavailable.

Exit: ppar independently satisfies every applicable final-product and acceptance
contract using an editable install and its direct wheel.

### Phase 4: Independent Acceptance and Coexistence

1. Run both complete product gates and both 500x gates again.
2. Compare final artifacts, schemas, financial results, charts, tables, workbooks, and
   reports with the Phase 1 baseline.
3. Install both candidate wheels into one clean environment.
4. Run both setup variants for ppar and the perfaud setup, then run every workspace.
5. Run `pip check`, inspect module origins, and prove neither product imports or
   packages the other.
6. Confirm all documentation examples and README-image drift checks pass from their
   owning repositories.
7. Rename the current checkout to
   `/Users/johnreynolds/MyStuff/Projects/ppar`, recreate path-bound environments, and
   repeat the product gates.

Exit: both local repositories pass independently and coexist without namespace,
command, dependency, resource, or artifact collisions.

### Phase 5: Hosted Cutover and Publication

Perform this phase only with the external authorizations listed below.

1. Rename `JohnDReynolds/portfolio-performance-analytics` to
   `JohnDReynolds/ppar` and update the ppar origin.
2. Create `JohnDReynolds/perfaud`, set its visibility, and add it as perfaud's only
   origin.
3. Do not push historical ppar release tags to perfaud. Begin perfaud tags at
   `v0.1.0`.
4. Update metadata, badges, README image URLs, branch protection, and Trusted
   Publishing for each independent repository.
5. Recheck that the `perfaud` PyPI name is claimable.
6. Publish and smoke-test the `perfaud==0.1.0` universal wheel first.
7. Publish and smoke-test the `ppar==0.2.0` universal wheel.
8. Install both public wheels together and repeat coexistence acceptance.
9. Tag the exact passing commits. Never replace a PyPI file; correct a bad release with
   a new patch version.

Exit: both canonical repositories and PyPI packages match their passing local
candidates and operate independently and together.

## Acceptance Contract

### Routine Product Gate

Each repository's `scripts/check_project.py` runs, at minimum:

1. Product tests.
2. Mypy over the product package and retained scripts.
3. Pyright over the product package and tests.
4. Pylint error checks over the product package, scripts, and tests.
5. Configuration-reference and executable-documentation drift checks.
6. README-image inventory, source-fingerprint, format, dimension, and decode checks.
7. Direct universal-wheel exact-content and Twine checks.
8. Editable-install and installed-wheel import-origin, dependency, resource, setup,
   API, version, CLI, and complete-workflow smokes outside the checkout.

CI runs the product gate independently on Python `3.11.9` and `3.12.1` without checking
out the other repository.

### Financial and Scale Gates

- ppar retains its established 500x workload and thresholds.
- perfaud retains its established 500x workload, financial/output equivalence checks,
  100x timing reference, 5.25x warning boundary, and 5.50x failure boundary.
- Rename perfaud's copied baseline to `scripts/scale_baseline_500x.json` without
  changing recorded values.
- Retain the production report row limit and larger-input stress behavior.
- Run the owning 500x gate after major namespace, reporting, safety, or performance
  work and in the final release candidate.

### Final Acceptance Matrix

| Area | Required evidence |
| --- | --- |
| Identity | Final repository, distribution, namespace, command, configuration, URLs, and versions use only `ppar` or `perfaud`. |
| Independence | Each checkout passes with the other absent; neither wheel contains, imports, or depends on the other. |
| Installation | Base wheels install without extras and provide every documented Axys/APX workflow plus ppar's Generic setup. |
| CLI | Only the approved setup/run/help/version surface exists; exact exit and error behavior passes. |
| Workspace | Setup is valid by construction, input layout is standard, no runner script exists, and run defaults only to `.`. |
| Configuration | YAML loads once through one typed pipeline; ppar source is explicit; perfaud policy remains fail-closed; no runtime override exists. |
| Output safety | Output is fixed at `WORKSPACE/output`; injected failures preserve the prior result; success removes stale artifacts. |
| Python API | Root exports and focused imports match the contract; both `RunResult` classes have exactly three fields; CLI and API artifacts agree. |
| Code shape | Final `src` layouts import cleanly; obsolete namespaces and catch-all/validator modules do not import. |
| ppar tables | Focused boundaries are Polars-only; pandas, PyArrow, and lxml are absent; financial and rendered outputs match baseline. |
| Exceptions | Numeric exception registry is absent; expected messages remain actionable; perfaud finding codes and report schemas are unchanged. |
| Templates | Templates are data-only resources, contain no `__init__.py`, and are complete in the installed wheel. |
| Packaging | One `py3-none-any` wheel per product has exact intended contents and passes Twine and installed-workflow smokes; no sdist path remains. |
| Documentation | One README index and four-document spine remain; examples execute; active configuration tables match code; stale archives and PDFs are absent. |
| README images | Every README image is retained under `docs/images/`, referenced once, carries its current source fingerprint, validates structurally, and is visible through canonical GitHub/PyPI-compatible URLs. |
| Financial behavior | Artifact names, schemas, columns, values, signs, rounding, classifications, explanations, and invariants match baseline. |
| Scale | Both unchanged 500x gates pass, including perfaud's unchanged warning and failure boundaries. |
| Coexistence | Both wheels install and run in one clean environment; `pip check` and module-origin checks pass. |

Release candidates run the routine product gate, applicable demo and bundle health
checks, the owning 500x gate, installed-wheel workflows, and the final acceptance rows
before publication.

## Git and Authorization Boundaries

Preserve history by cloning the complete current repository before extraction. Both
lineages share commits through the split point. The existing ppar tags remain only with
ppar; perfaud receives no inherited release tags.

Local code, tests, documentation, builds, and validation may proceed under this plan.
The final local directory rename writes outside the current workspace root and may
require filesystem approval when reached.

These hosted actions require authenticated access and explicit authorization at the
time of execution:

- renaming the current GitHub repository;
- creating the perfaud repository and choosing its visibility;
- changing origins, branch protection, repository secrets, or hosted metadata;
- configuring PyPI ownership or Trusted Publishing;
- uploading `perfaud==0.1.0` or `ppar==0.2.0`; and
- creating hosted tags or releases.

Preflight on 2026-08-28 found neither proposed sibling local directory and received
`Repository not found` from both proposed public GitHub URLs. Recheck local targets,
authenticated GitHub names, and the perfaud PyPI name immediately before cutover.
