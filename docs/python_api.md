# Python API

The root API is deliberately small: `from ppar import Analytics, __version__`.

The complete supported Python surface is:

- `ppar`: `Analytics`, `__version__`
- `ppar.attribution`: `Attribution`, `Chart`, `View`
- `ppar.axys_apx`: `AxysClassificationSources`, `AxysData`, `AxysPortfolio`
- `ppar.errors`: `PparError`
- `ppar.frequency`: `Frequency`
- `ppar.risk`: `RiskStatistics`
- `ppar.schema`: the names listed in that module's `__all__`

Other modules, classes, and helpers are implementation details. In particular,
`ppar.tables` and `ppar.utilities` are not supported application interfaces.

The normal object-acquisition paths are deliberately narrower than that supported
surface:

- Construct `Analytics` for ordinary CSV or Polars inputs and `AxysData` for Axys/APX
  exports.
- Receive `Attribution` from `Analytics.attribution()` or `attribution_for()`.
- Receive `AxysPortfolio` and `AxysClassificationSources` from `AxysData` methods.
- Construct `RiskStatistics` directly only for a portfolio/benchmark pair of NumPy
  arrays; `Analytics.risk_statistics()` supplies named and dated results otherwise.

See [Reports and results](reports.md) for the complete `View` and `Chart` catalog,
column and risk-metric glossary, format choices, and generated-program upgrade
guidance.

ppar has no complete-workspace `run()` API. The setup-generated `ppar_demo.py` shows
the full executable workflow with Python values.

## Analytics

The root README contains the shortest complete `Analytics` example. The generated
`ppar_demo.py` is the canonical full workflow for configuring calculations, selecting
reports, and saving them. This page does not duplicate those examples.

The portfolio and optional benchmark are the only positional constructor arguments.
Names, classifications, dates, frequency, holidays, and risk assumptions are
keyword-only so their meaning remains visible at each call site.

Portfolio-return, classification, and mapping table inputs accept only a CSV path or
a Polars DataFrame. Focused types and lower-level APIs live in `ppar.attribution`,
`ppar.frequency`, `ppar.risk`, and `ppar.axys_apx`.

ppar validates and aligns source periods, applies classification mappings and reporting
frequency, and checks that attribution results reconcile. The
[Methodology](methodology.md) guide describes the financial behavior without requiring
application code to use implementation-level objects.

### Results and files

| Result | Public method | Value or action |
| --- | --- | --- |
| Attribution table | `Attribution.to_polars(view)` | Returns a Polars DataFrame. |
| Attribution HTML | `Attribution.to_html(view)` | Returns an HTML string. |
| Attribution chart | `Attribution.to_chart(chart)` | Returns PNG bytes. |
| Attribution CSV | `Attribution.write_csv(view, path)` | Writes a CSV file. |
| Risk table | `RiskStatistics.to_polars()` | Returns a Polars DataFrame. |
| Risk HTML | `RiskStatistics.to_html()` | Returns an HTML string. |
| Risk CSV | `RiskStatistics.write_csv(path)` | Writes a CSV file. |

Applications choose where and how HTML and PNG reports are stored. Save HTML with
`path.write_text(attribution.to_html(view), encoding="utf-8")` and PNG with
`path.write_bytes(attribution.to_chart(chart))`, as demonstrated by `ppar_demo.py`.
Keeping these values in memory also supports notebooks, web responses, and custom
storage without temporary files.

## Direct risk arrays

The lower-level risk API also accepts a portfolio and benchmark pair of
one-dimensional NumPy arrays:

```python
import numpy as np

from ppar.frequency import Frequency
from ppar.risk import RiskStatistics

risk = RiskStatistics(
    (
        np.array([0.01, -0.02, 0.03, 0.02, 0.00, 0.01] * 2),
        np.array([0.00, -0.01, 0.02, 0.01, 0.01, 0.00] * 2),
    ),
    Frequency.MONTHLY,
)
```

