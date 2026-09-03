# ppar Cleanup Phase 9 Assessment

Assessment date: September 1, 2026

## Completed without reducing a gate

### Isolated wheel construction

The product gate now copies only `LICENSE`, `README.md`, `pyproject.toml`, and `src/`
to a temporary source directory before building. It no longer deletes or recreates
root `build/` or `src/ppar.egg-info`.

A complete product-gate run passed 338 tests and 386 subtests, static analysis, image
validation, wheel inspection, and both installed workflows. A post-run check confirmed
that both generated checkout paths remained absent.

### Accurate installed-package smoke claim

The smoke test deliberately retains its efficient existing implementation: install
the wheel with `--no-deps`, expose the already verified development dependencies, and
run the CLI plus both generated demonstrations outside the checkout. The function and
maintenance documentation now call this an installed-package workflow smoke test and
explicitly state that it is not an independent dependency-resolution test.

## User decisions

The user approved recommendations 1, 2, and 3 and rejected recommendation 4 on
September 1, 2026. The approved recommendations have been implemented. All 12 gallery
images, their README references, and the `main`-based image URLs remain in place.

### 1. Compatibility and Python support — approved and implemented

Current contract:

- `requires-python = ">=3.11.9"` accepts every later stable and future Python.
- CI runs the complete product gate only on Python 3.11.9 and 3.12.1.
- The release-candidate gate repeats the complete product gate on 3.12.1 before the
  unchanged 500x scale gate.

Evidence:

- Python 3.13 and 3.14 are stable maintained releases according to the
  [Python version status](https://devguide.python.org/versions/) and
  [Python release index](https://www.python.org/doc/versions/).
- A fresh constrained Python 3.13.1 environment passed the complete ppar product gate:
  338 tests, 386 subtests, static analysis, image validation, wheel inspection, and
  both installed demonstrations. The initial macOS run selected Matplotlib's GUI
  backend and aborted in the headless shell; setting the standard `Agg` backend made
  the environment deterministic. GitHub's Linux jobs already use a non-GUI backend.

Recommendation:

- State the actual supported range as Python 3.11.9 through 3.14 by changing package
  metadata to `>=3.11.9,<3.15` and matching the README.
- Retain the complete product gate on 3.11.9 and 3.12.1. This preserves minimum-version
  and primary-maintainer acceptance rather than weakening either established gate.
- Add test-suite jobs on the latest Python 3.13 and 3.14 patch releases. Do not rerun
  Mypy, Pyright, Pylint, image provenance, and wheel packaging there: those checks do
  not gain Python-runtime coverage from repetition. Set `MPLBACKEND=Agg` throughout CI.
- Retain the release candidate's complete 3.12.1 product gate before the unchanged
  500x check. It runs only manually or for publication and is justified release-time
  revalidation, not routine push duplication.

Tradeoff: CI gains two unit-test jobs, and Python 3.15 users will be rejected until a
future phase explicitly tests and adds that minor release. No existing gate is
removed.

### 2. Publish the validated wheel — approved and implemented

Current contract:

- The release-candidate job builds, inspects, Twine-checks, installs, and exercises a
  universal wheel in temporary storage.
- The publish job discards that wheel and independently rebuilds another wheel.

Recommendation:

- Let the release-candidate command optionally retain its already validated wheel.
- Upload that wheel with `actions/upload-artifact`.
- Make the dependent publish job download and publish that exact artifact rather than
  checking out the source and rebuilding it.

GitHub documents workflow artifacts as the mechanism for passing build output between
jobs in the same workflow run in
[Store and share data with workflow artifacts](https://docs.github.com/actions/configuring-and-managing-workflows/persisting-workflow-data-using-artifacts).

Tradeoff: this adds a small command-line output option and two standard artifact
steps, but removes the more consequential risk that tested and published wheels differ.
Local release-candidate runs remain temporary and leave the checkout unchanged unless
an output directory is explicitly requested. No validation is removed.

### 3. Narrow README-image provenance — approved and implemented

Current contract:

- Every Python, CSV, Markdown, YAML, and `py.typed` file below `src/ppar` contributes
  to every image fingerprint.
- Consequently, unrelated Axys/APX, CLI, template-documentation, and typing-marker
  edits invalidate all gallery images.

Recommendation:

- Fingerprint the renderer, dependency constraints, `pyproject.toml`, all top-level
  ppar calculation/reporting modules, and the generic CSV inputs actually used to
  render the gallery.
- Exclude Axys/APX, CLI, generated-tutorial prose, and `py.typed`, none of which is on
  the rendering path.
- Add tests that protect the declared transitive input boundary.

Tradeoff: this intentionally narrows a provenance gate. A future renderer change that
starts using another subpackage must add that subpackage to the explicit input list.
Pixel, size, format, inventory, and retained-input provenance checks remain unchanged.

### 4. Reduce the README gallery — rejected

Current contract:

- The README embeds 12 full-width images totaling approximately 7.0 MB.
- `OverallAttributionBySecurity.jpg` alone is approximately 4.2 MB and 8,199 pixels
  tall.
- A test permanently requires exactly 12 images even though the real contract is that
  the README, renderer, and tracked inventory agree.
- Image URLs target `main`, allowing an old PyPI release to display newer images.

Recommendation:

- Retain six representative examples totaling approximately 1.4 MB:
  `OverallAttributionByEconomicSector.png`, `SubPeriodReturns.png`,
  `ActiveContributionsByEconomicSector.png`, `CumulativeReturns.png`,
  `OverallAttributionByEconomicSector.jpg`, and `RiskStatistics.jpg`.
- Delete the other six tracked marketing images. This preserves the previously chosen
  `SubPeriodReturns.png` example and does not change the standard report bundle.
- Continue requiring exact agreement among the declared renderer inventory, README,
  and tracked files, but remove the arbitrary assertion that the count must always be
  12.
- Point image URLs at the release tag matching `pyproject.toml` instead of `main`, and
  test that the two versions agree.

Tradeoff: the README becomes substantially shorter and the repository loses roughly
5.6 MB of redundant marketing binaries. Six output types are no longer pictured in
the README, but they remain fully supported, documented as available output, and
produced by the demonstration.

## Validation

The completed implementation passed:

- 339 tests and 386 subtests;
- Mypy, Pyright, both Pylint levels, documentation validation, and image validation;
- isolated universal-wheel build, inspection, Twine validation, installation, and
  both installed workflows;
- retention of the exact validated wheel for workflow artifact handoff; and
- the unchanged 500x scale sequence, with a 1.059x median large-site ratio, 1.878x
  selected-workload ratio, and 1.401x long-history ratio.

The retained wheel declares `Requires-Python: <3.15,>=3.11.9`. Root `build/` and
`src/ppar.egg-info` remained absent after the complete release-candidate run. Exactly
12 gallery files and 12 README image references remain.
