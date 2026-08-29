"""Create portfolio analytics reports from CSV input files.

The initial settings use the included demonstration data. To analyze your own
portfolio, replace the input files and update the settings below.

Use the command in README.md to run this script. Reports are written to ``output/``.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from ppar import Analytics
from ppar.attribution import Attribution, Chart, View
from ppar.frequency import Frequency
from ppar.publication import atomic_output_directory
import ppar.utilities as util


# Input and output paths are based on this script's location. You can therefore
# use the absolute command in README.md without first changing directories.
DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = DIRECTORY / "output"

# Each performance CSV contains one row per security and source period. It must
# have these headings:
#
#   from_date, thru_date, identifier, weight, return
#
# Dates use YYYY-MM-DD. Weights and returns are decimals: 0.25 means 25%, not
# 0.25%. Beginning weights should total approximately 1.0 within each period.
# An optional ``name`` column supplies a portfolio or benchmark display name.
PORTFOLIO_PERFORMANCE = DIRECTORY / "input/performance/Mega-Cap Alpha Portfolio.csv"
BENCHMARK_PERFORMANCE = DIRECTORY / "input/performance/Mega-Cap Benchmark.csv"

# The date bounds are inclusive. Change them to focus every table and chart on
# one reporting window. Use dt.date.min or dt.date.max to keep all available
# history at the corresponding end.
FROM_DATE = dt.date(2021, 6, 1)
THRU_DATE = dt.date(2026, 5, 29)

# This name appears in report titles and determines which classification and
# mapping files are used below.
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
    """Load generic CSV files and build security and classification attribution.

    Returns:
        Analytics calculation, security attribution, and selected-classification
        attribution.
    """
    # Analytics matches portfolio and benchmark periods, applies the requested
    # date window and frequency, and prepares the common return history used by
    # both attribution and risk statistics.
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

    # Security attribution answers which individual holdings drove relative
    # performance. The broader classification attribution rolls those holdings
    # into groups such as economic sectors. Both sides use the same mapping here;
    # pass different portfolio and benchmark mappings when their taxonomies differ.
    security_attribution = analytics.attribution(
        "Security",
        SECURITY_CLASSIFICATION,
    )
    classification_attribution = analytics.attribution(
        CLASSIFICATION,
        CLASSIFICATION_DATA,
        (CLASSIFICATION_MAPPING, CLASSIFICATION_MAPPING),
    )
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
