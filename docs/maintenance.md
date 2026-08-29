# Maintenance

Create the repository environment and install the complete development surface:

```bash
python3.11 -m venv .venv
./.venv/bin/python -m pip install -c constraints/ci.txt -e ".[dev]"
```

Run the routine product gate:

```bash
./.venv/bin/python scripts/check_project.py
```

It runs tests, mypy, Pyright, pylint error checks, documentation/configuration drift,
README-image drift, a direct universal-wheel inspection, and installed-wheel Axys/APX
and Generic workflows outside the checkout.

After major cross-cutting, reporting, safety, or performance work, run the unchanged
500x gate:

```bash
./.venv/bin/python scripts/check_scale.py --scale 500
```

The release-candidate command composes both gates:

```bash
./.venv/bin/python scripts/check_release_candidate.py
```

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
