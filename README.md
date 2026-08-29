# ppar

Portfolio performance attribution, contribution, and ex-post risk analytics.

ppar compares a portfolio with a benchmark, explains active return by classification,
and produces reviewable HTML tables and PNG charts. It runs locally and supports both
Axys/APX exports and a small vendor-neutral CSV format.

## Start here

ppar requires Python 3.11.9 or newer.

```bash
python -m pip install ppar

# Axys/APX demonstration workspace (the default)
ppar setup ./my_ppar
ppar run ./my_ppar

# Vendor-neutral demonstration workspace
ppar setup ./my_generic_ppar --generic
ppar run ./my_generic_ppar
```

Both setup commands create a complete runnable workspace:

```text
my_ppar/
  README.md
  ppar.yaml
  input/
  output/
```

Edit `ppar.yaml` and replace the demonstration files under `input/` with your data.
Every run writes the complete result atomically to `output/`; a failed run leaves the
previous successful output intact.

## What it produces

The standard quarterly workspace writes security and classification attribution
tables, attribution and contribution charts, cumulative return charts, heatmaps, and
an ex-post risk-statistics table.

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

<img src="https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/RiskStatistics.jpg" alt="Ex-post risk statistics table" width="100%" />

## Python

```python
from ppar import Analytics
from ppar.attribution import View

analytics = Analytics("portfolio.csv", "benchmark.csv")
overall = analytics.attribution().to_polars(View.OVERALL_ATTRIBUTION)
print(overall)
```

Public tabular results are Polars DataFrames. HTML, PNG, and CSV output is available
from the owning attribution or risk object.

## Documentation

- [Configuration](docs/configuration.md)
- [Methodology](docs/methodology.md)
- [Python API](docs/python_api.md)
- [Maintenance](docs/maintenance.md)

[License](LICENSE)

Downloading, installing, accessing, copying, or using ppar constitutes acceptance of
the license. The public package grants a time-limited internal evaluation license;
production and other commercial use require a separate written agreement.
