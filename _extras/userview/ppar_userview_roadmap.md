# ppar User-View Roadmap

Status: Complete for the currently approved scope after the September 4, 2026
post-cleanup reassessment; Phases 0, 2, 3, 5, 6, 7, 8, 9, and 10 are completed,
Phase 1 remains rejected, Phase 4 remains deferred, and independent second-user
observation remains an optional external follow-up

Assessment date: September 4, 2026

## Objective

Evaluate ppar as a prospective user would encounter it: deciding whether to install
the product, following its documentation, running setup, adapting the generated
workflow, using the Python API, handling failures, and reviewing the resulting report
bundle.

This roadmap records user-facing opportunities. It is separate from the completed
correctness roadmap, which established the mathematical, validation, and
release-candidate foundation on which this work would build.

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
work, and Extra High for exceptionally difficult financial, numerical, or invariant
work with interacting edge cases. No phase in this roadmap currently warrants Ultra.

## Overall impression

A user would probably think:

> This is a rigorous Python analytics library with a polished static report set. A
> Python-literate analyst can start quickly and see the assumptions, but a less
> technical analyst still has to edit a long Python program and browse an unrelated
> directory of report files.

The product now makes a much stronger first impression than it did at the original
assessment. Phases 9 and 10 resolved the immediate first-run seams and the report and
metric orientation gap. The remaining opportunities are deliberate product decisions:
a report-bundle entry point, and one chart whose shared scale can hide small but
meaningful allocation effects.

The right expectation is still an evaluation-ready library and editable reporting
starter, not a turnkey portfolio-reporting application. That positioning is reasonable
provided prospective users understand it before adopting the workflow.

## What works particularly well

- The two-command start is concise and immediately executable:

  ```bash
  ppar setup ./my_ppar
  python ./my_ppar/ppar_demo.py
  ```

- `ppar -h` and `ppar setup -h` clearly explain `DIRECTORY`, the default data source,
  and the Axys/APX option.
- Setup refuses to overwrite a nonempty directory.
- Both demonstrations successfully produce the advertised 11 reports in about ten
  seconds on the review machine.
- Absolute demonstration paths and script-relative inputs avoid working-directory
  ambiguity.
- The generated scripts expose their assumptions as editable Python values and
  contain extensive tutorial comments.
- Report filenames and titles identify the portfolio, benchmark, classification,
  frequency, and date range consistently.
- The methodology communicates strong financial discipline: source reconciliation,
  date alignment, conservation checks, linking, and risk-domain validation are
  explicit.
- The root Python API is small and typed.
- Local processing, ordinary files, and user-controlled output suit confidential
  portfolio data.

## September 4, 2026 reassessment evidence

This reassessment approached the repository from the outside in rather than reviewing
only implementation structure. It covered the root and generated documentation, CLI
help and setup behavior, both generated programs, public signatures and enums, an
expected missing-file failure, and visual and structural inspection of the standard
HTML and PNG output.

Observed during reassessment before Phase 9:

- Vendor-neutral setup completed and directed the user to the generated README.
- Axys/APX setup completed and identified the selected source type.
- Repeating setup against a nonempty directory failed safely with one concise message.
- Both unmodified demonstrations generated the expected four HTML tables and seven PNG
  charts.
- A single warm vendor-neutral run took 9.96 seconds and emitted no text until all
  reports had been written.
- Removing the portfolio performance file produced an ordinary traceback, as intended,
  but its final message was `perfattr preparation failed: performance CSV path must
  identify an existing local regular file`. It named an implementation dependency and
  did not identify the missing path.
- The generated generic and Axys/APX programs are now 234 and 278 lines respectively.
  Their extensive comments make them auditable and adaptable, but their size is an
  honest adoption boundary for users who do not routinely edit Python.
- The four HTML reports have meaningful browser titles, responsive markup, semantic
  table headers, and readable presentation formatting. They contain no links to one
  another, consistent with the Phase 4 deferral.

This remains a Codex product review, not an observed independent-human usability test.

## User-facing findings

### 1. Expected input failures look like programming failures — resolved to scope

