# Project Coding Guidelines

Apply these conventions when modifying or creating code in this project.

## Model Reasoning Guidance

- Default to GPT-5.6 Sol Medium.
- Before beginning work that would materially benefit from High or Extra High
  reasoning, notify the user and recommend the appropriate level with a one-sentence
  explanation.
- Recommend High for difficult, cross-cutting design, financial logic, debugging, or
  invariant work.
- Recommend Extra High only for exceptionally difficult problems with substantial
  ambiguity or interacting edge cases.
- Do not recommend changing levels for routine implementation.

## Style And Quality

- Follow PEP 8 unless an established project-specific convention intentionally differs.
- Limit lines to 99 characters.
- Keep code free of `pylint` and `pyright` errors. Evaluate warnings case by case.
- Prefer small, behavior-preserving changes unless a broader refactor has clear value.

## Portable Preparation Boundary

- Treat `perfattr` as the sole authority for source-neutral performance validation,
  canonical CSV loading, portfolio selection from normalized frames, calendar and
  period alignment, classification mapping, frequency consolidation, and attribution
  calculations.
- Keep all Polars/pandas translation in `src/ppar/_perfattr_adapter.py`. Do not add a
  permanent local fallback or another implementation of a portable algorithm.
- Keep vendor-specific parsing, portfolio accounting, source-level predicate pushdown,
  security-identity construction, holiday-file loading, Polars-facing compatibility
  objects, risk, reports, and presentation in `ppar`.
- Preserve ppar's public APIs, output schemas, warnings, null placement, deterministic
  ordering, and presentation precision at the adapter boundary.
- Require `1e-12` relative and absolute numerical parity across the adapter, together
  with identical reconciliation outcomes. Do not require bit-for-bit floating-point
  identity.

## Test-Gate Integrity

- Never raise, relax, disable, or bypass a test, benchmark, warning threshold, failure
  threshold, invariant, or release gate merely because it is failing.
- Treat an unexpected gate failure as evidence of a possible product regression and
  investigate the implementation first.
- Obtain the user's explicit approval before intentionally changing an established
  gate or threshold. State the current value, proposed value, evidence, and tradeoff.
- Never relax a tolerance specified in a test plan without first obtaining the
  user's explicit approval.
- Keep the 500x scale check in the core release-candidate workflow. Run it after major
  cross-cutting, reporting, audit, safety-net, or performance changes even when the
  complete release-candidate sequence is not otherwise required.
- Keep inexpensive financial, conservation, lineage, and explanation-reconciliation
  invariants enabled in production runs. Put redundant full-artifact reparsing or
  similarly expensive independent verification in test and release-candidate checks
  when running it in production would materially degrade performance.

## Test Ownership

- Keep exhaustive source-neutral calculation, normalization, alignment, mapping, and
  consolidation cases in `perfattr`, which owns those implementations.
- Keep `ppar` tests for Polars/pandas and CSV translation, host error and warning
  behavior, public schema and null placement, presentation, source-specific behavior,
  and representative end-to-end delegation.
- Retain at least one successful and one failing public `ppar` example for each
  material adapter seam. Do not duplicate a complete portable edge-case matrix merely
  to exercise the same `perfattr` call repeatedly through `Analytics`.
- Before removing a portable invariant that is covered only in `ppar`, add an
  independently explained test for it in `perfattr` and verify both suites.

## Typing And Naming

- Annotate public parameters, public return values, class attributes, and non-obvious
  local variables where annotations improve readability or type checking.
- Avoid unnecessary annotations for obvious local variables.
- Prefix module-level identifiers with `_` when they are intended only for use within
  that module.
- Do not underscore public APIs or intentionally imported package-internal names.

## Public APIs

- Use idiomatic Python conventions at public boundaries.
- Normalize compatibility sentinels and legacy conventions at public boundaries.
- Preserve public behavior unless an API change is explicitly requested.

## Output Schema Stability

- Never add new columns to output files.

## Comments And Financial Logic

- Comment non-obvious intent, business rules, financial interpretation, assumptions,
  sign conventions, and important edge cases.
- Avoid comments that simply paraphrase straightforward code.
- Favor explicit names and intermediate variables when they improve financial
  interpretability or auditability.

## Docstrings

Use consistently formatted Google-style docstrings for all public APIs and meaningful
internal classes and functions. Type annotations do not replace behavioral
documentation.

- Modules should include a concise summary and useful context where appropriate.
- Classes should document their purpose and meaningful public instance state using
  `Attributes:`.
- Nontrivial functions and methods should use applicable `Args:`, `Returns:`, and
  `Raises:` sections.
- Constructors should document their arguments either in the class docstring or in
  `__init__`, following a consistent project-wide approach.
- Use `Yields:` instead of `Returns:` for generators.
- Use `Examples:` when a public entry point is not obvious.
- Use `Notes:` for significant formulas, data-shape expectations, assumptions, or
  validation behavior.
- Use `Warnings:` only for genuine misuse risks or significant side effects.
- Use `References:` for financial methodologies or external specifications when
  useful.
- Use `See Also:` only when it meaningfully improves navigation.
- Trivial private helpers may retain concise one-line docstrings.
- When modifying an existing public API, bring its docstring into compliance as part
  of the same change.
