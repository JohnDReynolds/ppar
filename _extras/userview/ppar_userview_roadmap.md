# ppar User-View Roadmap

Status: Complete with deliberate exclusions; Phases 0, 2, 3, 5, 6, 7, and 8
completed, Phase 1 rejected, Phase 4 deferred, and independent second-user observation
retained as an optional external follow-up  
Assessment date: September 2, 2026

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

> The analytics engine appears rigorous and trustworthy, and the demonstration is
> impressively easy to start. However, the surrounding workflow and reports still
> feel like a developer-oriented evaluation kit rather than a finished product for
> portfolio analysts.

The calculations inspire more confidence than the current product shell. The main
risk is that the user-facing layer makes a carefully engineered analytics package
feel less mature than it is.

## What works particularly well

- The two-command start is concise and immediately executable:

  ```bash
  ppar setup ./my_ppar
  python ./my_ppar/ppar_demo.py
  ```

- `ppar -h` and `ppar setup -h` clearly explain `DIRECTORY`, the default data source,
  and the Axys/APX option.
- Setup refuses to overwrite a nonempty directory.
- Both demonstrations run quickly and immediately produce the advertised 11 reports.
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

## User-facing findings

### 1. Expected input failures look like programming failures

A missing or malformed input encountered by `ppar_demo.py` produces a complete Python
traceback. Its final `PparError` message can be useful, but the user must read through
implementation paths and stack frames to find it.

Decision: do not add demo-specific traceback suppression or install a process-wide
exception hook. ppar remains a Python library whose public APIs raise ordinary
exceptions, including structured `PparError` context where available. Improving
individual unclear messages remains worthwhile and is retained in Phase 7.

### 2. Report units are ambiguous

Tables and charts display returns, weights, contributions, and effects as raw decimals
such as `0.8339` and `0.0656`. A knowledgeable user may infer 83.39% and 6.56%, but a
presentation report should not require that inference.

Related presentation problems include:

- `-0.0000` values in tables and heatmaps;
- chart axes on which several distinct ticks render as `0.00`;
- heatmaps filled with small decimals rather than percentages or basis points; and
- column headings and chart axes without explicit units.

Presentation output should use deliberate percentage or basis-point formatting while
machine-readable Polars and CSV output retains numeric decimals.

### 3. Reports lack important review context

The risk report does not display the configured risk-free rate, minimum acceptable
return, VaR confidence level, or complete portfolio-value assumption. Report files
also lack the ppar version, creation date, and source or configuration provenance.

The Axys/APX documentation explains that weights may be inferred or adjusted during
reconciliation, but the report bundle contains no reconciliation summary showing what
changed. An analyst can review the calculated values, but an auditor or investment
committee reviewer still needs the script and source files to understand how the
reports were produced.

### 4. The report bundle has no entry point

The 11 descriptive filenames are useful, but users receive a directory of unrelated
HTML and PNG files and must decide where to begin. The HTML pages do not link to one
another and lack a useful document title, report summary, download links, and sticky
headings for long security tables.

A small `index.html` should summarize the run and link every artifact. The standard
workflow should also consider selectable CSV artifacts: CSV is an advertised public
output, but the generated scripts currently select only HTML and PNG reports.

### 5. The generated vendor-neutral README is too sparse

The Axys/APX README provides a substantial input contract, while the vendor-neutral
README contains only the execution command, required performance headings, and the
fact that classification and mapping files have two columns.

A user replacing demonstration data still needs a concise explanation of:

- column meanings and units;
- date and period rules;
- portfolio and benchmark coverage requirements;
- classification and mapping file orientation;
- display-name behavior; and
- common validation failures.

Setup explicitly sends the user to this generated README, so it should be sufficient
for the next step without requiring discovery of explanations inside the generated
script. Reports are written directly to `output/`; the earlier statement that a
successful run replaces the complete directory is obsolete.

### 6. The introductory Python example produced too much output

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
208- or 250-line starter program, and a collection of static report files. This is a
reasonable design, but some users will initially expect a conventional CLI reporting
application.

The product should describe itself explicitly as a Python analytics library with a
generated, editable reporting program. Phase 7 removed the potentially misleading
phrase "self-contained demonstration directory" because the generated script still
depends on the installed ppar package. Broader positioning remains a separate product
decision.

For users who are not Python developers, a preflight validation mode, visible progress
during long runs, and a concise run summary would materially improve the workflow
without requiring a YAML configuration or restoring `ppar run`.

### 9. User documentation has important gaps

The documentation spine is concise, but it lacks:

- a report catalog explaining each `View` and `Chart`;
- an output-column glossary with formulas and units;
- a troubleshooting guide organized by common input errors;
- a complete vendor-neutral input reference;
- guidance for updating a generated script when ppar is upgraded; and
- a clear separation between user documentation and contributor maintenance.

Phase 7 made the 45-day single-user evaluation term and a direct commercial-licensing
contact visible before installation. The remaining documentation gaps above were not
expanded into Phase 7.

### 10. Smaller polish issues weakened the finished impression — resolved

Status: **Resolved across Cleanup Phase 7 and User-View Phase 7.**

- Cleanup Phase 7 corrected the `Attribution` docstring, risk-statistic labels,
  multi-dot filename handling, HTML row-limit error, and publication terminology.
- User-View Phase 7 replaced the remaining known internal-looking audit messages with
  plain descriptions.
- HTML reports now include document titles, responsive viewport metadata, accessible
  table labels and header scopes, and sticky column headings.
- Charts now use a color-vision-friendly series and sign palette. Legends, labels,
  bar positions, and zero axes remain redundant cues rather than relying on color
  alone. Heatmaps use a blue-to-red diverging scale instead of red and green.

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
  vermillion colors. Sign charts use blue and vermillion rather than green and red,
  and heatmaps use a blue-to-red diverging scale. Existing text, position, direction,
  legends, and zero axes preserve non-color cues.
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

## Completion criteria

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
- User and contributor documentation are clearly separated and internally consistent.
- Public filenames, machine-readable schemas, financial results, and established test
  and scale thresholds remain unchanged unless a separately approved contract change
  is necessary.
