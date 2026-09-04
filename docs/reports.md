# Reports and results

Use this guide to choose an output, interpret its columns and risk metrics, and decide
whether presentation or machine-readable output is the better fit. See
[Methodology](methodology.md) for the detailed financial model and
[Python API](python_api.md) for input configuration.

## Obtain result objects

| Object | Normal entry point |
| --- | --- |
| `Analytics` | Construct from portfolio and optional benchmark CSV paths or Polars DataFrames. |
| `AxysData` | Construct from an Axys/APX base directory and source mapping. |
| `RiskStatistics` | Construct directly only for a portfolio/benchmark pair of NumPy arrays. |
| `Attribution` | Receive from `Analytics.attribution()` or `Analytics.attribution_for()`. |
| `AxysPortfolio` | Receive from `AxysData.get_portfolio()` or `get_portfolios()`. |
| `AxysClassificationSources` | Receive from an `AxysData` classification-source method. |

Import `View` and `Chart` from `ppar.attribution`, `Frequency` from `ppar.frequency`,
and `PparError` from `ppar.errors`. The string constants in `ppar.schema` are useful
when preparing inputs or selecting Polars columns. Returned objects remain supported
public types; the table identifies their normal acquisition path rather than removing
them from the public API.

## Attribution table views

Pass one of these values to `Attribution.to_polars()`, `to_html()`, or `write_csv()`.

| `View` | Row grain and use | Standard demo |
| --- | --- | --- |
| `CUMULATIVE_ATTRIBUTION` | Period totals through time plus final total. | Classification |
| `OVERALL_ATTRIBUTION` | Item totals for the full range plus final total. | Both |
| `SUBPERIOD_ATTRIBUTION` | One row per period and item. | No |
| `SUBPERIOD_SUMMARY` | One total row per period. | No |

Sorting is available for every view except chronological `CUMULATIVE_ATTRIBUTION`.
Use the cumulative view to follow linked results, overall attribution to rank drivers,
subperiod attribution to investigate item detail in one period, and the summary to
compare total returns and effects by period. The generated program demonstrates the
selected view tuples and report-writing loops.

## Attribution charts

Pass one of these values to `Attribution.to_chart()`. Every chart is returned as PNG
bytes. “Standard” means that the unmodified generated program writes the chart.

| `Chart` | Question answered | Standard |
| --- | --- | --- |
| `CUMULATIVE_ATTRIBUTION` | Linked effects through time. | Yes |
| `CUMULATIVE_CONTRIBUTION` | Linked total contributions through time. | No |
| `CUMULATIVE_RETURN` | Compounded return paths. | Yes |
| `HEATMAP_ACTIVE_CONTRIBUTION` | Active contribution by item and period. | Yes |
| `HEATMAP_ACTIVE_RETURN` | Active group return by item and period. | No |
| `HEATMAP_ATTRIBUTION` | Total effect by item and period. | Yes |
| `HEATMAP_PORTFOLIO_CONTRIBUTION` | Portfolio contribution by item and period. | No |
| `HEATMAP_PORTFOLIO_RETURN` | Portfolio return by item and period. | No |
| `OVERALL_ATTRIBUTION` | Full-range effects by item. | Yes |
| `OVERALL_CONTRIBUTION` | Full-range portfolio and benchmark contribution. | Yes |
| `SUBPERIOD_ATTRIBUTION` | Total effects by period. | Yes |
| `SUBPERIOD_RETURN` | Portfolio, benchmark, and active return by period. | No |

The subperiod and cumulative charts show totals across the requested classification;
the heatmaps and overall charts show classification-item detail.

## Attribution column glossary

For one period and item, let `wP` and `wB` be portfolio and benchmark weights, `rP`
and `rB` their item returns, and `RB` the total benchmark return. Values are numeric
decimals in Polars and CSV output, so `0.05` means 5%. HTML and PNG output present
return-like values as percentages.

| Column or pattern | Meaning |
| --- | --- |
| `from_date`, `thru_date` | Inclusive source or consolidated reporting period. |
| `Classification_Identifier`, `Classification_Name` | Stable item key and label. |
| `Portfolio_Weight`, `Benchmark_Weight` | Item weights `wP` and `wB`. |
| `Portfolio_Return`, `Benchmark_Return` | Item or total returns `rP` and `rB`. |
| `Portfolio_Contribution_Simple` | Within-period portfolio contribution `wP * rP`. |
| `Benchmark_Contribution_Simple` | Within-period benchmark contribution `wB * rB`. |
| `Active_Weight` | `wP - wB`. |
| `Active_Return` | Item `rP - rB`; summary portfolio return minus benchmark return. |
| `Active_Contribution_Simple` | Portfolio contribution minus benchmark contribution. |
| `Allocation_Effect_Simple` | Brinson-Fachler `(wP - wB) * (rB - RB)`. |
| `Selection_Effect_Simple` | Portfolio-weighted `wP * (rP - rB)`. |
| `Total_Effect_Simple` | Allocation plus selection. |
| Names ending in `_Smoothed` | Corresponding value after Carino linking. |
| Names beginning with `Cumulative_` | Value accumulated through that period. |
| `Total_Return` | Source-period portfolio return derived as the sum of holding contributions. |