A missing or malformed input encountered by `ppar_demo.py` produces a complete Python
traceback. Its final `PparError` message can be useful, but the user must read through
implementation paths and stack frames to find it.

Decision: do not add demo-specific traceback suppression or install a process-wide
exception hook. ppar remains a Python library whose public APIs raise ordinary
exceptions, including structured `PparError` context where available. Improving
individual unclear messages remains worthwhile. Phase 9 removed portable-core branding
from preparation and calculation messages. CSV loading failures now identify the
rejected path, while the existing specific identity diagnostics remain intact.

### 2. Report units are ambiguous — resolved

Status: **Resolved in Phase 2.**

Tables and charts previously displayed returns, weights, contributions, and effects as
raw decimals such as `0.8339` and `0.0656`. A knowledgeable user could infer 83.39% and
6.56%, but a presentation report should not require that inference.

Phase 2 also resolved:

- `-0.0000` values in tables and heatmaps;
- chart axes on which several distinct ticks render as `0.00`;
- heatmaps filled with small decimals rather than percentages or basis points; and
- column headings and chart axes without explicit units.

Presentation output now uses deliberate percentage formatting while machine-readable
Polars and CSV output retains numeric decimals.

### 3. Reports lack important review context — partly resolved

The risk report now displays the configured risk-free rate, minimum acceptable return,
VaR confidence level, and portfolio-value assumption. Report files still lack the ppar
version, creation date, and source or configuration provenance by the narrowed Phase 3
decision.

The Axys/APX documentation explains that weights may be inferred or adjusted during
reconciliation, but the report bundle contains no reconciliation summary showing what
changed. An analyst can review the calculated values, but an auditor or investment
committee reviewer still needs the script and source files to understand how the
reports were produced.

### 4. The report bundle has no entry point

The 11 descriptive filenames are useful, but users receive a directory of unrelated
HTML and PNG files and must decide where to begin. The HTML pages now have useful
document titles and sticky headings, but do not link to one another or provide a bundle
summary or download links.

A small `index.html` could summarize the run and link every artifact. Selectable CSV
publication could also complement the current HTML and PNG bundle. Both remain
deliberately deferred with Phase 4; Phase 10 should explain the existing direct CSV
method without changing the standard bundle.

### 5. The generated vendor-neutral README is too sparse — resolved

Status: **Resolved in Phase 5.**

The Axys/APX README provides a substantial input contract. The vendor-neutral README
now also documents the execution command, complete performance-column contract, units,
period and coverage rules, classification and mapping orientation, identity behavior,
and common substitution errors.

The resolved guide covers:

- column meanings and units;
- date and period rules;
- portfolio and benchmark coverage requirements;
- classification and mapping file orientation;
- display-name behavior; and
- common validation failures.

Setup explicitly sends the user to this generated README, which is now sufficient for
the next step without requiring discovery of explanations inside the generated script.
Reports are written directly to `output/`; the earlier statement that a successful run
replaces the complete directory is obsolete.

### 6. The introductory Python example produced too much output — resolved

Status: **Resolved in Phase 6.**

The earlier root README example produced a large identifier-level DataFrame whose
headings wrapped heavily in a terminal. Phase 6 retained the shortest generic
`Analytics` setup but reduced its result to one row containing total portfolio,
benchmark, and active returns. The generated `ppar_demo.py` remains the complete
classification and reporting example rather than duplicating that workflow in the
root README and Python API guide.

The API guide now identifies every result method and shows the minimal standard-library
operations for saving returned HTML strings and PNG bytes.

### 7. Direct risk arrays produced surprising presentation output — resolved

Status: **Resolved during Cleanup Phase 7 and retained through User-View Phase 6.**

This finding referred to the lower-level `RiskStatistics` example in
`docs/python_api.md`, which passes portfolio and benchmark return arrays directly
rather than loading `Performance` data through `Analytics`.

The example now supplies 12 monthly observations, enough for its annualized
statistics. The accompanying documentation states the minimum history for monthly,
quarterly, and yearly inputs and explains the behavior of shorter valid samples.
Direct arrays have no source names or dates, so their HTML now uses the neutral titles
`Portfolio` and `Benchmark` and omits the date range instead of exposing the internal
`0001-01-01` and `9999-12-31` sentinel dates. No optional name or date parameters were
added to the array API.

