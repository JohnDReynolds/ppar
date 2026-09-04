# ppar

Portfolio performance attribution, contribution, and ex-post risk analytics.

ppar compares a portfolio with a benchmark, explains active return by classification,
and produces reviewable HTML tables and PNG charts. It runs locally and accepts
vendor-neutral CSV files or Axys/APX exports.

## Start here

ppar supports Python 3.11.9 through Python 3.14.

ppar is available under a 45-day, single-user internal evaluation license.
Production, commercial, multi-user, or continued use requires a separate agreement;
contact `jjjkreynolds@gmail.com`. Review the [license](LICENSE) before installing.

```bash
python -m pip install ppar
```

Then choose one demonstration.

Vendor-neutral (the default):

```bash
ppar setup ./my_ppar
python ./my_ppar/ppar_demo.py
```

Axys/APX:

```bash
ppar setup ./my_ppar --axys-apx
python ./my_ppar/ppar_demo.py
```

Either setup command creates a demonstration directory:

```text
my_ppar/
  README.md
  ppar_demo.py
  input/
  output/
```

The extensively commented `ppar_demo.py` is both a tutorial and the executable
workflow. Edit its Python values to choose input paths, calculation assumptions, and
reports, then replace the demonstration files under `input/` with your data.

## What it produces

The standard demonstration writes security and classification attribution tables,
attribution and contribution charts, cumulative return charts, heatmaps, and an
ex-post risk-statistics table.

The gallery below shows examples of available output, including reports that can be
selected by editing `ppar_demo.py`.

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/OverallAttributionByEconomicSector.png" alt="Overall attribution by economic sector chart" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/OverallContributionByEconomicSector.png" alt="Overall contribution by economic sector chart" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/SubPeriodAttributionEffectsByEconomicSector.png" alt="Sub-period attribution effects chart" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/SubPeriodReturns.png" alt="Sub-period portfolio and benchmark returns" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/ActiveContributionsByEconomicSector.png" alt="Active contributions heatmap" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/TotalAttributionEffectsByEconomicSector.png" alt="Total attribution effects heatmap" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/CumulativeAttributionEffectsByEconomicSector.png" alt="Cumulative attribution effects" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/CumulativeReturns.png" alt="Cumulative portfolio and benchmark returns" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/CumulativeAttributionByEconomicSector.jpg" alt="Cumulative attribution table" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/OverallAttributionByEconomicSector.jpg" alt="Overall attribution table by economic sector" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/OverallAttributionBySecurity.jpg" alt="Overall attribution table by security" width="100%" />

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/RiskStatistics.jpg" alt="Ex-post risk statistics table" width="50%" />

## Python

This prints the overall portfolio, benchmark, and active returns as decimals:

```python
from pathlib import Path

from ppar import Analytics
from ppar.attribution import View

performance_input_directory = Path("./my_ppar") / "input" / "performance"

analytics = Analytics(
    performance_input_directory / "Mega-Cap Alpha Portfolio.csv",
    performance_input_directory / "Mega-Cap Benchmark.csv",
)

overall_returns = (
    analytics.attribution()
    .to_polars(View.OVERALL_ATTRIBUTION)
    .tail(1)
    .select("Portfolio_Return", "Benchmark_Return", "Active_Return")
)
print(overall_returns)
```

The generated `ppar_demo.py` is the complete reporting example. Results are available
as Polars DataFrames, HTML text, PNG bytes, or CSV files.

## Documentation

- [Methodology](docs/methodology.md)
- [Reports and results](docs/reports.md)
- [Python API](docs/python_api.md)
- [Contributor maintenance](docs/maintenance.md)

Downloading, installing, accessing, copying, or using ppar constitutes acceptance of
the [license](LICENSE).
