# Demonstration configuration

`ppar setup DIRECTORY` creates the vendor-neutral demonstration. Add `--axys-apx` to
create the Axys/APX demonstration instead. Each directory contains one executable,
extensively commented `ppar_demo.py`. The generated workflow does not use a YAML
workspace configuration or provide a `ppar run` command. Run the script directly:

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
| `FROM_DATE`, `THRU_DATE` | Inclusive reporting window |
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

The Axys/APX script additionally defines `PORTFOLIO`, `BENCHMARK`, and
`AXYS_SOURCE_VALUES`. The latter is an ordinary nested dictionary containing source
paths, vendor-column mappings, and classification mappings. `AxysData.from_values()`
validates and uses those Python values without reading YAML.

The default Axys/APX demonstration reads `portperf.csv`, `secperf.csv`, and
`secmast.csv`. Its generated README explains the three input contracts, while
`AXYS_SOURCE_VALUES` shows the exact paths and source headings to customize.

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

## Output

Both scripts visibly select the same curated report bundle. Edit `SECURITY_VIEWS`,
`CLASSIFICATION_VIEWS`, and `CLASSIFICATION_CHARTS` to add, remove, or reorder tables
and charts. Set `INCLUDE_RISK_STATISTICS` to `False` to omit the risk-statistics table.
The scripts list every other available view and chart choice in nearby comments.

When `INCLUDE_RISK_STATISTICS` is `True`, risk statistics are produced only when
`FREQUENCY` is a fixed, valid frequency. With `Frequency.AS_OFTEN_AS_POSSIBLE`, source
periods are preserved and risk statistics are intentionally omitted.

Each successful run atomically replaces `output/` with the complete new bundle. If
loading, calculation, report rendering, or publication fails, the previous successful
output remains intact.