### 8. Product positioning is not fully explicit

The current product is a Python analytics library, a setup generator, an editable
234- or 278-line starter program, and a collection of static report files. This is a
reasonable design, but some users will initially expect a conventional CLI reporting
application.

The product should describe itself explicitly as a Python analytics library with a
generated, editable reporting program. Phase 7 removed the potentially misleading
phrase "self-contained demonstration directory" because the generated script still
depends on the installed ppar package. Broader positioning remains a separate product
decision.

The 45-day single-user evaluation boundary and commercial contact are conspicuous
before installation, which is good. The lack of a published support, update, pricing,
or purchase process beyond a personal email also signals an early-stage commercial
offering. That is not a documentation defect while those policies do not exist; add
them only when there is a real product commitment to describe.

For users who are not Python developers, a preflight validation mode could improve the
workflow, but it is not an 80/20 change. One start message and a concise completion
summary are sufficient for the current approximately ten-second standard run and do
not require a YAML configuration, progress framework, or restoration of `ppar run`.

### 9. User documentation has important gaps — resolved to selected scope

Status: **Resolved in Phase 10.**

The documentation spine now includes one compact report guide covering every `View`
and `Chart`, attribution columns, all risk metrics, formulas, units, unavailable cells,
format selection, CSV writing, object acquisition, and generated-program upgrades. The
Python API guide distinguishes objects users construct from values returned by
`Analytics` or `AxysData`, and the root README labels maintenance as contributor
material.

Runtime constructors still truthfully expose their actual internal `Performance`
annotation. Masking it would require an inaccurate annotation or a factory/class
redesign, so Phase 10 clarified normal acquisition in documentation and interactive
help instead. The Python API guide does not require `Performance` or `perfattr` as user
concepts.

No exhaustive troubleshooting guide was added. The generated vendor-neutral README
already describes common substitution failures, and public exceptions retain specific
messages and structured context. A larger failure catalog would duplicate those
contracts and is not needed for the selected 80/20 scope.

### 10. Smaller polish issues weakened the finished impression — resolved

Status: **Resolved across Cleanup Phase 7 and User-View Phase 7.**

- Cleanup Phase 7 corrected the `Attribution` docstring, risk-statistic labels,
  multi-dot filename handling, HTML row-limit error, and publication terminology.
- User-View Phase 7 replaced the remaining known internal-looking audit messages with
  plain descriptions.
- HTML reports now include document titles, responsive viewport metadata, accessible
  table labels and header scopes, and sticky column headings.
- Series and sign charts use a color-vision-friendly palette. Legends, labels, bar
  positions, and zero axes remain redundant cues rather than relying on color alone.
  A later product-owner decision returned heatmaps to muted red for negative values
  and green for positive values, with numeric percentages in every populated cell.

### 11. One generated Axys/APX instruction was visibly broken — resolved

Status: **Resolved in Phase 9.**

The final paragraph of the earlier Axys/APX README ended with the fragments `Leave` and
`Attribution calculations use the portable perfattr core.` The first sentence is
unfinished and the second exposes an implementation detail where the user expects a
next step. Phase 9 replaced both fragments with one complete user-directed instruction.

### 12. The standard run was silent long enough to feel stalled — resolved

Status: **Resolved in Phase 9.**

The earlier generated programs printed nothing until calculation and rendering
finished. The standard vendor-neutral journey took 9.96 seconds on the review machine.
Both programs now print `Generating reports...` before loading or calculation and a
completion line with the report count and output directory before the unchanged file
list. No progress framework, logging policy, or new runner was added.

### 13. The report catalog is visual but not explanatory — resolved

Status: **Resolved in Phase 10.**

The root gallery remains concise and visual. Its new reports-guide link leads to the
question and result grain for every supported view and chart, identifies standard-
bundle choices, and explains when Polars, HTML, PNG, or CSV is appropriate. The guide
also explains the distinction between `SUBPERIOD_SUMMARY` and attribution results.

