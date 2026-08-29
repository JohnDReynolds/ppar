# Configuration

Each workspace has one `ppar.yaml`. ppar reads only that file from the requested
workspace; it does not search parent directories or infer a source.

## Shared settings

| Key | Type | Required | Default or allowed values |
| --- | --- | --- | --- |
| `source` | string | yes | `axys_apx` or `generic` |
| `portfolio` | string | Axys/APX | none |
| `benchmark` | string | Axys/APX | none |
| `frequency` | string | no | `monthly`, `quarterly`, `yearly`; otherwise source periods |
| `holidays` | path | no | none |
| `from_date` | ISO date | no | earliest available date |
| `thru_date` | ISO date | no | latest available date |
| `classification` | string | no | `Security` |
| `annual_minimum_acceptable_return` | number | no | `0.0` |
| `annual_risk_free_rate` | number | no | `0.03` |
| `confidence_level` | number | no | `0.95`, strictly between zero and one |
| `portfolio_value` | number | no | `100000`, greater than zero |
| `currency_symbol` | string | no | `$` |

Output is always `WORKSPACE/output`; there is no output setting or runtime override.

## Axys/APX

```yaml
source: axys_apx
portfolio: MEGA_ALPHA
benchmark: MEGA_BENCH
frequency: quarterly
holidays: input/holidays.csv
classification: Economic Sector

files:
  portfolio_performance:
    path: input/portperf.csv
    columns:
      from_date: From Date
      thru_date: Thru Date
      portfolio_code: Portfolio Code
      portfolio_return: Portfolio Return
  security_performance:
    path: input/secperf.csv
    columns:
      from_date: From Date
      thru_date: Thru Date
      portfolio_code: Portfolio Code
      security_symbol: Security Symbol
      weight: Beginning Weight
      security_return: Security Return
      contribution: Contribution
```

All vendor headings are mapped explicitly. The setup-created configuration includes
complete portfolio-performance, security-performance, security-master, and
classification mappings.

## Generic

```yaml
source: generic
frequency: quarterly
holidays: input/holidays.csv
classification: Economic Sector

files:
  portfolio_performance:
    path: input/performance/Portfolio.csv
  benchmark_performance:
    path: input/performance/Benchmark.csv
  security_classification:
    path: input/classifications/Security.csv
  classification:
    path: input/classifications/Economic Sector.csv
  mapping:
    path: input/mappings/Security--to--Economic Sector.csv
```

Performance CSVs have a header and the columns `from_date`, `thru_date`, `identifier`,
`weight`, and `return`. An optional `name` column supplies display names.
Classification and mapping files are headerless two-column CSVs.
