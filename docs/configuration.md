# Demonstration configuration

`ppar setup DIRECTORY` creates the vendor-neutral demonstration. Add `--axys-apx` to
create the Axys/APX demonstration instead. Each directory contains one executable,
extensively commented `ppar_demo.py`. The generated workflow does not provide a
`ppar run` command. Run the script directly:

```bash
python DIRECTORY/ppar_demo.py
```

All relative paths are anchored to the script rather than the shell's current
directory. The script groups its editable Python values near the top and explains how
each affects loading, calculations, or reports.

## Shared calculation settings

Both demonstrations expose corresponding values for:

| Python value | Purpose |
| --- | --- |
| `FROM_DATE`, `THRU_DATE` | Inclusive earliest and latest source-period end dates to retain |
| `CLASSIFICATION` | Primary grouping used for classification reports |
| `FREQUENCY` | Period consolidation; must be fixed when risk statistics are selected |
| `HOLIDAYS` | Headerless file of nonbusiness dates |
| `ANNUAL_MINIMUM_ACCEPTABLE_RETURN` | Downside-risk threshold |
| `ANNUAL_RISK_FREE_RATE` | Annual risk-free return assumption |
| `CONFIDENCE_LEVEL` | Value-at-risk confidence level |
| `PORTFOLIO_VALUE` | Numeric value and currency symbol for monetary risk |
| `SECURITY_VIEWS` | HTML security-level tables to produce |
| `CLASSIFICATION_VIEWS` | HTML classification tables to produce |
| `CLASSIFICATION_CHARTS` | PNG classification charts to produce |
| `INCLUDE_RISK_STATISTICS` | Whether to produce the HTML risk-statistics table |

Date selection uses each complete source period's `thru_date`. For example,
`FROM_DATE = 2024-02-15` retains a February 1–29 source period because that period
ends after the inclusive lower bound. A `THRU_DATE` inside that same source period
excludes it because the period ends after the inclusive upper bound. ppar does not
calculate a partial-period return from a bound inside a source period.

The Axys/APX script additionally defines `PORTFOLIO`, `BENCHMARK`, and
`AXYS_SOURCE_VALUES`. The latter is an ordinary nested dictionary containing source
paths, vendor-column mappings, and classification mappings. `AxysData()` validates
and uses those Python values.

The supported top-level keys in `AXYS_SOURCE_VALUES` are `files`, `mappings`, and
`security_id`. `files` is limited to `portfolio_performance`,
`security_performance`, and `security_master`. Each `mappings` entry identifies a
classification code column and display-name column in `secmast.csv`. `security_id`
is optional and configures composite security identities when the exports do not
provide one shared identifier column. Independent classification files, filters,
display-name overrides, and source-path override dictionaries are outside the focused
Axys/APX contract; use the vendor-neutral `Analytics` inputs for those layouts.

The default Axys/APX demonstration reads `portperf.csv`, `secperf.csv`, and
`secmast.csv`. Its generated README explains the three input contracts, while
`AXYS_SOURCE_VALUES` shows the exact paths and source headings to customize.
Portfolio loading remains separate from report selection: each attribution call
explicitly obtains the Security or selected-classification sources from `AxysData`.

Axys/APX portfolio codes and names are exact text and must be nonblank and free of
surrounding whitespace. When a portfolio is renamed across source periods, ppar uses
the latest name in the retained reporting window and prefixes it with the exact
portfolio code. Physical CSV row order and names outside the selected date window do
not affect report titles.

For each `secperf.csv` row, ppar prefers the weight implied by contribution divided
by a nonzero security return and otherwise uses the reported weight. Exact signed
weights, including short positions, are preserved. Missing weights are inferred only
when the weight-sum and portfolio-return equations determine them uniquely;
underdetermined, contradictory, or infeasible evidence stops the run. Each security
identifier must occur at most once per account and source period because the adapter
cannot safely infer whether duplicate rows are accidental or represent lots.

The vendor-neutral script instead names the portfolio, benchmark, classification, and
mapping CSV paths directly. Its performance files have a header and the columns
`from_date`, `thru_date`, `identifier`, `weight`, and `return`; an optional `name`
column supplies display names. Classification and mapping files are headerless
two-column CSVs.

Performance identifiers and both mapping columns are exact textual identities.
Leading zeroes are preserved. These values must be non-null, nonblank, and free of
surrounding whitespace; meaningful internal spaces are retained.

A classification row pairs an identifier with its display name. Exact duplicate
identifier/name pairs are collapsed; assigning conflicting names to one identifier
stops the run. A mapping row pairs a source identifier with a target classification
identifier. Exact duplicate source/target pairs are also collapsed; assigning
conflicting targets to one source identifier stops the run. An identifier omitted
from a mapping remains its own target. These rules apply equally to CSV and Polars
DataFrame inputs.

## Output

Both scripts visibly select the same curated report bundle. Edit `SECURITY_VIEWS`,
`CLASSIFICATION_VIEWS`, and `CLASSIFICATION_CHARTS` to add, remove, or reorder tables
and charts. Set `INCLUDE_RISK_STATISTICS` to `False` to omit the risk-statistics table.
The scripts list every other available view and chart choice in nearby comments.

When `INCLUDE_RISK_STATISTICS` is `True`, risk statistics are produced only when
`FREQUENCY` is a fixed, valid frequency. With `Frequency.AS_OFTEN_AS_POSSIBLE`, source
periods are preserved and risk statistics are intentionally omitted.

The scripts create `output/` when necessary and write each selected report directly.
A report replaces an existing file with the same name; unrelated files remain in the
directory. If a later report fails, files written earlier in that run remain. Users
can replace these simple loops with file-management behavior suited to their own
applications.
