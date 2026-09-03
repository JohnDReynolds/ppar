# ppar Cleanup Phase 10 Implementation

Status: Complete  
Implementation date: September 1, 2026

## Final documentation contract

The active documentation now states the complete selected support boundary:

- Python 3.11.9 through 3.14;
- the focused Axys/APX `portperf.csv`, `secperf.csv`, and `secmast.csv` source model;
- complete-period selection by inclusive `thru_date`, including an inside-period
  example;
- exact duplicate classification and mapping pairs collapse, while conflicting
  values for one identifier stop the run;
- attribution HTML is limited to 1,010 rows, with Polars and CSV as full-data
  alternatives; and
- transactional output replacement protects the prior bundle from Python exceptions
  and interruptions but does not claim process-crash atomicity.

The generated READMEs and tutorials did not change because Phase 10 changed no user
workflow. Duplicate behavior belongs in the focused configuration reference, and the
product gate now checks that those rules remain documented.

## Repository-wide assessment

Reference and obsolete-terminology scans found no live retired YAML runner,
`--generic` option, old Axys fixture path, or unsupported Axys configuration language.
The remaining `ppar run` mention explicitly says the command does not exist. Remaining
uses of "workspace" name internal temporary scale/smoke directories rather than the
CLI's user-facing `DIRECTORY` argument.

No tracked cache, editor, checkout build, or egg-info artifact was present. One
ignored root `.DS_Store` file was removed. Runtime source imports no `perfaud`, and
the retained wheel contains no `perfaud` path.

A focused Pylint scan reported no unused import, variable, argument, or unreachable
code. Its duplicate-code scan reported four similar explicit narrow-data column
selections in `core.py` and `performance.py`. Those selections intentionally make
each financial transformation's output schema visible. Sharing the private tuple
across modules would create coupling for negligible simplification, so no change was
made and the signal was not globally suppressed.

## Validation

Focused checks passed:

- 29 tests and 6 subtests for classification/mapping and documentation policy; and
- 122 tests and 243 subtests for financial baselines, schemas, output names and order,
  publication, image quality/provenance, package contracts, and both demonstrations.

Fresh generic and Axys/APX setup directories were created and run from `/tmp`, outside
the checkout. Each printed and produced the approved ordered 11-report bundle.

The complete release-candidate command passed:

- 339 tests and 386 subtests;
- Mypy, Pyright, Pylint errors-only, and the selected unused-code warning policy;
- documentation and 12-image inventory, fingerprint, format, size, and decoding
  validation;
- isolated universal-wheel construction, inspection, Twine, dependency checks, and
  installed-package workflows; and
- the unchanged 500x scale sequence.

The scale results were 1.084x for the large-site workload, 1.933x for the selected
workload, and 1.437x for long history. The first remains an established warning below
the unchanged 1.10x failure threshold. The retained artifact is
`/tmp/ppar_phase10_validated_wheel/ppar-0.2.0-py3-none-any.whl`.

Root `build/` and `src/ppar.egg-info` remained absent, and `git diff --check` passed.
No report name, report order, output column, financial formula, tolerance, or gate
threshold changed.

## Roadmap relationships

- The correctness roadmap is complete and remains authoritative for formulas,
  conservation, alignment, reconciliation, and numerical invariants.
- The optimization roadmap remains unimplemented. Cleanup's CI-only `Agg` setting is
  not the proposed production-backend optimization.
- The user-view roadmap records that automated installation, help, both setup paths,
  standard outputs, clean-wheel operation, and correctness/scale validation are
  complete. Own-data user journeys and human-profile validation remain there.
