"""Create portfolio analytics reports from Axys/APX export files.

The initial settings use the included demonstration data. To analyze your own
portfolio, replace the export files and update the settings below.

Use the command in README.md to run this script. Reports are written to ``output/``.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl

from ppar import Analytics
from ppar.attribution import Attribution, Chart, View
from ppar.axys_apx import AxysData
from ppar.frequency import Frequency
from ppar.publication import atomic_output_directory
import ppar.schema as cols
import ppar.utilities as util


# Input and output paths are based on this script's location. You can therefore
# use the absolute command in README.md without first changing directories.
DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = DIRECTORY / "output"

# These must match account codes in portperf.csv and secperf.csv. PORTFOLIO is
# the managed account; BENCHMARK is the comparison account.
PORTFOLIO = "MEGA_ALPHA"
BENCHMARK = "MEGA_BENCH"

# The date bounds are inclusive. Change them to focus every table and chart on
# one reporting window. Use None to keep all available history at either end.
FROM_DATE: dt.date | None = dt.date(2021, 6, 1)
THRU_DATE: dt.date | None = dt.date(2026, 5, 29)

# Choose "Security" or one of the mappings defined in AXYS_SOURCE_VALUES. This
# grouping appears in the classification tables and charts.
CLASSIFICATION = "Economic Sector"

# Choose MONTHLY, QUARTERLY, or YEARLY to consolidate source periods into
# completed calendar periods. AS_OFTEN_AS_POSSIBLE preserves the source periods;
# that choice omits risk statistics because the report requires a fixed frequency.
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

# portperf.csv has one row per account and source period. secperf.csv has one row
# per security, account, and source period. Returns, beginning weights, and
# contributions are decimals: 0.05 means 5%. secmast.csv supplies security names
# and the classification columns used by the mappings below.
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

# These tuples are the report menu. Views become HTML tables; charts become PNG
# images. Remove an item to omit its report, add another enum member to produce
# it, or reorder items to change the printed file order. The script also writes
# one overall security-attribution table and, for fixed frequencies, one
# risk-statistics table.
#
# Additional View choices:
#   View.SUBPERIOD_ATTRIBUTION, View.SUBPERIOD_SUMMARY
#
# Additional Chart choices:
#   Chart.CUMULATIVE_CONTRIBUTION, Chart.HEATMAP_ACTIVE_RETURN,
#   Chart.HEATMAP_PORTFOLIO_CONTRIBUTION, Chart.HEATMAP_PORTFOLIO_RETURN,
#   Chart.SUBPERIOD_RETURN
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


def main() -> int:
    """Run the demonstration and publish its selected reports.

    Returns:
        Process exit code. Zero means the complete output bundle was published.

    Raises:
        PparError: If source validation or an analytics calculation fails.
        OSError: If an input cannot be read or output cannot be published.
    """
    analytics, security_attribution, classification_attribution = _build_analytics()

    # Build the entire bundle away from output/. Only a successful bundle replaces
    # the prior reports, so an input or calculation error cannot leave partial output.
    with atomic_output_directory(OUTPUT_DIRECTORY) as staging_directory:
        output_names = _write_reports(
            analytics,
            security_attribution,
            classification_attribution,
            staging_directory,
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
    # AxysData translates the site headings above, selects both accounts, aligns
    # their common periods, and reconciles security-level weights so their weighted
    # returns agree with the corresponding account return in portperf.csv.
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

    # Security attribution answers which individual holdings drove relative
    # performance. Combine the secmast.csv names found for both accounts so every
    # portfolio and benchmark holding has the same display-name source.
    security_classification = pl.concat(
        [
            source.get_classification_sources(
                "Security", portfolio
            ).classification_data_source,
            source.get_classification_sources(
                "Security", benchmark
            ).classification_data_source,
        ],
        how="vertical",
    ).unique(subset=[cols.IDENTIFIER], keep="any")
    security_attribution = analytics.attribution(
        "Security",
        security_classification,
    )

    # Classification attribution rolls holdings into CLASSIFICATION groups. The
    # source loader attached those group codes and names to both accounts above.
    classification_attribution = analytics.attribution()
    return analytics, security_attribution, classification_attribution


def _write_reports(
    analytics: Analytics,
    security_attribution: Attribution,
    classification_attribution: Attribution,
    output_directory: Path,
) -> tuple[str, ...]:
    """Write the selected report bundle to one staging directory.

    Args:
        analytics: Completed portfolio-versus-benchmark calculation.
        security_attribution: Attribution grouped by individual security.
        classification_attribution: Attribution grouped by ``CLASSIFICATION``.
        output_directory: Temporary directory receiving the complete bundle.

    Returns:
        Output filenames in deterministic display order.
    """
    names: list[str] = []

    # Always include one holding-level table. It is useful for tracing a sector's
    # result back to the securities that produced it.
    security_name = "security_overall_attribution.html"
    _write_text(
        output_directory / security_name,
        security_attribution.to_html(View.OVERALL_ATTRIBUTION),
    )
    names.append(security_name)

    # Enum names become predictable filenames such as
    # classification_overall_attribution.html.
    for view in CLASSIFICATION_VIEWS:
        name = f"classification_{view.name.lower()}.html"
        _write_text(output_directory / name, classification_attribution.to_html(view))
        names.append(name)

    # Charts use the same naming rule and are written as standalone PNG files.
    for chart in CLASSIFICATION_CHARTS:
        name = f"classification_{chart.name.lower()}.png"
        (output_directory / name).write_bytes(classification_attribution.to_chart(chart))
        names.append(name)

    # Native source periods do not establish a fixed annualization frequency, so
    # risk statistics are deliberately limited to monthly, quarterly, or yearly runs.
    if FREQUENCY is not Frequency.AS_OFTEN_AS_POSSIBLE:
        risk_name = "risk_statistics.html"
        _write_text(output_directory / risk_name, analytics.risk_statistics().to_html())
        names.append(risk_name)

    return tuple(names)


def _write_text(path: Path, value: str) -> None:
    """Write one UTF-8 HTML report."""
    path.write_text(value, encoding=util.ENCODING)


if __name__ == "__main__":
    raise SystemExit(main())
