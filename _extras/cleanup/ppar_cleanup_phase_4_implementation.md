# ppar cleanup Phase 4 implementation

Date: September 2, 2026

## Outcome

Phase 4 removed redundant report rendering and editorial prose gates while retaining
every distinct user journey and failure boundary. The complete generic and Axys/APX
setup-variant test remains the single authoritative test of the ordered standard
11-report bundle.

Six unnecessary complete bundle renders were removed from the test suite:

- the root introductory Python example now proves only that a user can replace the
  generic performance inputs and execute the documented example;
- the customized Axys account-code journey loads the edited tutorial script, builds
  its analytics, calculates classification attribution, and renders one focused
  security-attribution table to verify the customized portfolio and benchmark names;
  and
- the four malformed-source cases now seed representative existing ppar and
  independently created output files instead of first generating complete bundles.

The malformed-source cases assert the exact set and byte contents of the seeded
output after required-column or identity validation fails. This is a more direct test
of the promised failure boundary than comparing against output the same test just
rendered.

The duplicate standard-report inventory and its helpers were removed from
`tests/test_user_journeys.py`. The one inventory in
`tests/test_mega_cap_demo_data_contract.py` remains independent of the templates it
checks, so an incorrect product inventory cannot validate itself.

Two exact tutorial prose fragments were removed from `scripts/check_project.py`, and
one exact editorial sentence was removed from `tests/test_package_metadata.py`.
Active-document, local-link, executable-command, API-surface, methodology behavior,
build, wheel, and installed-workflow checks remain intact.

## Verification

Focused tests:

```text
python -m unittest tests.test_user_journeys \
  tests.test_mega_cap_demo_data_contract tests.test_package_metadata
19 tests passed in 3.395 seconds
```

Complete product gate:

```text
383 tests passed, 477 subtests passed in 12.21 seconds
Mypy: success
Pyright: 0 errors, 0 warnings
Pylint errors-only: passed
Pylint unused-import/unused-variable: 10.00/10
README image check: current
Universal wheel build: passed
Twine: passed
Installed-wheel generic workflow: passed with 11 reports
Installed-wheel Axys/APX workflow: passed with 11 reports
git diff --check: passed
```

The pytest duration is 30.2% below the 17.50-second Phase 3 observation and 35.6%
below the roadmap's original 18.97-second observation. These are observations only;
no timing threshold was introduced.

## Accounting

Phase 4 changed four test/check files: 45 lines were added and 88 removed, for a net
reduction of 43 lines. Through Phases 1-4, the cleanup has added 191 lines and removed
1,097, for a net reduction of 906 lines. No production code, public API, output
schema, report inventory, financial calculation, invariant, or established gate was
changed in this phase.
