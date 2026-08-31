# Python API

The root API is deliberately small:

```python
from ppar import Analytics, __version__
```

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

Performance, classification, and mapping table inputs accept only a CSV path or a
Polars DataFrame. Focused types and lower-level APIs live in `ppar.attribution`,
`ppar.frequency`, `ppar.risk`, and `ppar.axys_apx`.

## Axys/APX values

`AxysData.from_values(base_directory, values)` configures Axys/APX loading from an
ordinary Python mapping. Relative source paths are resolved against `base_directory`.
The Axys/APX demonstration contains a complete, commented example.

`AxysData.get_classification_sources_for_pair()` combines classification names and
portfolio/benchmark mappings for two reconciled Axys portfolios. Its result can be
passed directly to `Analytics.attribution_for()`; the Axys/APX demonstration uses
this method for its security-level report.

## Report bundles and atomic publication

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
calculation. The atomic context replaces the destination only after its body succeeds.
Expected validation and calculation failures use `ppar.errors.PparError`; its message
is intended for people, and optional `context` contains independent diagnostic values.
