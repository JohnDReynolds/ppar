"""Create portfolio analytics reports from CSV input files.

The initial settings use the included demonstration data. To analyze your own
portfolio, replace the input files and update the settings below.

Use the command in README.md to run this script. Reports are written to ``output/``.

Additional capabilities:
    This script can be adapted to process multiple portfolio codes, benchmarks,
    classifications, date ranges, and frequencies.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from ppar import Analytics
from ppar.attribution import Attribution, Chart, View
from ppar.frequency import Frequency


# Input and output paths are based on this script's location. You can therefore
# use the absolute command in README.md without first changing directories.
DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = DIRECTORY / "output"

# FROM_DATE and THRU_DATE define the inclusive reporting period. Complete source
# periods are selected by their thru_date. Use dt.date.min or dt.date.max when
# you do not want a lower or upper limit.
FROM_DATE = dt.date(2021, 7, 1)
THRU_DATE = dt.date(2026, 5, 29)

# This grouping appears in the classification tables and charts and determines
# which classification data and mapping are selected in the source settings below.
CLASSIFICATION = "Economic Sector"

# Choose MONTHLY, QUARTERLY, or YEARLY to consolidate source periods into
# completed calendar periods. AS_OFTEN_AS_POSSIBLE preserves the source periods,
# but omits the risk statistics report because that report requires a fixed frequency.
FREQUENCY = Frequency.QUARTERLY

# Attribution uses ppar's original Polars calculator by default. Set this to
# "pandas" to run the same prepared data and reports through perfattr.
ATTRIBUTION_ENGINE = "polars"

# holidays.csv is headerless and contains one YYYY-MM-DD date per line. Holidays
# let ppar recognize the actual business-day endpoint of a month, quarter, or year.
HOLIDAYS = DIRECTORY / "input" / "holidays.csv"

# Rates are annual decimals: 0.03 means 3%. The minimum acceptable return is used
# by downside-risk measures; the risk-free rate is used by measures such as the
# Sharpe ratio. CONFIDENCE_LEVEL must be between 0 and 1. PORTFOLIO_VALUE and its
# currency symbol scale monetary risk measures such as value at risk.
ANNUAL_MINIMUM_ACCEPTABLE_RETURN = 0.0
ANNUAL_RISK_FREE_RATE = 0.03
CONFIDENCE_LEVEL = 0.95
PORTFOLIO_VALUE = (100_000.0, "$")

# Each performance CSV contains one row per security and source period. It must
# have these headings:
#
#   from_date, thru_date, identifier, weight, return
#
# Dates use YYYY-MM-DD. Weights and returns are decimals: 0.25 means 25%, not
# 0.25%. For each period, weights must sum to 1.0. ppar calculates each
# security's contribution as weight * return and derives the total portfolio
# return by summing those contributions.
#
# An optional ``name`` column can supply a display name for each identifier. This
# demo instead gets security names from Security.csv below. If neither source
# supplies a display name, reports use the identifier itself.
#
# Portfolio and benchmark titles use the corresponding CSV filename without its
# extension unless ``portfolio_name`` and ``benchmark_name`` are passed to Analytics.
PORTFOLIO_PERFORMANCE = DIRECTORY / "input/performance/Mega-Cap Alpha Portfolio.csv"
BENCHMARK_PERFORMANCE = DIRECTORY / "input/performance/Mega-Cap Benchmark.csv"

# Master CSVs can contain multiple portfolios identified by a ``portfolio_code``
# column. To produce reports for several portfolios, load the files with Polars,
# loop over their portfolio codes, and pass each filtered portfolio and benchmark
# pair to Analytics.

# Classification and mapping CSVs are headerless and have exactly two columns:
#
#   Security.csv: security identifier, security display name
#   <classification>.csv: classification identifier, display name
#   mapping CSV: security identifier, classification identifier
#
# Every identifier in the performance files must be named in Security.csv and
# mapped when classification reports are requested.
#
# Surrounding whitespace is removed from identifiers and names; meaningful
# internal spaces are retained. Repeated identical pairs are collapsed, while
# conflicting names or mapping targets stop the run.
SECURITY_CLASSIFICATION = DIRECTORY / "input/classifications/Security.csv"
CLASSIFICATION_DATA = DIRECTORY / f"input/classifications/{CLASSIFICATION}.csv"
CLASSIFICATION_MAPPING = (
    DIRECTORY / f"input/mappings/Security--to--{CLASSIFICATION}.csv"
)

# These settings specify every report the script produces. Views become HTML
# tables; charts become PNG images. Remove an item to omit its report, add another
# item to produce it, or reorder items to change the printed file order. The Risk
# Statistics report can be selected independently but requires a fixed frequency.
#
# Additional View choices:
#   View.SUBPERIOD_ATTRIBUTION, View.SUBPERIOD_SUMMARY
#
# Additional Chart choices:
#   Chart.CUMULATIVE_CONTRIBUTION, Chart.HEATMAP_ACTIVE_RETURN,
#   Chart.HEATMAP_PORTFOLIO_CONTRIBUTION, Chart.HEATMAP_PORTFOLIO_RETURN,
#   Chart.SUBPERIOD_RETURN
SECURITY_VIEWS = (View.OVERALL_ATTRIBUTION,)
CLASSIFICATION_VIEWS = (
    View.CUMULATIVE_ATTRIBUTION,
    View.OVERALL_ATTRIBUTION,
)
CLASSIFICATION_CHARTS = (
    Chart.OVERALL_CONTRIBUTION,
    Chart.OVERALL_ATTRIBUTION,
    Chart.SUBPERIOD_ATTRIBUTION,
    Chart.HEATMAP_ACTIVE_CONTRIBUTION,
    Chart.HEATMAP_ATTRIBUTION,
    Chart.CUMULATIVE_ATTRIBUTION,
    Chart.CUMULATIVE_RETURN,
)
INCLUDE_RISK_STATISTICS = True


def main() -> int:
    """Run the demonstration and write its selected reports.

    Returns:
        Process exit code. Zero means every selected report was written.

    Raises:
        PparError: If source validation or an analytics calculation fails.
        OSError: If an input or output file cannot be accessed.
    """
    # Load and calculate the shared analytics once before rendering any reports.
    analytics, security_attribution, classification_attribution = _build_analytics()

    # Create the output directory if this is the first run. Each report replaces
    # only a same-named file; unrelated files in the directory remain untouched.
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    output_paths: list[Path] = []

    # Write the selected holding-level attribution tables.
    for view in SECURITY_VIEWS:
        output_path = OUTPUT_DIRECTORY / f"security_{view.name.lower()}.html"
        output_path.write_text(
            security_attribution.to_html(view),
            encoding="utf-8",
        )
        output_paths.append(output_path)

    # Write the selected classification-level attribution tables.
    for view in CLASSIFICATION_VIEWS:
        output_path = OUTPUT_DIRECTORY / f"classification_{view.name.lower()}.html"
        output_path.write_text(
            classification_attribution.to_html(view),
            encoding="utf-8",
        )
        output_paths.append(output_path)

    # Render the selected classification charts.
    for chart in CLASSIFICATION_CHARTS:
        output_path = OUTPUT_DIRECTORY / f"classification_{chart.name.lower()}.png"
        output_path.write_bytes(classification_attribution.to_chart(chart))
        output_paths.append(output_path)

    # Native source periods do not establish a fixed annualization frequency, so
    # risk statistics are limited to monthly, quarterly, or yearly runs.
    if (
        INCLUDE_RISK_STATISTICS
        and FREQUENCY is not Frequency.AS_OFTEN_AS_POSSIBLE
    ):
        output_path = OUTPUT_DIRECTORY / "risk_statistics.html"
        output_path.write_text(
            analytics.risk_statistics().to_html(),
            encoding="utf-8",
        )
        output_paths.append(output_path)

    print("Output files:")
    # List the reports in the same order in which they were produced.
    for output_path in output_paths:
        print(f"  {output_path}")
    return 0


def _build_analytics() -> tuple[Analytics, Attribution, Attribution]:
    """Load vendor-neutral CSV files and build security and classification attribution.

    Returns:
        Analytics calculation, security attribution, and selected-classification
        attribution.
    """
    # 1. Load the source data and create Analytics. Analytics matches portfolio
    # and benchmark periods, applies the requested date window and frequency, and
    # prepares the common return history used by attribution and risk statistics.
    analytics = Analytics(
        PORTFOLIO_PERFORMANCE,
        BENCHMARK_PERFORMANCE,
        portfolio_classification_name="Security",
        benchmark_classification_name="Security",
        from_date=FROM_DATE,
        thru_date=THRU_DATE,
        frequency=FREQUENCY,
        holidays=HOLIDAYS,
        annual_minimum_acceptable_return=ANNUAL_MINIMUM_ACCEPTABLE_RETURN,
        annual_risk_free_rate=ANNUAL_RISK_FREE_RATE,
        confidence_level=CONFIDENCE_LEVEL,
        portfolio_value=PORTFOLIO_VALUE,
    )

    # 2. Create security attribution. This answers which individual holdings drove
    # relative performance.
    security_attribution = analytics.attribution(
        "Security",
        SECURITY_CLASSIFICATION,
        engine=ATTRIBUTION_ENGINE,
    )

    # 3. Create classification attribution. This rolls holdings into groups such
    # as economic sectors. Both sides use the same mapping here; pass different
    # portfolio and benchmark mappings when their taxonomies differ.
    classification_attribution = analytics.attribution(
        CLASSIFICATION,
        CLASSIFICATION_DATA,
        (CLASSIFICATION_MAPPING, CLASSIFICATION_MAPPING),
        engine=ATTRIBUTION_ENGINE,
    )
    return analytics, security_attribution, classification_attribution


if __name__ == "__main__":
    raise SystemExit(main())
