# Python API

The root API is deliberately small:

```python
from ppar import Analytics, run, __version__
```

`run(workspace=".")` executes the same complete workflow as `ppar run` and returns a
frozen `RunResult` with `workspace`, `output_directory`, and `artifacts`.

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

Expected validation and calculation failures use `ppar.errors.PparError`. Its message
is intended for people; optional `context` contains independent diagnostic values.