Overall weights are averaged by elapsed days in accepted source periods. A zero-net
signed group can have an undefined return but a defined contribution. In that case,
the total effect remains active contribution minus `(wP - wB) * RB`; selection carries
the residual when allocation cannot use a benchmark group return. Smoothed item and
period detail foot to linked total return. See
[Methodology](methodology.md#contribution-and-attribution) for those cases, period
alignment, and conservation behavior.

## Risk-statistics table

`Analytics.risk_statistics()` returns a named and dated `RiskStatistics` result.
Direct construction from arrays uses neutral portfolio and benchmark names and has no
date range. `to_polars()`, `to_html()`, and `write_csv()` expose the same five groups:

| Group | Purpose |
| --- | --- |
| Absolute Risk | Return level and dispersion for each series. |
| Downside Risk | Results below the configured minimum acceptable return. |
| Benchmark-Relative Risk | Co-movement and active-return dispersion. |
| Risk-Adjusted Performance | Return relative to volatility, downside risk, active risk, or beta. |
| Regression | Portfolio sensitivity and intercept-like returns relative to the benchmark. |

Let `P` and `B` be aligned periodic return arrays, `A = P - B`, `n` the observation
count, `m` the periods per year, and `V` the configured portfolio value. `Rf` and `MAR`
are periodic rates obtained by compounding down the configured annual risk-free and
minimum acceptable rates. `sd` denotes population standard deviation, matching the
displayed risk calculations.

| Statistic | Definition and displayed unit |
| --- | --- |
| Return Range | `max(R) - min(R)`; percentage. |
| Mean Return | Arithmetic `mean(R)`; percentage. |
| Annualized Mean Return | `(1 + mean(R))^m - 1`; percentage. |
| Standard Deviation | `sd(R)`; percentage. |
| Annualized Standard Deviation | `sqrt(m) * sd(R)`; percentage. |
| Downside Probability | `count(R < MAR) / n`; percentage. |
| Expected Downside Value | `sum(min(R - MAR, 0)) / n`; percentage, normally nonpositive. |
| Downside Deviation / Annualized Downside Deviation | Root-mean-square shortfall; percentage. |
| Value At Risk | `max(0, -(mean(R) + z(1-confidence) * sd(R)) * V)`; currency loss. |
| Correlation | Pearson correlation of `P` and `B`; dimensionless. |
| R-Squared | `Correlation^2`; dimensionless. |
| Tracking Error / Annualized Tracking Error | `sd(A)`; percentage. |
| Sharpe Ratio / Annualized Sharpe Ratio | `(mean(R) - Rf) / sd(R)`; dimensionless. |
| Sortino Ratio / Annualized Sortino Ratio | Excess over `MAR` divided by downside deviation. |
| Information Ratio | `mean(A) / sd(A)`; dimensionless and portfolio-only. |
| M-Squared | `Sharpe(P) * sd(B) + Rf`; percentage and portfolio-only. |
| Treynor Ratio | `(mean(P) - Rf) / Beta`; percentage and portfolio-only. |
| Beta | Sample `cov(P, B) / var(B)`; dimensionless and portfolio-only. |
| Alpha / Annualized Alpha | `mean(P) - Beta * mean(B)`; portfolio-only percentage. |
| Jensen's Alpha / Annualized Jensen's Alpha | CAPM-adjusted portfolio-only percentage. |

The `Difference` column is portfolio minus benchmark when both values exist.
Benchmark-relative and regression statistics have no separate benchmark comparator,
so those cells are unavailable. Annualized values are also unavailable with less than
one full year of observations. Annualized volatility and ratios multiply by `sqrt(m)`;
annualized Alpha and Jensen's Alpha compound as `(1 + value)^m - 1`. Constant or
resolution-limited source variation can make correlation, beta, or a ratio unavailable;
a nonzero numerator over observable zero risk can instead produce signed infinity.
HTML presents unavailable cells as blank, while machine-readable output retains the
numeric missing-value representation.

Downside deviation is `sqrt(mean(min(R - MAR, 0)^2))`. Sortino is
`(mean(R) - MAR) / Downside Deviation`. Jensen's Alpha is
`(mean(P) - Rf) - Beta * (mean(B) - Rf)`.

## Choose an output format

| Format | Best use | Behavior |
| --- | --- | --- |
| Polars | Analysis, tests, notebooks, or applications. | In-memory decimal values. |
| CSV | Spreadsheet or durable machine handoff. | Written decimal values. |
| HTML | Human review of complete tables. | Standalone presentation page. |
| PNG | Presentations and quick visual review. | In-memory chart bytes. |

CSV writing needs no additional reporting layer:

```python
from pathlib import Path

from ppar.attribution import View

attribution.write_csv(View.OVERALL_ATTRIBUTION, Path("overall_attribution.csv"))
risk.write_csv(Path("risk_statistics.csv"))
```

The generated programs demonstrate saving HTML strings and PNG bytes. Applications
remain responsible for filenames, directory layout, and replacement policy.

## Generated programs and upgrades

`ppar setup` copies the current demonstration README, program, and input files into a
new directory. That editable copy does not change when ppar is upgraded. To adopt a
new template, create a fresh setup directory with the upgraded version, compare its
`ppar_demo.py` and README with the existing copy, and reapply only the site-specific
paths, account choices, assumptions, and report selections. Setup deliberately refuses
to write into a nonempty directory.
