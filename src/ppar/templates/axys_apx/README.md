# ppar Axys/APX demonstration

Run the tutorial-style demonstration script from any working directory:

```bash
python __PPAR_DEMO_PATH__
```

## Use your own Axys/APX exports

The demonstration reads three CSV files:

| File | Contents |
| --- | --- |
| `portperf.csv` | One row per account and source period |
| `secperf.csv` | One row per security, account, and source period |
| `secmast.csv` | One row per security |

The demonstration maps these ppar fields:

```text
portperf.csv:
  from_date, thru_date, portfolio_code, portfolio_name, portfolio_return
secperf.csv:
  from_date, thru_date, portfolio_code, security_symbol, security_type,
  weight, security_return, contribution
secmast.csv:
  security_symbol, security_type, security_name, classification codes and names
```

These filenames and fields form ppar's demonstration contract. They are not
guaranteed native Axys/APX object, profile, report, filename, or column names because
export formats vary by site.

`portfolio_code` and `portfolio_name` are text. Surrounding whitespace is removed,
and values that are then blank are rejected. A name may change across source periods;
ppar uses the latest name in the retained reporting window and prefixes it with the
portfolio code in output titles.

`AXYS_SOURCE_VALUES` in `ppar_demo.py` maps each file path and ppar field to the exact
heading used by your exports. Replace the demonstration CSV files in `input/`, or
point those paths to files elsewhere, and update the headings as needed.

The script loads the portfolio and benchmark first, then explicitly selects the
classification sources for each attribution report.

Returns, weights, and contributions are decimals: `0.05` means 5%. The demonstrated
security identity combines `security_type` and `security_symbol`, so those fields must
identify the same securities in `secperf.csv` and `secmast.csv`. Each entry under
`mappings` identifies the `secmast.csv` columns containing a classification code and
its displayed name.

The supported top-level settings are `files`, `mappings`, and the optional
`security_id`. Classifications for this Axys/APX workflow come from `secmast.csv`;
independent classification files and filters are not part of this source contract.

ppar reconciles the security-level performance in `secperf.csv` to the corresponding
reported account return in `portperf.csv`. It prefers the weight implied by
contribution divided by a nonzero security return and otherwise uses the reported
weight. Exact signed weights, including short positions, are preserved. Missing
weights are inferred only when the weight-sum and portfolio-return equations
determine them uniquely. Underdetermined, contradictory, infeasible, or materially
unreconciled account periods stop the run instead of producing reports from
inconsistent inputs.

Each security identifier must occur at most once per account and source period.
Duplicate rows are rejected because ppar cannot safely infer whether they are
accidental duplicates or separate lots requiring a site-specific aggregation rule.

Finally, edit `ppar_demo.py` to select the portfolio, benchmark, dates,
classification, calculation assumptions, and reports you want to produce. Leave
Attribution calculations use the portable `perfattr` core.