### 14. The overall-attribution chart can visually suppress allocation

The three overall-attribution panels share one horizontal scale. In the standard data,
selection and total effects are much larger than allocation effects, so the allocation
bars appear nearly empty even when their differences are meaningful. A shared scale is
valid and supports direct comparison, so this is not a correctness issue. Before
changing it, compare independent panel scales or value labels against the current
chart and make an explicit product decision. This is a presentation candidate, not a
release blocker.

## Recommended implementation order

### Phase 0: Define presentation and compatibility contracts

Recommended Codex level: **GPT-5.6 Sol High**

Status: **Completed September 2, 2026, through the Phase 2 presentation contract,
output-contract regressions, and retained machine-readable values.**

Before changing output, record the intended distinction between machine-readable
decimals and presentation percentages or basis points. Decide which report metadata
belongs in titles, footers, or a manifest without adding columns to established output
files. Capture the existing filenames, schemas, and calculated values as regression
contracts.

### Phase 1: Make failures user-facing

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: **Rejected by user decision on September 2, 2026.**

The proposed implementation would have added concise expected-error handling only to
the two generated `ppar_demo.py` workflows. It would not inherently improve arbitrary
Python programs written directly against ppar.

The only automatic mechanism available to every importing program would be an
import-time `sys.excepthook` replacement. That process-wide side effect would be
inappropriate for a library: it could interfere with notebooks, IDEs, test runners,
application-specific exception handling, and unrelated code. It also could not safely
suppress generic `ValueError` or `OSError` tracebacks without hiding failures from the
user's own program.

ppar will therefore retain ordinary Python exception behavior. Public APIs continue
to raise structured `PparError` exceptions, including machine-readable context where
available, and callers remain responsible for choosing how their applications present
uncaught errors. Improving individual unclear error messages remains in Phase 7; no
demo-specific traceback wrapper or global exception hook will be added.

### Phase 2: Clarify units and numerical presentation

Recommended Codex level: **GPT-5.6 Sol High**

Status: **Completed September 2, 2026.**

Format presentation tables and charts with explicit percentages or basis points,
normalize display-only negative zero, and ensure chart ticks preserve meaningful
differences. Keep Polars and CSV numerical values unchanged.

Implementation decision: presentation output uses percentages rather than basis
points. Attribution tables, heatmap annotations, and chart ticks display decimal
values as percentages. Risk-statistics rows use percentages for return-like and
probability measures, ordinary decimals for dimensionless measures, and currency for
value at risk. Chart tick precision adapts for unusually small intervals. Polars and
CSV output retain the original decimal values.

### Phase 3: Make reports self-describing

Recommended Codex level: **GPT-5.6 Sol High**

Status: **Completed September 2, 2026, with scope narrowed by user decision.**

Implemented:

- The risk report displays its configured annual risk-free rate, annual minimum
  acceptable return, and VaR confidence level in a full-width assumptions line below
  the report subtitle and above the result headings.
- The assumptions use presentation percentages while their underlying configuration
  values and calculations remain unchanged.
- The existing portfolio-value assumption remains in the value-at-risk row label,
  where it was already displayed, and is not duplicated in the new assumptions line.

Not implemented in this phase:

- ppar version information;
- report-generation date or time;
- source-file, configuration, or broader provenance metadata;
- an Axys/APX reconciliation summary;
- assumptions or metadata on attribution reports;
- new Polars or CSV columns, or any change to machine-readable numerical values; or
- a separate or duplicated portfolio-value assumption.

These excluded ideas are not part of completed Phase 3 and have no implementation
commitment unless the user chooses to revisit them later.

### Phase 4: Create a navigable report bundle

Recommended Codex level: **GPT-5.6 Sol High**

Status: **Deferred by user decision on September 2, 2026.**

Generate an `index.html` or equivalent manifest linking the selected reports and
summarizing the analysis. Improve individual HTML document metadata, long-table
navigation, responsive behavior, and printing. Assess selectable CSV publication.

