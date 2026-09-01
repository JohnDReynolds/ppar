# Python API

The root API is deliberately small:

```python
from ppar import Analytics, __version__
```

The complete supported Python surface is:

- `ppar`: `Analytics`, `__version__`
- `ppar.attribution`: `Attribution`, `Chart`, `View`
- `ppar.axys_apx`: `AxysClassificationSources`, `AxysData`, `AxysPortfolio`
- `ppar.errors`: `PparError`
- `ppar.frequency`: `Frequency`
- `ppar.publication`: `atomic_output_directory`, `write_report_bundle`
- `ppar.risk`: `RiskStatistics`
- `ppar.schema`: the names listed in that module's `__all__`

Other modules, classes, and helpers are implementation details. In particular,
`ppar.tables` and `ppar.utilities` are not supported application interfaces.

ppar has no complete-workspace `run()` API. The setup-generated `ppar_demo.py` shows
the full executable workflow with ordinary Python values.

## Analytics

```python
from pathlib import Path

from ppar import Analytics
from ppar.attribution import Chart, View
from ppar.frequency import Frequency

performance_input_directory = Path("./my_ppar") / "input" / "performance"

analytics = Analytics(
    performance_input_directory / "Mega-Cap Alpha Portfolio.csv",
    performance_input_directory / "Mega-Cap Benchmark.csv",
    frequency=Frequency.QUARTERLY,
)
attribution = analytics.attribution()

frame = attribution.to_polars(View.OVERALL_ATTRIBUTION)
html = attribution.to_html(View.OVERALL_ATTRIBUTION)
png = attribution.to_chart(Chart.OVERALL_ATTRIBUTION)
attribution.write_csv(View.OVERALL_ATTRIBUTION, "overall.csv")

risk = analytics.risk_statistics()
risk_frame = risk.to_polars()
risk_html = risk.to_html()
risk.write_csv("risk.csv")
```

The portfolio and optional benchmark are the only positional constructor arguments.
Names, classifications, dates, frequency, holidays, and risk assumptions are
keyword-only so their meaning remains visible at each call site.

Performance, classification, and mapping table inputs accept only a CSV path or a
Polars DataFrame. Focused types and lower-level APIs live in `ppar.attribution`,
`ppar.frequency`, `ppar.risk`, and `ppar.axys_apx`.

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
`Performance` inputs when source names and dates should appear.

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

`AxysData.get_classification_sources_for_pair()` combines classification names and
portfolio/benchmark mappings for two reconciled Axys portfolios. Its
`AxysClassificationSources` result can be passed directly to
`Analytics.attribution_for()`. The Axys/APX demonstration uses this explicit pairing
for both its security-level and selected-classification reports. For portfolio-only
analytics, use `AxysData.get_classification_sources()` with the one reconciled
portfolio. `AxysPortfolio.to_analytics()` accepts an optional positional benchmark;
all remaining options are keyword-only.

Portfolio codes and names are validated as exact, nonblank text. A portfolio rename
is permitted across periods; `AxysPortfolio.portfolio_name` contains the exact code
and the latest name within the retained `AxysData.get_portfolio()` date window. CSV
row order and later unselected periods do not change that display name.

Attribution HTML tables are limited to 1,010 rows. For larger results, use
`to_polars()` or `write_csv()` rather than `to_html()`.

## Report bundles and transactional publication

`write_report_bundle()` writes any selected combination of security views,
classification views, classification charts, and risk statistics. Report categories
that are not needed can be omitted. The generated demonstrations combine it with
`atomic_output_directory()` so a complete bundle replaces the prior output only after
every selected report succeeds:

Continuing with `analytics`, `attribution`, and `risk` created above:

```python
from ppar.publication import atomic_output_directory, write_report_bundle

output_directory = Path("./my_ppar") / "output"

with atomic_output_directory(output_directory) as staging_directory:
    output_names = write_report_bundle(
        output_directory=staging_directory,
        security_attribution=attribution,
        security_views=(View.OVERALL_ATTRIBUTION,),
        risk_statistics=risk,
    )
```

`write_report_bundle()` returns the filenames in display order. It requires at least
one selected report and validates that each selected category has its corresponding
calculation. Repeated selections and values of the wrong enum type are rejected before
any report is written. The context provides rollback safety for Python exceptions and
interruptions; it does not claim process-crash atomicity. On success, it replaces the
entire destination directory, so unrelated files in the prior directory are not
retained. Call `write_report_bundle()` directly to write into a directory without
that replacement behavior. Expected validation and calculation failures use
`ppar.errors.PparError`; its message is intended for people, and optional `context`
contains independent diagnostic values.
