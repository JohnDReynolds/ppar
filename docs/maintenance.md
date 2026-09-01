# Maintenance

Create the primary repository environment with Python 3.12.1 and install the complete
development surface:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install -c constraints/ci.txt -e ".[dev]"
```

ppar supports Python 3.11.9 through 3.14. The compatibility workflow runs the complete
product gate on the minimum 3.11.9 and primary 3.12.1 environments, plus the complete
test suite on the latest Python 3.13 and 3.14 patch releases.

Run the routine product gate:

```bash
./.venv/bin/python scripts/check_project.py
```

It runs tests, mypy, Pyright, Pylint error checks, focused unused-import and
unused-variable checks, documentation/demonstration drift, README-image drift, a
direct universal-wheel inspection, and installed-package Axys/APX and vendor-neutral
workflow smoke tests outside the checkout. The smoke tests install the wheel without
dependencies and reuse the already verified development dependencies; they validate
the installed package and workflows, not independent dependency resolution.

After major cross-cutting, reporting, safety, or performance work, run the unchanged
500x gate:

```bash
./.venv/bin/python scripts/check_scale.py --scale 500
```

The large-site result first runs one untimed warm-up for the baseline and scaled
workspaces. It then collects five baseline-then-scaled timing pairs and applies the
unchanged thresholds to the median of the five scaled/baseline ratios. Every timed
observation and ratio is printed. To investigate timing components without changing
the release result, add `--diagnostics`; this also reports fixture preparation,
Python startup, and calculation-only timings as observation-only components.

The release-candidate command composes both gates:

```bash
./.venv/bin/python scripts/check_release_candidate.py
```

GitHub runs the routine product gate on Python 3.11.9 and 3.12.1 and the test suite on
Python 3.13 and 3.14. The release-candidate workflow runs the complete command above
on Python 3.12.1, uploads the validated universal wheel, and can be started manually.
The publishing workflow requires that release-candidate job and publishes the exact
wheel it validated rather than rebuilding it.

To intentionally refresh README images, run:

```bash
./.venv/bin/python scripts/render_readme_images.py
```

Then review the changed images and run the routine gate. Generated images embed a
fingerprint of the renderer, relevant package sources, demonstration inputs, and
pinned dependencies. The gate checks that fingerprint, the README inventory, image
formats and dimensions, and image decodability without platform-specific rasterizing.

Build releases as a direct wheel only. Do not build or publish an sdist. Publishing,
tagging, GitHub changes, and PyPI changes require separate authorization.