Cross-phase progress: Phase 7 completed document metadata, responsive viewport
configuration, semantic table structure, and sticky column headings. The report-bundle
entry point, cross-report navigation, printing review, and selectable CSV publication
remain deferred with this phase.

### Phase 5: Strengthen the first-run documentation

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: **Completed September 2, 2026, with scope narrowed by user decision.**

Implemented:

- The generated vendor-neutral README identifies the performance input and report
  output locations.
- A compact table defines every required performance column plus the optional
  display-name column, including date forms and decimal units.
- The input contract now covers unique rows, non-overlapping source periods,
  period-weight totals, derived total returns, compatible portfolio and benchmark
  histories, common selected periods, and inclusive period-end date selection.
- A second compact table defines the orientation of security-name, classification,
  and mapping files, followed by their identifier requirements.
- One short paragraph identifies common first-run mistakes without becoming an
  exhaustive troubleshooting guide.
- Focused package tests preserve the essential guide and prevent obsolete atomic or
  complete-output-replacement language from returning.

Not implemented in this phase:

- The obsolete claim that a successful run replaces the complete `output/`
  directory. The demonstrations now write selected reports directly; the README says
  only that reports are written to `output/`.
- A replacement for the root README Python example. It was reassessed and retained
  because it is current, executable, concise, and already follows the previously
  selected `./my_ppar` workflow.
- A full report catalog, formula or output-column glossary, or exhaustive
  troubleshooting document. Those would make the first-run README less focused and
  were not necessary to substitute valid data.
- Changes to the Axys/APX generated README, whose separate input contract was already
  substantially documented.

### Phase 6: Refine the public Python API experience

Recommended Codex level: **GPT-5.6 Sol High**

Status: **Completed September 2, 2026, with the API kept deliberately small.**

Implemented in this phase:

- The root README remains the one complete introductory `Analytics` example. It now
  prints a one-row Polars result containing overall portfolio, benchmark, and active
  returns instead of a large identifier-level table.
- The Python API guide no longer duplicates the introductory data-loading example.
  It directs users to the root README for the shortest calculation and to the
  generated `ppar_demo.py` for the complete configurable reporting workflow.
- A compact result-method table covers Polars, HTML, PNG, and CSV output for
  attribution and risk statistics.
- The guide shows HTML and PNG persistence with the standard `Path.write_text()` and
  `Path.write_bytes()` operations already used by `ppar_demo.py`.
- A focused documentation test keeps the introductory example syntactically valid,
  compact, and unique to the root README.

Completed before this phase and retained:

- Cleanup Phase 6 documented and narrowed the supported Python and Axys/APX public
  APIs.
- Cleanup Phase 7 removed sentinel dates from direct-array risk presentation,
  documented minimum history, supplied a sufficiently long risk example, and
  established direct-array title fallbacks.

Assessed but not added:

- `write_html()` and `write_png()` convenience methods. They would be thin wrappers
  around ordinary `Path` operations, enlarge the public API, and embed file-management
  policy in an analytics library without simplifying the generated workflow.
- Additional public metadata properties. Existing report titles and result objects
  serve the current documented workflows; no concrete user need justifies a new
  metadata contract yet.
- Additional full Python examples. The root README, direct-risk example, and generated
  `ppar_demo.py` cover the distinct entry points without maintaining parallel versions
  of the same workflow.

### Phase 7: Finish terminology, accessibility, and licensing polish

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: **Completed September 2, 2026, as focused user-facing polish.**

Implemented:

- The README states the 45-day, single-user internal evaluation terms before the
  installation command and gives the existing package-author email as the direct
  commercial-licensing contact.
- The license repeats that direct contact and uses the lowercase `ppar` product name
  consistently.
- The misleading phrase "self-contained demonstration directory" was removed from
  the README and setup module description.
- Remaining known invariant errors containing internal function names, abbreviations,
  or implementation notation now use plain descriptions.
- Complete HTML reports include a meaningful browser `<title>`, responsive viewport
  metadata, an accessible table label, column and row-group header scopes, and sticky
  column headings.
