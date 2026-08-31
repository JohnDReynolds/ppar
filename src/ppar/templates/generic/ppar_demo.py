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
from ppar.publication import atomic_output_directory, write_report_bundle


# Input and output paths are based on this script's location. You can therefore
# use the absolute command in README.md without first changing directories.
DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = DIRECTORY / "output"

# The date bounds are inclusive. Change them to focus every table and chart on
# one reporting window. Use dt.date.min for no lower date bound and dt.date.max
# for no upper date bound.
FROM_DATE = dt.date(2021, 6, 1)
THRU_DATE = dt.date(2026, 5, 29)

# This grouping appears in the classification tables and charts and determines
# which classification data and mapping are selected in the source settings below.
CLASSIFICATION = "Economic Sector"

# Choose MONTHLY, QUARTERLY, or YEARLY to consolidate source periods into
# completed calendar periods. AS_OFTEN_AS_POSSIBLE preserves the source periods,
# but omits the risk statistics report because that report requires a fixed frequency.
FREQUENCY = Frequency.QUARTERLY

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
    """Run the demonstration and publish its selected reports.

    Returns:
        Process exit code. Zero means the complete output bundle was published.

    Raises:
        PparError: If source validation or an analytics calculation fails.
        OSError: If an input cannot be read or output cannot be published.
    """
    analytics, security_attribution, classification_attribution = _build_analytics()

    # atomic_output_directory() lets the script build the complete report bundle in
    # a staging directory and replace the entire OUTPUT_DIRECTORY only after every
    # report succeeds. Using atomic_output_directory() is optional.
    with atomic_output_directory(OUTPUT_DIRECTORY) as staging_directory:
        # Native source periods do not establish a fixed annualization frequency, so
        # risk statistics are limited to monthly, quarterly, or yearly runs.
        risk_statistics = (
            analytics.risk_statistics()
            if INCLUDE_RISK_STATISTICS
            and FREQUENCY is not Frequency.AS_OFTEN_AS_POSSIBLE
            else None
        )
        output_names = write_report_bundle(
            output_directory=staging_directory,
            security_attribution=security_attribution,
            security_views=SECURITY_VIEWS,
            classification_attribution=classification_attribution,
            classification_views=CLASSIFICATION_VIEWS,
            classification_charts=CLASSIFICATION_CHARTS,
            risk_statistics=risk_statistics,
        )

    print("Output files:")
    for name in output_names:
        print(f"  {OUTPUT_DIRECTORY / name}")
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
    )

    # 3. Create classification attribution. This rolls holdings into groups such
    # as economic sectors. Both sides use the same mapping here; pass different
    # portfolio and benchmark mappings when their taxonomies differ.
    classification_attribution = analytics.attribution(
        CLASSIFICATION,
        CLASSIFICATION_DATA,
        (CLASSIFICATION_MAPPING, CLASSIFICATION_MAPPING),
    )
    return analytics, security_attribution, classification_attribution


if __name__ == "__main__":
    raise SystemExit(main())
