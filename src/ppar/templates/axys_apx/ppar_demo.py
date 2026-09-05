"""Create portfolio analytics reports from Axys/APX export files.

The initial settings use the included demonstration data. To analyze your own data,
replace the export files and update the settings below.

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


# Input and output paths are based on this script's location. You can therefore
# use the absolute command in README.md without first changing directories.
DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = DIRECTORY / "output"

# FROM_DATE and THRU_DATE define the inclusive reporting period. Complete input
# periods are selected by their thru_date. Use dt.date.min or dt.date.max when
# you do not want a lower or upper limit.
FROM_DATE = dt.date(2021, 7, 1)
THRU_DATE = dt.date(2026, 5, 29)

# This grouping appears in the classification tables and charts and determines
# which classification data and mapping are selected in the source settings below.
CLASSIFICATION = "Economic Sector"

# Choose MONTHLY, QUARTERLY, or YEARLY to consolidate input periods into
# completed calendar periods. AS_OFTEN_AS_POSSIBLE preserves the input periods,
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
# account and input period. secperf.csv has one row per security, account, and input
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
    """Run the demonstration and write its selected reports.

    Returns:
        Process exit code. Zero means every selected report was written.

    Raises:
        PparError: If source validation or an analytics calculation fails.
        OSError: If an input or output file cannot be accessed.
    """
    print("Generating reports...", flush=True)

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

    # Native input periods do not establish a fixed annualization frequency, so
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

    print(f"Created {len(output_paths)} report files in {OUTPUT_DIRECTORY}.")
    print("Output files:")
    # List the reports in the same order in which they were produced.
    for output_path in output_paths:
        print(f"  {output_path}")
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
    source = AxysData(DIRECTORY, AXYS_SOURCE_VALUES)
    portfolios = source.get_portfolios(
        (PORTFOLIO, BENCHMARK),
        from_date=FROM_DATE,
        thru_date=THRU_DATE,
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
    # relative performance.
    security_attribution = analytics.attribution_for(
        source.get_classification_sources_for_pair(
            "Security",
            portfolio,
            benchmark,
        ),
    )

    # 3. Create classification attribution. This rolls holdings into CLASSIFICATION
    # groups.
    classification_attribution = analytics.attribution_for(
        source.get_classification_sources_for_pair(
            CLASSIFICATION,
            portfolio,
            benchmark,
        ),
    )
    return analytics, security_attribution, classification_attribution


if __name__ == "__main__":
    raise SystemExit(main())