- Series charts use the color-vision-friendly Okabe-Ito blue, orange, green, and
  vermillion colors. Sign charts use blue and vermillion rather than green and red.
  Phase 8 later restored muted red and green heatmaps by product-owner decision;
  numeric annotations keep each populated cell interpretable without color alone.
- The deterministic 12-image README gallery was regenerated, and focused tests cover
  the HTML structure, chart palette, terminology, licensing visibility, and contact.

Completed before this phase and retained:

- Cleanup Phase 7 corrected the approved risk labels, relevant docstrings, multi-dot
  filename handling, HTML row-limit error, and publication terminology.

Not implemented in this phase:

- A report-bundle index or cross-report navigation, which remains deferred with
  Phase 4.
- Preflight validation, progress reporting, or a new CLI execution workflow.
- A report catalog, full formula glossary, or exhaustive troubleshooting guide.
- Changes to financial calculations, output schemas, filenames, report selection, or
  machine-readable values.

### Phase 8: Integrated user-journey validation

Recommended Codex level: **GPT-5.6 Sol High**

Status: **Completed September 2, 2026 through automated validation and product-owner
usability review; an independent second-user observation remains an optional external
follow-up rather than a publication requirement.**

New integrated journeys:

- A vendor-neutral setup replaces both demonstration performance files with a small,
  valid four-quarter user history and executes the exact root README `Analytics`
  example.
- The lower-level direct-array risk example is extracted from `docs/python_api.md` and
  executed exactly as documented.
- An Axys/APX setup changes the portfolio and benchmark account codes and display
  names in both the exports and generated script, builds the configured analytics,
  and verifies the customized identities through one focused attribution table.
- These journeys are ordinary tests in the main suite rather than a separate or
  duplicative acceptance framework.

Existing integrated coverage retained:

- CLI help, missing-argument behavior, both setup variants, personalized README
  commands, and refusal to overwrite nonempty setup directories.
- Successful execution of both unmodified generated demonstrations and exact standard
  report filenames.
- Failed generic and Axys/APX substitutions for missing columns and malformed
  identities, including actionable `PparError` tracebacks and preservation of prior
  output.
- Isolated-source wheel construction, wheel-content inspection, Twine validation,
  clean-environment installation, dependency checking, absence of perfaud, installed
  CLI execution, and both installed demonstration workflows.
- The full calculation, presentation, typing, lint, documentation-image, correctness,
  and required 500× equivalence gates.

User-profile assessment:

- A Python-capable user has a short executable API example, one generated full
  workflow, explicit output methods, and successful customization paths for both data
  sources.
- A portfolio analyst who does not routinely edit Python can follow the exact setup
  and demonstration commands, but using independent data still requires editing
  Python values. Expected failures retain Python tracebacks by the explicit
  Phase 1 decision, and the report bundle still lacks an entry page by the Phase 4
  deferral.
- This Codex review exercises both perspectives but is not a substitute for observing
  two independent people. No independent human usability session was conducted, and
  the roadmap does not represent otherwise.

Product-owner usability follow-up completed September 2, 2026:

- Heatmaps now use muted red for negative values and green for positive values while
  retaining a numeric percentage in every cell.
- The risk-statistics assumptions line now begins directly with the annual risk-free
  rate rather than the redundant label `Assumptions:`.
- The root README now says to edit the demonstration's `Python values`.
- The redundant `docs/configuration.md` was removed. Essential editable-setting
  guidance remains beside the corresponding values in both generated scripts, while
  input contracts remain in their generated READMEs.
- The obsolete 1,010-row attribution HTML cap was removed. HTML includes every result
  row; the Python guide recommends Polars or CSV when a very large HTML file would be
  impractical.
- Generic and Axys/APX textual identities now remove surrounding whitespace at
  ingestion, retain meaningful internal spaces, reject values that become blank, and
  continue to reject conflicts after normalization. Axys/APX sources normalize and
  filter in one lazy query with requested-account selection pushed into the scan and
  one materialization per source.
- Both generated scripts describe `FROM_DATE` and `THRU_DATE` as the inclusive
  reporting period, retain the complete-source-period `thru_date` rule, and add concise
  purpose comments around report creation and each output loop.