The two arrays must have the same length and contain at least two finite, real
numeric returns. Annualized statistics require a full year of observations: 12
monthly, 4 quarterly, or 1 yearly; the general two-observation minimum still applies.
Shorter valid samples retain the nonannualized statistics and report annualized values
as unavailable. Every periodic return must be greater than -100%. Accepted integer
and floating arrays are normalized to `float64` before calculation, and risk statistics
require a fixed monthly, quarterly, or yearly frequency. Arrays contain no names or
dates, so their HTML uses `Portfolio` and `Benchmark` and omits the date range. Use
`Analytics.risk_statistics()` when source names and dates should appear.

Risk-ratio denominators use the floating-point resolution of their source returns,
not a fixed absolute cutoff. Small observable volatility, downside deviation,
tracking error, and signed beta values retain finite ratios. Exact or
resolution-limited zero risk produces `NaN` for a zero numerator and signed infinity
for a nonzero numerator; an undefined beta keeps the Treynor ratio undefined.

## Axys/APX values

`AxysData(base_directory, values)` configures Axys/APX loading from an ordinary Python
mapping. Relative source paths are resolved against `base_directory`. The supported
top-level keys are `files`, `mappings`, and `security_id`:

- `files` configures the paths and exact source-column mappings for
  `portfolio_performance`, `security_performance`, and `security_master`.
- `mappings` names classifications stored in `secmast.csv`. Each entry specifies a
  `classification_column` and `display_name_column`.
- `security_id` optionally configures a composite security identifier, including
  per-dataset source columns when the two exports differ.

External classification files, classification filters, display-name overrides, and
source-path override dictionaries are not part of the Axys/APX API. Use generic
`Analytics` classification and mapping inputs when independent lookup files are
required. The generated Axys/APX demonstration contains the complete focused example.

Generic `Analytics.attribution(..., mapping_data_sources=...)` accepts either static
two-column mappings (`identifier, classification_identifier`) or effective-dated
four-column mappings (`from_date, thru_date, identifier,
classification_identifier`). CSV mappings are headerless; Polars mappings are
positional. Effective dates are closed and inclusive, and each source period for a
mapped identifier must fit wholly within one assignment. `ppar` translates the host
container, then validates assignments and reconciles the resulting attribution data.

Axys/APX mapping remains static because its configured classification source is one
undated security-master snapshot. `ppar` does not invent historical assignments from
that snapshot. Use the generic mapping input only when an authoritative dated mapping
source is available.

`AxysData.get_classification_sources_for_pair()` combines classification names and
portfolio/benchmark mappings for two reconciled Axys portfolios. Its
`AxysClassificationSources` result can be passed directly to
`Analytics.attribution_for()`. The Axys/APX demonstration uses this explicit pairing
for both its security-level and selected-classification reports. For portfolio-only
analytics, use `AxysData.get_classification_sources()` with the one reconciled
portfolio. `AxysPortfolio.to_analytics()` accepts an optional reconciled
`AxysPortfolio` benchmark; frequency, holiday, and risk assumptions are keyword-only.
Select the reporting date window when loading both portfolios with
`AxysData.get_portfolio()` or `get_portfolios()`.

Surrounding whitespace is removed from portfolio codes and names, and values that are
then blank are rejected. A portfolio rename is permitted across periods;
`AxysPortfolio.portfolio_name` contains the code and the latest name within the
retained `AxysData.get_portfolio()` date window. CSV row order and later unselected
periods do not change that display name.

Attribution HTML tables include every result row. For very large results,
`to_polars()` or `write_csv()` may be more practical than opening a large HTML file.

The generated demonstrations show ordinary loops for selecting and writing multiple
HTML and PNG reports. Applications remain free to choose their own filenames,
directory layout, replacement behavior, and error-recovery policy. Expected
validation and calculation failures use `ppar.errors.PparError`; its message is
intended for people, and optional `context` contains independent diagnostic values.
