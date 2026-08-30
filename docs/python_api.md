# Python API

The root API is deliberately small:

```python
from ppar import Analytics, __version__
```

ppar has no complete-workspace `run()` API. The setup-generated `ppar_demo.py` shows
the full executable workflow with ordinary Python values.

## Analytics

```python
from ppar import Analytics
from ppar.attribution import Chart, View
from ppar.frequency import Frequency

analytics = Analytics(
    "portfolio.csv",
    "benchmark.csv",
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

Performance, classification, and mapping table inputs accept only a CSV path or a
Polars DataFrame. Focused types and lower-level APIs live in `ppar.attribution`,
`ppar.frequency`, `ppar.risk`, and `ppar.axys_apx`.

## Axys/APX values

`AxysData.from_values(base_directory, values)` configures Axys/APX loading from an
ordinary Python mapping. Relative source paths are resolved against `base_directory`.
The default setup demonstration contains a complete, commented example.

`AxysData.get_classification_sources_for_pair()` combines classification names and
portfolio/benchmark mappings for two reconciled Axys portfolios. Its result can be
passed directly to `Analytics.attribution_for()`; the Axys/APX demonstration uses
this method for its security-level report.

## Atomic publication

Applications that create multiple reports can use the same publication primitive as
the generated demonstrations:

```python
from pathlib import Path

from ppar.publication import atomic_output_directory

output = Path("output")
with atomic_output_directory(output) as staging:
    (staging / "report.html").write_text("<p>complete</p>", encoding="utf-8")
```

The context replaces the destination only after its body succeeds. Expected validation
and calculation failures use `ppar.errors.PparError`; its message is intended for
people, and optional `context` contains independent diagnostic values.