- The unnecessary Axys/APX README sentence about keeping report grouping visible was
  removed.
- The complete tests and static checks passed, the 12-image gallery was regenerated
  and visually checked, and the required 500x scale gate passed without changing any
  threshold.

Not added:

- Another example, acceptance runner, configuration format, `ppar run` workflow,
  preflight mode, or progress UI.
- Human-usability claims unsupported by an actual observed session.
- Changes to financial calculations, public schemas, filenames, report selection, or
  established correctness and scale thresholds.

### Phase 9: Repair the first-run seams

Recommended Codex level: **GPT-5.6 Sol Medium**

Status: **Completed September 4, 2026.**

Make three small, independent repairs:

- Replace the broken final Axys/APX README paragraph with one complete next-step
  instruction. Do not discuss the portable calculation implementation there.
- Translate common portable-core preparation and calculation failures into ppar terms.
  For path failures, identify the rejected user path. Preserve `PparError`, its cause,
  ordinary traceback behavior, and useful structured context; do not add a global
  exception hook or demo-specific suppression.
- Have both generated programs announce that report generation is starting, then print
  a concise completion line with the artifact count and output directory before the
  existing file list. Do not add logging, a progress bar, per-report chatter, a
  preflight mode, or a new CLI execution path.

Implemented:

- The Axys/APX README now ends with one complete instruction for selecting the desired
  portfolio, benchmark, dates, classification, assumptions, and reports.
- Preparation and calculation failures use ppar terminology. CSV-loading errors include
  the supplied path and structured boundary/path context. Existing identity-specific
  messages remain more specific, and every translated failure retains its cause.
- Both generated programs immediately announce report generation and then state the
  artifact count and output directory before listing the files.
- Focused regressions cover the generated instruction, the missing-path text and
  context, preparation and calculation terminology, both successful generated
  workflows, and the preserved whitespace diagnostic.

Validation:

- The routine product gate passed: 335 tests and 501 subtests, mypy, Pyright, both
  Pylint gates, documentation and image provenance, universal-wheel inspection, Twine,
  dependency checking, and both installed-package demonstration workflows.
- The deterministic 12-image gallery was regenerated because its source fingerprint
  includes the generated programs; visual output remained coherent on inspection.
- The unchanged 500x scale gate passed with 6,063,000 scaled rows and byte-equivalent
  report files. The large-site observation was 1.011x baseline time, the selected
  workload was 2.132x at 10x rows, and the gated long-history result was 1.083x at 5x
  rows against unchanged 1.58x warning and 1.65x failure thresholds.

### Phase 10: Add compact report and API orientation

Recommended Codex level: **GPT-5.6 Sol High**

Status: **Completed September 4, 2026.**

Add one concise user guide, or equivalently compact sections in the existing user
documents, that covers:

- every supported `View` and `Chart`, the question it answers, and its output form;
- the risk-statistics groups and the meaning of blank or unavailable cells;
- attribution and risk columns, units, and formulas, linking to methodology instead of
  duplicating its detailed financial explanation;
- when to choose Polars, HTML, PNG, or CSV, including one minimal CSV-writing example;
- which public objects users construct directly and which are returned by `Analytics`
  or `AxysData`; and
- the fact that generated programs are editable copies and do not update automatically
  when ppar is upgraded.

Label the root `Maintenance` link as contributor maintenance. Keep the root README's
short start path and gallery rather than expanding it into a reference manual. Avoid
another end-to-end example, generated API reference, configuration format, or new
public convenience methods.

As part of this phase, assess whether public annotations and docstrings can hide
unsupported `ppar.performance.Performance` and implementation-level `perfattr` names
without changing runtime behavior. Prefer documentation clarity over a factory or
class hierarchy redesign.

Implemented:

- `docs/reports.md` is the single compact guide to result acquisition, all four
  supported `View` choices, all twelve `Chart` choices, standard-bundle membership,
  attribution columns, and all 26 risk-statistic labels.
- The guide records formulas and units, explains blank or unavailable risk cells,
  links the detailed financial methodology, compares Polars, HTML, PNG, and CSV, and
  includes one minimal CSV-writing example.
