"""Create portfolio analytics reports from Axys/APX export files.

The initial settings use the included demonstration data. To analyze your own
portfolio, replace the export files and update the settings below.

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
from ppar.axys_apx import AxysData
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

# These must match account codes in portperf.csv and secperf.csv. PORTFOLIO is
# the managed account; BENCHMARK is the comparison account.
PORTFOLIO = "MEGA_ALPHA"
BENCHMARK = "MEGA_BENCH"

# Axys/APX exports can contain multiple accounts. To produce reports for several
# portfolios, loop over their account codes and select each portfolio and benchmark
# pair with AxysData.

# The "Use your own Axys/APX exports" section in README.md describes the three input
# files, their mapped fields, and their relationship. portperf.csv has one row per
# account and source period. secperf.csv has one row per security, account, and source
# period. secmast.csv supplies security names and classification columns.
#
# Axys/APX headings vary by site. Each ``columns`` entry maps a ppar field on the
# left to the exact export heading on the right. Update both the file paths and
# headings when substituting exports from your site.
AXYS_SOURCE_VALUES: dict[str, object] = {
    "files": {
        "portfolio_performance": {
            "path": "input/portperf.csv",
            "columns": {
                "from_date": "From Date",
                "thru_date": "Thru Date",
                "portfolio_code": "Portfolio Code",
                "portfolio_name": "Portfolio Name",
                "portfolio_return": "Portfolio Return",
            },
        },
        "security_performance": {
            "path": "input/secperf.csv",
            "columns": {
                "from_date": "From Date",
                "thru_date": "Thru Date",
                "portfolio_code": "Portfolio Code",
                "security_symbol": "Security Symbol",
                "security_type": "Security Type",
                "weight": "Beginning Weight",
                "security_return": "Security Return",
                "contribution": "Contribution",
            },
        },
        "security_master": {
            "path": "input/secmast.csv",
            "columns": {
                "security_symbol": "Security Symbol",
                "security_type": "Security Type",
                "security_name": "Security Name",
            },
        },
    },
    # A mapping identifies the secmast.csv column containing each security's
    # classification code and the column containing its displayed group name.
    # Add another entry here to make another secmast classification selectable.
    "mappings": {
        "Economic Sector": {
            "classification_column": "Sector Code",
            "display_name_column": "Sector Name",
        },
        "Asset Class": {
            "classification_column": "Asset Class Code",
            "display_name_column": "Asset Class Name",
        },
        "Country": {
            "classification_column": "Country Code",
            "display_name_column": "Country Name",
        },
        "Currency": {
            "classification_column": "Currency Code",
            "display_name_column": "Currency Name",
        },
    },
}

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
    """Load Axys/APX exports and build security and classification attribution.

    Returns:
        Analytics calculation, security attribution, and selected-classification
        attribution.
    """
    # 1. Load the source data and create Analytics. AxysData translates the site
    # headings above and reconciles security-level weights so their weighted returns
    # agree with the corresponding account return in portperf.csv. Analytics then
    # matches portfolio and benchmark periods and applies the requested frequency.
    source = AxysData.from_values(DIRECTORY, AXYS_SOURCE_VALUES)
    portfolios = source.get_portfolios(
        (PORTFOLIO, BENCHMARK),
        from_date=FROM_DATE,
        thru_date=THRU_DATE,
        classification_name=CLASSIFICATION,
    )
    portfolio = portfolios[PORTFOLIO]
    benchmark = portfolios[BENCHMARK]

    analytics = portfolio.to_analytics(
        benchmark,
        frequency=FREQUENCY,
        holidays=HOLIDAYS,
        annual_minimum_acceptable_return=ANNUAL_MINIMUM_ACCEPTABLE_RETURN,
        annual_risk_free_rate=ANNUAL_RISK_FREE_RATE,
        confidence_level=CONFIDENCE_LEVEL,
        portfolio_value=PORTFOLIO_VALUE,
    )

    # 2. Create security attribution. This answers which individual holdings drove
    # relative performance. The paired source includes names for holdings found in
    # either the portfolio or benchmark.
    security_attribution = analytics.attribution_for(
        source.get_classification_sources_for_pair(
            "Security",
            portfolio,
            benchmark,
        )
    )

    # 3. Create classification attribution. This rolls holdings into CLASSIFICATION
    # groups. The source loader attached those group codes and names to both accounts.
    classification_attribution = analytics.attribution()
    return analytics, security_attribution, classification_attribution


if __name__ == "__main__":
    raise SystemExit(main())