- Generated programs are identified as editable copies that do not update when ppar
  is upgraded, with a concise regenerate-and-reapply workflow.
- The root README links the guide without expanding the quick start or gallery and
  labels its maintenance link `Contributor maintenance`.
- The Python API guide explains normal object acquisition and no longer introduces
  `perfattr` as a user concept. Public result docstrings identify `Attribution`,
  `AxysPortfolio`, and `AxysClassificationSources` as returned values rather than the
  normal construction path.
- The project documentation check treats the new guide as active documentation.
  Focused contracts require every supported enum and risk label, acquisition and
  upgrade guidance, the format comparison, and an executable CSV example.

Annotation assessment:

- No public signature or runtime behavior changed. `Attribution`'s actual constructor
  still consumes the package's `Performance` container, so replacing that annotation
  would either misdescribe the callable or require the factory/class hierarchy redesign
  this phase explicitly avoided. Documentation and interactive help now direct users
  through `Analytics.attribution()` instead.
- No generated API reference, second end-to-end example, configuration format, or
  convenience method was added. Public schemas, filenames, selected reports, and
  financial calculations are unchanged.

Validation:

- The focused documentation contract passed 13 tests and 47 subtests.
- The complete product gate passed 337 tests and 543 subtests, mypy, Pyright, both
  Pylint gates, documentation and gallery provenance, universal-wheel inspection,
  Twine, dependency checking, and both installed demonstration workflows.
- The deterministic gallery was refreshed because source-docstring fingerprints
  changed; representative visual inspection remained coherent.
- The unchanged 500x scale gate passed with 6,063,000 scaled rows. The large-site
  observation was 0.995x baseline time, the selected workload was 1.970x at 10x rows,
  and the gated long-history result was 1.064x at 5x rows against unchanged 1.58x
  warning and 1.65x failure thresholds.

### Optional output-readability decision

Recommended Codex level: **GPT-5.6 Sol High**

Status: **Assessment candidate only; not currently an implementation phase.**

Render the standard overall-attribution chart with the current shared scale, independent
panel scales, and value labels. Choose the version that best balances comparison across
effects with visibility of small allocation values. Separately decide whether the
financial convention of red-negative and green-positive heatmaps outweighs the
accessibility benefit of avoiding a red-green diverging palette. Preserve numeric
annotations and other non-color cues either way.

Do not combine this choice with Phase 9 or 10. It affects visual interpretation and the
12-image published gallery, so it warrants explicit product-owner review before code or
snapshot changes.

## Completion criteria

- Both generated READMEs end with complete, user-directed instructions and contain no
  accidental implementation fragment.
- A missing input path produces a ppar-owned final message that identifies the path;
  ordinary traceback behavior remains unchanged.
- Both generated programs provide immediate start feedback and a concise artifact-count
  completion summary without introducing a runner or progress framework.
- Users can find a compact catalog of every report choice, a metric and column glossary,
  output-format guidance, and generated-program upgrade guidance.
- Public documentation distinguishes constructible entry points from returned result
  types and does not require users to understand internal `Performance` containers.
- Expected failures retain actionable `PparError` messages and ordinary Python
  traceback behavior; ppar does not install process-wide exception handling.
- Presentation units are explicit and no report displays misleading negative zero or
  indistinguishable axis labels.
- The risk report identifies the approved risk-free-rate, minimum-acceptable-return,
  and confidence-level assumptions; broader provenance remains outside the selected
  Phase 3 scope.
- The standard report bundle retains descriptive filenames; an entry point and
  cross-report navigation remain deliberately deferred with Phase 4.
- The generated vendor-neutral README is sufficient to substitute valid user data.
- The root Python example produces a compact, meaningful overall-return result.
- Direct-array risk output never exposes sentinel dates and documents undefined
  statistics.
- User and contributor documentation are clearly labeled and internally consistent.
- The overall-attribution scale and heatmap palette remain unchanged unless the
  optional output-readability comparison is explicitly approved.
- Public filenames, machine-readable schemas, financial results, and established test
  and scale thresholds remain unchanged unless a separately approved contract change
  is necessary.
