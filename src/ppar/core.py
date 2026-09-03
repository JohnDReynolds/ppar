"""Coordinate analytics for portfolio and benchmark performance data.

This module provides the Analytics class, which reads portfolio and benchmark
Performance data, aligns both data sets to common subperiods, optionally
consolidates those subperiods to the requested frequency, and exposes Attribution
and RiskStatistics objects.
"""

# Python Imports
import datetime as dt
from pathlib import Path
from typing import cast, Protocol, Sequence
import warnings

# Third-Party Imports
import polars as pl

# Project Imports
from ppar.attribution import Attribution
from ppar.frequency import (
    Frequency,
    completed_frequency_bucket_ends,
    fixed_frequency_coverage_start,
    frequency_bucket,
    frequency_bucket_label,
    load_holidays,
)
from ppar.mapping import Mapping
from ppar.performance import Performance
from ppar.risk import RiskStatistics
import ppar.schema as cols
from ppar.errors import PparError
import ppar.utilities as util


_FREQUENCY_BUCKET_COLUMN = "_frequency_bucket"


def _period_tuples(source_periods: pl.DataFrame) -> list[tuple[dt.date, dt.date]]:
    """Return sorted inclusive source periods as Python date tuples."""
    return [
        (cast(dt.date, from_date), cast(dt.date, thru_date))
        for from_date, thru_date in source_periods.select(cols.DATE_COLUMNS)
        .unique()
        .sort(cols.THRU_DATE)
        .iter_rows()
    ]


def _formatted_periods(
    periods: Sequence[tuple[dt.date, dt.date]],
) -> list[tuple[str, str]]:
    """Return period tuples formatted for concise error messages."""
    return [(from_date.isoformat(), thru_date.isoformat()) for from_date, thru_date in periods]


class AttributionSources(Protocol):  # pylint: disable=too-few-public-methods
    """Describe bundled classification sources accepted by Analytics."""

    @property
    def classification_name(self) -> str | None:
        """Return the target classification name."""
        raise NotImplementedError

    @property
    def classification_data_source(self) -> str | Path | pl.DataFrame | None:
        """Return the classification data source."""
        raise NotImplementedError

    @property
    def mapping_data_sources(
        self,
    ) -> Sequence[str | Path | pl.DataFrame | None] | None:
        """Return optional mapping data sources."""
        raise NotImplementedError


class Analytics:  # pylint: disable=too-many-instance-attributes
    """Coordinate attribution and risk-statistics calculations.

    Analytics validates and aligns portfolio and benchmark Performance data, then
    consolidates that data to the requested reporting frequency. It acts as the
    public entry point for attribution and risk-statistics calculations.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        # Portfolio and Benchmark parameters
        portfolio_data_source: str | Path | pl.DataFrame,
        benchmark_data_source: str | Path | pl.DataFrame | None = None,
        *,
        portfolio_name: str | None = None,
        benchmark_name: str | None = None,
        portfolio_classification_name: str | None = None,
        benchmark_classification_name: str | None = None,
        # Date and frequency parameters
        from_date: str | dt.date = dt.date.min,
        thru_date: str | dt.date = dt.date.max,
        frequency: Frequency = Frequency.AS_OFTEN_AS_POSSIBLE,
        # RiskStatistics parameters
        annual_minimum_acceptable_return: float = util.DEFAULT_ANNUAL_MINIMUM_ACCEPTABLE_RETURN,
        annual_risk_free_rate: float = util.DEFAULT_ANNUAL_RISK_FREE_RATE,
        confidence_level: float = util.DEFAULT_CONFIDENCE_LEVEL,
        portfolio_value: tuple[float, str] = (
            util.DEFAULT_PORTFOLIO_VALUE,
            util.DEFAULT_CURRENCY_SYMBOL,
        ),
        holidays: str | Path | None = None,
    ):
        """Initialize an Analytics instance.

        Reads portfolio and benchmark performance data, converts the requested date
        bounds to ``datetime.date`` values, aligns the two performance data sets to
        common subperiods, and consolidates subperiods according to ``frequency``.
        When no benchmark data source is supplied, the portfolio data source is reused
        as the benchmark data source so portfolio-only analytics can be calculated.

        Args:
            portfolio_data_source: Portfolio performance CSV path or Polars DataFrame.
            benchmark_data_source: Benchmark performance CSV path or Polars DataFrame.
                Defaults to
                ``None``, which causes the portfolio data source to be reused.
            portfolio_name: Portfolio display name used in output titles.
            benchmark_name: Benchmark display name used in output titles.
            portfolio_classification_name: Classification name associated with the
                portfolio performance data.
            benchmark_classification_name: Classification name associated with the
                benchmark performance data.
            from_date: Earliest period ``thru_date`` to retain, either as a
                ``datetime.date`` or a string in ``yyyy-mm-dd`` format.
            thru_date: Latest period ``thru_date`` to retain, either as a
                ``datetime.date`` or a string in ``yyyy-mm-dd`` format.
            frequency: Reporting frequency used to consolidate subperiods.
            annual_minimum_acceptable_return: Annual minimum acceptable return used in
                downside-risk calculations.
            annual_risk_free_rate: Annual risk-free rate used in risk statistics that
                require a risk-free return.
            confidence_level: Confidence level used when calculating value at risk.
            portfolio_value: Tuple containing the portfolio value and its currency
                symbol for value-at-risk calculations.
            holidays: Optional path to a headerless, single-column file
                containing one ``YYYY-MM-DD`` holiday per line. Configured
                holidays extend the weekend-only effective-endpoint calendar.

        Data Parameters:
            ``portfolio_data_source`` and ``benchmark_data_source`` use the
            narrow layout below. For each time period, weights must sum to
            1.0. Column order and row order do not matter. The ``name`` column
            is optional.

            Narrow layout::

                from_date, thru_date, identifier, return, weight, name
                2024-01-01, 2024-01-31, AAPL, -0.0422272121, 0.4, Apple Inc.
                2024-01-01, 2024-01-31, MSFT,  0.0572811503, 0.6, Microsoft

        Raises:
            PparError: If either date cannot be converted, the portfolio and benchmark
                do not share any valid subperiods, there are too few performance rows
                for the calculated subperiods, or a nested Performance validation
                raises ``PparError``.
        """
        portfolio_name = util.normalize_optional_string(portfolio_name, "portfolio_name")
        benchmark_name = util.normalize_optional_string(benchmark_name, "benchmark_name")
        portfolio_classification_name = util.normalize_optional_string(
            portfolio_classification_name,
            "portfolio_classification_name",
        )
        benchmark_classification_name = util.normalize_optional_string(
            benchmark_classification_name,
            "benchmark_classification_name",
        )

        # Default the benchmark to the portfolio.  This will allow for "portfolio-only" analysis
        # if they do not have a benchmark.
        if benchmark_data_source is None:
            benchmark_data_source = portfolio_data_source
            benchmark_name = portfolio_name
            benchmark_classification_name = portfolio_classification_name

        # Convert the dates to dt.date types.
        from_date = util.convert_to_date(from_date)
        thru_date = util.convert_to_date(thru_date)

        # Set the simple class variables directly from the constructor parameters.
        self._annual_minimum_acceptable_return = annual_minimum_acceptable_return
        self._annual_risk_free_rate = annual_risk_free_rate
        self._confidence_level = confidence_level
        self._frequency = frequency
        self._holidays = load_holidays(holidays)
        self._portfolio_value = portfolio_value

        # Initialize the cached risk calculation.
        self._riskstatistics: RiskStatistics | None = None

        # Get a tuple of the two Performance objects. 0 = portfolio, 1 = benchmark.
        self._performances = (
            # Portfolio
            Performance(
                portfolio_data_source,
                name=portfolio_name,
                classification_name=portfolio_classification_name,
                from_date=from_date,
                thru_date=thru_date,
            ),
            # Benchmark
            Performance(
                benchmark_data_source,
                name=benchmark_name,
                classification_name=benchmark_classification_name,
                from_date=from_date,
                thru_date=thru_date,
            ),
        )

        # Get the from dates and thru dates for all subperiods that are common between the
        # two Performance objects.
        (
            self._subperiod_dates,
            self._subperiod_buckets,
            source_periods,
        ) = self._calculate_subperiod_dates(
            f"from {util.date_str(from_date)} to {util.date_str(thru_date)}"
        )

        # Reuse the period lists materialized during alignment. Applying the same
        # comparison-window predicate as the row filter below keeps the cached
        # sequences synchronized without another full-frame unique-and-sort query.
        source_period_dates = tuple(
            [
                period
                for period in periods
                if self._from_date() <= period[1] <= self._thru_date()
            ]
            for periods in source_periods
        )

        # Now that the dates have been firmly established, remove extraneous dates from
        # the Performance objects.
        for perf in self._performances:
            # Filtering preserves already-validated row order and arithmetic.
            perf._replace_calculated_rows(  # pylint: disable=protected-access
                perf.narrow_df.lazy()
                .filter(
                    (self._from_date() <= pl.col(cols.THRU_DATE))
                    & (pl.col(cols.THRU_DATE) <= self._thru_date())
                )
                .collect(),
                sort_rows=False,
            )

        # Consolidate multiple subperiods (e.g. daily) into single periods (e.g. monthly) based on
        # self._frequency.
        self._consolidate_all_subperiods(source_period_dates)

    def audit(self) -> None:
        """Audit the Analytics instance.

        Audits the aligned portfolio and benchmark Performance objects. Each
        Attribution audits itself when it is constructed.

        Raises:
            PparError: If the underlying Performance audit fails.
        """
        # Audit the portfolio/benchmark pair of performances.  These are the performances that
        # were originally read in the constructor. Depending on their classifications, they may
        # be different than the performances in the attributions.
        Performance.audit_performances(
            self._performances, self._from_date(), self._thru_date()
        )

    def _from_date(self) -> dt.date:
        """Return the overall from date.

        Returns:
            The first from date in the aligned subperiod date range.
        """
        return self._subperiod_dates[0][0]

    def _calculate_subperiod_dates(
        self,
        message_suffix: str,
    ) -> tuple[
        list[tuple[dt.date, dt.date]],
        list[int],
        tuple[list[tuple[dt.date, dt.date]], list[tuple[dt.date, dt.date]]],
    ]:
        """Calculate common subperiod dates for portfolio and benchmark data.

        Native-frequency periods must match as complete inclusive intervals
        inside the common comparison window. Fixed frequencies may use
        different source partitions, but each aligned bucket must cover the
        same complete, gapless inclusive date range on both sides.

        Args:
            message_suffix: Suffix to include in the ``PparError`` message when no
                valid subperiods are found.

        Returns:
            Aligned ``(from_date, thru_date)`` tuples and their fixed-frequency
            bucket identifiers, followed by the ordered source-period lists for
            the portfolio and benchmark. The bucket list is empty for
            native-frequency data.

        Raises:
            PparError: If no common subperiods can be calculated or source
                intervals cannot be aligned without changing their coverage.
        """
        # Cache one row per reporting period from each performance stream.
        df0 = self._performances[0].period_totals()
        df1 = self._performances[1].period_totals()
        source_periods = [_period_tuples(source) for source in (df0, df1)]

        if self._frequency != Frequency.AS_OFTEN_AS_POSSIBLE:
            bucket_results = [
                completed_frequency_bucket_ends(
                    periods,
                    self._frequency,
                    self._holidays,
                )
                for periods in source_periods
            ]
            complete_buckets = [result[0] for result in bucket_results]
            for source_index, result in enumerate(bucket_results):
                incomplete_terminal_bucket = result[2]
                comparison_index = 1 - source_index
                if (
                    incomplete_terminal_bucket is not None
                    and incomplete_terminal_bucket
                    in complete_buckets[comparison_index]
                ):
                    raise PparError(
                        "portfolio and benchmark terminal-bucket completeness "
                        "differs for "
                        f"{frequency_bucket_label(incomplete_terminal_bucket, self._frequency)}.",
                    )
            common_buckets = sorted(
                set(complete_buckets[0]).intersection(complete_buckets[1])
            )
            truncations = [
                result[1] for result in bucket_results if result[1] is not None
            ]
            if truncations:
                truncation = min(truncations, key=lambda item: item.bucket)
                actual_end = (
                    truncation.actual_end.isoformat()
                    if truncation.actual_end is not None
                    else "missing"
                )
                warnings.warn(
                    f"{self._frequency.value} output was truncated before "
                    f"{frequency_bucket_label(truncation.bucket, self._frequency)}: "
                    f"source endpoint {actual_end} did not match expected endpoint "
                    f"{truncation.expected_end.isoformat()}.",
                    RuntimeWarning,
                    stacklevel=2,
                )
            subperiod_dates = []
            subperiod_buckets = []
            previous_endpoint: dt.date | None = None
            for bucket in common_buckets:
                thru_date = complete_buckets[0][bucket]
                if complete_buckets[1][bucket] != thru_date:
                    raise PparError(
                        "portfolio and benchmark effective endpoints differ for "
                        f"{frequency_bucket_label(bucket, self._frequency)}.",
                    )
                coverage_starts = [
                    fixed_frequency_coverage_start(
                        periods,
                        bucket,
                        thru_date,
                        previous_endpoint,
                        self._frequency,
                        self._holidays,
                        source_label,
                    )
                    for periods, source_label in (
                        (source_periods[0], "portfolio"),
                        (source_periods[1], "benchmark"),
                    )
                ]
                if coverage_starts[0] != coverage_starts[1]:
                    raise PparError(
                        "portfolio and benchmark actual source coverage starts "
                        f"differ for {frequency_bucket_label(bucket, self._frequency)}: "
                        f"{coverage_starts[0].isoformat()} versus "
                        f"{coverage_starts[1].isoformat()}.",
                    )
                subperiod_dates.append((coverage_starts[0], thru_date))
                subperiod_buckets.append(bucket)
                previous_endpoint = thru_date
        else:
            common_period_set = set(source_periods[0]).intersection(source_periods[1])
            common_periods = sorted(
                common_period_set,
                key=lambda period: period[1],
            )
            subperiod_buckets = []
            if common_periods:
                comparison_start = common_periods[0][0]
                comparison_end = common_periods[-1][1]
                unmatched_periods = [
                    [
                        period
                        for period in periods
                        if period not in common_period_set
                        and period[1] >= comparison_start
                        and period[0] <= comparison_end
                    ]
                    for periods in source_periods
                ]
                if unmatched_periods[0] or unmatched_periods[1]:
                    raise PparError(
                        "Unmatched native-frequency periods exist inside the common "
                        "comparison window. Portfolio-only periods: "
                        f"{_formatted_periods(unmatched_periods[0])}. "
                        "Benchmark-only periods: "
                        f"{_formatted_periods(unmatched_periods[1])}.",
                    )
            subperiod_dates = common_periods

        # Assert that there is at least one subperiod.
        if len(subperiod_dates) == 0:
            raise PparError(f"No common performance periods were found {message_suffix}.")

        # Return the common from and thru dates that define the subperiods.
        return subperiod_dates, subperiod_buckets, (source_periods[0], source_periods[1])

    def _consolidate_all_subperiods(
        self,
        source_period_dates: Sequence[Sequence[tuple[dt.date, dt.date]]],
    ) -> None:
        """Consolidate portfolio and benchmark data to the aligned subperiods.

        For each Performance object, verifies that enough rows exist for the
        aligned subperiods. Fixed-frequency data is consolidated unless its
        complete ordered period boundaries already match the reporting periods
        exactly.

        Args:
            source_period_dates: Ordered source-period boundaries for the portfolio
                and benchmark, already restricted to the common comparison window.

        Raises:
            PparError: If a Performance has fewer rows than the calculated subperiod
                date list.
        """
        # Iterate through the portfolio and benchmark Performance objects.
        for performance, source_periods in zip(
            self._performances,
            source_period_dates,
            strict=True,
        ):
            quantity_of_periods = len(source_periods)
            if quantity_of_periods < len(self._subperiod_dates):
                raise PparError(
                    f"{performance.error_message_context} from "
                    f"{util.date_str(self._from_date())} "
                    f"to {util.date_str(self._thru_date())}",
                )

            if (
                (
                    self._frequency != Frequency.AS_OFTEN_AS_POSSIBLE
                    and not self._source_periods_match_reporting_periods(source_periods)
                )
                or len(self._subperiod_dates) < quantity_of_periods
            ):
                performance._replace_calculated_rows(  # pylint: disable=protected-access
                    self._consolidate_subperiods(performance),
                    sort_rows=False,
                )

    def _source_periods_match_reporting_periods(
        self,
        source_periods: Sequence[tuple[dt.date, dt.date]],
    ) -> bool:
        """Return whether source periods already equal every reporting period.

        Args:
            source_periods: Ordered, unique inclusive period boundaries from one
                performance stream.

        Returns:
            ``True`` only when period count, order, start dates, and end dates
            exactly match the aligned reporting-period sequence.
        """
        return source_periods == self._subperiod_dates

    def _consolidate_subperiods(self, performance: Performance) -> pl.DataFrame:
        """Consolidate a Performance object into the aligned subperiods.

        Combines multiple source rows, such as daily rows, into the subperiods stored
        in ``self._subperiod_dates``. Returns are geometrically linked, weights are
        summed using day-weighting coefficients, and contributions are summed after
        applying logarithmic linking coefficients.

        Args:
            performance: Performance instance to consolidate.

        Returns:
            DataFrame containing one narrow calculated row per identifier in
            each aligned subperiod.
        """
        subperiod_data: dict[str, list[dt.date] | list[int]] = {
            "_subperiod_from_date": [bd for bd, _ in self._subperiod_dates],
            "_subperiod_thru_date": [ed for _, ed in self._subperiod_dates],
        }
        if self._subperiod_buckets:
            subperiod_data[_FREQUENCY_BUCKET_COLUMN] = self._subperiod_buckets

        # Create a DataFrame, one row per subperiod.
        subperiods = (
            pl.DataFrame(subperiod_data)
            .with_row_index(name="subperiod_id")
            .with_columns(
                (
                    (
                        pl.col("_subperiod_thru_date")
                        - pl.col("_subperiod_from_date")
                    ).dt.total_days()
                    + 1
                ).alias("_subperiod_quantity_of_days")
            )
            .sort("_subperiod_from_date")
        )

        source_periods = performance.narrow_df.select(
            *cols.DATE_COLUMNS,
            cols.QUANTITY_OF_DAYS,
            cols.TOTAL_RETURN,
        ).unique().sort(cols.THRU_DATE)
        if self._subperiod_buckets:
            source_periods = source_periods.with_columns(
                pl.Series(
                    _FREQUENCY_BUCKET_COLUMN,
                    [
                        frequency_bucket(thru_date, self._frequency)
                        for thru_date in source_periods[cols.THRU_DATE]
                    ],
                    dtype=pl.Int64,
                )
            )
            selected_source_periods = source_periods.filter(
                pl.col(_FREQUENCY_BUCKET_COLUMN).is_in(self._subperiod_buckets)
            )
            assigned_periods = selected_source_periods.join(
                subperiods,
                on=_FREQUENCY_BUCKET_COLUMN,
                how="inner",
            )
            if assigned_periods.height != selected_source_periods.height:
                raise PparError(
                    f"{performance.error_message_context}: source periods did not "
                    "map one-to-one into aligned reporting buckets.",
                )
            out_of_bounds = assigned_periods.filter(
                (pl.col(cols.FROM_DATE) < pl.col("_subperiod_from_date"))
                | (pl.col(cols.THRU_DATE) > pl.col("_subperiod_thru_date"))
            )
            if not out_of_bounds.is_empty():
                raise PparError(
                    f"{performance.error_message_context}: source periods extend "
                    "outside their aligned reporting bucket: "
                    f"{_formatted_periods(_period_tuples(out_of_bounds))}.",
                )
        else:
            native_subperiods = subperiods.with_columns(
                pl.col("_subperiod_from_date").alias("_source_from_date"),
                pl.col("_subperiod_thru_date").alias("_source_thru_date"),
            )
            assigned_periods = source_periods.join(
                native_subperiods,
                left_on=list(cols.DATE_COLUMNS),
                right_on=["_source_from_date", "_source_thru_date"],
                how="inner",
            )
            if assigned_periods.height != source_periods.height:
                raise PparError(
                    f"{performance.error_message_context}: native-frequency source "
                    "periods did not map exactly to aligned reporting periods.",
                )

        # A reporting-period total return must compound the lower-frequency rows.
        # A +10% day followed by a -10% day is -1%, not 0%.
        subperiod_returns = assigned_periods.group_by("subperiod_id").agg(
            pl.col(cols.TOTAL_RETURN).add(1).product().sub(1).alias("subperiod_return")
        )
        subperiod_weight_denominators = assigned_periods.group_by("subperiod_id").agg(
            pl.col(cols.QUANTITY_OF_DAYS).sum().alias("_weight_denominator_days")
        )

        assigned_rows = (
            performance.narrow_df.join(
                assigned_periods.select(
                    *cols.DATE_COLUMNS,
                    "subperiod_id",
                    "_subperiod_from_date",
                    "_subperiod_thru_date",
                    "_subperiod_quantity_of_days",
                ),
                on=cols.DATE_COLUMNS,
            )
            .join(subperiod_returns, on="subperiod_id")
            .join(subperiod_weight_denominators, on="subperiod_id")
            .with_columns(
                # Weights are interpreted as period exposures, so consolidation averages
                # them by elapsed days instead of taking the first or last holding weight.
                (
                    pl.col(cols.QUANTITY_OF_DAYS)
                    / pl.col("_weight_denominator_days")
                ).alias("weight_coefficient"),
                # Contributions are linked so their sum over source rows equals the
                # geometrically linked reporting-period return. This preserves the
                # additive attribution story while returns themselves compound.
                pl.struct(["subperiod_return", cols.TOTAL_RETURN])
                .map_batches(
                    lambda x: util.logarithmic_linking_coefficient_series(
                        x.struct.field("subperiod_return"),
                        x.struct.field(cols.TOTAL_RETURN),
                    ),
                    return_dtype=pl.Float64,
                )
                .alias("linking_coefficient"),
            )
        )

        consolidated_subperiods = (
            assigned_rows.group_by(["subperiod_id", cols.IDENTIFIER])
            .agg(
                pl.col("_subperiod_from_date").first().alias(cols.FROM_DATE),
                pl.col("_subperiod_thru_date").first().alias(cols.THRU_DATE),
                pl.col("_subperiod_quantity_of_days")
                .first()
                .alias(cols.QUANTITY_OF_DAYS),
                pl.col("subperiod_return").first().alias(cols.TOTAL_RETURN),
                pl.col(cols.RETURN).add(1).product().sub(1).alias(cols.RETURN),
                (pl.col(cols.WEIGHT) * pl.col("weight_coefficient")).sum().alias(cols.WEIGHT),
                (pl.col(cols.CONTRIBUTION) * pl.col("linking_coefficient"))
                .sum()
                .alias(cols.CONTRIBUTION),
            )
            .select(
                *cols.DATE_COLUMNS,
                cols.QUANTITY_OF_DAYS,
                cols.TOTAL_RETURN,
                cols.IDENTIFIER,
                cols.RETURN,
                cols.WEIGHT,
                cols.CONTRIBUTION,
            )
            .sort([cols.THRU_DATE, cols.IDENTIFIER])
        )

        performance.subperiods_have_been_consolidated = True

        return consolidated_subperiods

    def _thru_date(self) -> dt.date:
        """Return the overall thru date.

        Returns:
            The last thru date in the aligned subperiod date range.
        """
        return self._subperiod_dates[-1][-1]

    def attribution(
        self,
        classification_name: str | None = None,
        classification_data_source: str | Path | pl.DataFrame | None = None,
        mapping_data_sources: Sequence[str | Path | pl.DataFrame | None] | None = None,
        classification_label: str | None = None,
        engine: str = "polars",
    ) -> Attribution:
        """Return an Attribution instance for the requested classification.

        Maps portfolio and/or benchmark Performance objects to the requested
        classification when needed, then constructs and returns a fresh Attribution.

        Args:
            classification_name: Classification name for the requested Attribution.
                If omitted and both Performance objects share a common non-empty
                classification name, that common name is used.
            classification_data_source: Optional classification data source. This can
                be a CSV file path or Polars DataFrame.
            mapping_data_sources: Optional two-item sequence of mapping data sources
                where item 0 maps the portfolio and item 1 maps the benchmark. Each
                source can be a CSV file path or Polars DataFrame; use ``None`` when
                a performance already uses the target
                classification.
            classification_label: Optional label displayed in tables and charts. If
                supplied, this overrides the classification name for presentation.
            engine: Calculation engine. ``"polars"`` is the existing default;
                ``"pandas"`` selects the portable ``perfattr`` calculator.

        Data Parameters:
            Example ``classification_data_source`` for a Security classification::

                AAPL, Apple Inc.
                MSFT, Microsoft

            Example ``mapping_data_sources`` data for Security to Economic Sector::

                AAPL, IT
                GOOG, CS

        Returns:
            Attribution instance associated with ``classification_name``.

        Raises:
            PparError: If ``classification_name`` is required because at least one
                Performance has a known classification name but no target
                classification name is supplied, or if a nested Mapping, Performance,
                or Attribution operation raises ``PparError``.
        """
        classification_name = util.normalize_optional_string(
            classification_name,
            "classification_name",
        )
        classification_label = util.normalize_optional_string(
            classification_label,
            "classification_label",
        )
        if (
            isinstance(classification_data_source, str)
            and not classification_data_source.strip()
        ):
            raise PparError(
                "classification_data_source path must not be blank; use None to omit it.",
                context={
                    "parameter": "classification_data_source",
                    "value": classification_data_source,
                },
            )
        if mapping_data_sources is None:
            mapping_data_sources = (None, None)
        else:
            mapping_data_sources = util.two_item_tuple(
                mapping_data_sources, "Analytics mapping_data_sources"
            )
            for source_index, source in enumerate(mapping_data_sources):
                if isinstance(source, str) and not source.strip():
                    raise PparError(
                        "mapping_data_sources paths must not be blank; use None "
                        "to omit a mapping.",
                        context={
                            "parameter": "mapping_data_sources",
                            "source_index": source_index,
                            "value": source,
                        },
                    )

        # If the classification name is omitted and the portfolio and benchmark share a
        # non-empty classification name, use that common classification.
        if (
            classification_name is None
            and self._performances[0].classification_name is not None
            and self._performances[0].classification_name
            == self._performances[1].classification_name
        ):
            classification_name = self._performances[0].classification_name

        # If the target classification is unknown but either source Performance has a
        # known classification, require an explicit target. This still allows all
        # classifications to be unknown for identifier-level attribution.
        if classification_name is None and (
            (self._performances[0].classification_name is not None)
            or (self._performances[1].classification_name is not None)
        ):
            raise PparError(
                "classification_name is required when source classifications differ."
            )

        # Get the performances for the common classification_name.
        if classification_name is None:
            attribution_performances = list(self._performances)
        else:
            attribution_performances = [
                (
                    perf
                    if perf.classification_name == classification_name
                    else self._map_performance(
                        perf, classification_name, mapping_data_sources[idx]
                    )
                )
                for idx, perf in enumerate(self._performances)
            ]

        # Now that both attribution performances are of the same common Classification,
        # calculate the Attribution.
        return Attribution(
            (attribution_performances[0], attribution_performances[1]),
            classification_name,
            classification_data_source,
            self._frequency,
            classification_label,
            engine,
        )

    def attribution_for(
        self,
        sources: AttributionSources,
        classification_label: str | None = None,
        engine: str = "polars",
    ) -> Attribution:
        """Return an Attribution instance from a bundled source object.

        Args:
            sources: Object containing a classification name, classification data
                source, and optional mapping data sources. Axys classification
                source bundles implement this shape.
            classification_label: Optional label displayed in tables and charts. If
                supplied, this overrides the classification name from ``sources`` for
                presentation.
            engine: Calculation engine passed to :meth:`attribution`.

        Returns:
            Attribution instance associated with ``sources.classification_name``.

        Raises:
            PparError: If the bundled source values cannot produce the requested
                Attribution.
        """
        return self.attribution(
            classification_name=sources.classification_name,
            classification_data_source=sources.classification_data_source,
            mapping_data_sources=sources.mapping_data_sources,
            classification_label=classification_label,
            engine=engine,
        )

    def risk_statistics(self) -> RiskStatistics:
        """Return risk statistics for the aligned Performance objects.

        Creates and caches a RiskStatistics instance on first use, then returns the
        cached instance on subsequent calls.

        Returns:
            RiskStatistics instance for the portfolio and benchmark Performance data.
        """
        # Calculate the risk statistics if they are not already cached.
        if self._riskstatistics is None:
            self._riskstatistics = RiskStatistics(
                self._performances,
                self._frequency,
                self._annual_minimum_acceptable_return,
                self._annual_risk_free_rate,
                self._confidence_level,
                self._portfolio_value,
            )

        # Return the DataFrame of the risk statistics.
        return self._riskstatistics

    def _map_performance(
        self,
        performance: Performance,
        to_classification_name: str,
        mapping_data_source: util.MappingDataSource | None,
    ) -> Performance:
        """Map a Performance object to a different classification.

        Uses the supplied mapping data to roll up contribution and weight columns from
        ``performance.classification_name`` to ``to_classification_name``. Mapped
        returns are calculated as mapped contributions divided by mapped weights. A
        zero-weight, nonzero-contribution group has an undefined null return; a group
        with both zero weight and zero contribution has a zero return.

        Args:
            performance: Existing Performance object to map.
            to_classification_name: Target classification name.
            mapping_data_source: Mapping data source used to map source identifiers to
                target classification items. Must be provided when mapping is needed.

        Data Parameters:
            Example mapping data for Security to Economic Sector::

                AAPL, IT
                GOOG, CO

        Returns:
            New Performance object using ``to_classification_name``.

        Raises:
            PparError: If the Mapping or resulting Performance cannot be created or
                validated, or if mapping is required but no mapping source is supplied.
        """
        if mapping_data_source is None:
            raise PparError(util.file_path_error(""))

        to_froms = Mapping(
            performance.identifiers,
            mapping_data_source,
        ).to_froms
        to_identifier_by_from = {
            from_identifier: to_identifier
            for to_identifier, from_identifiers in to_froms.items()
            for from_identifier in from_identifiers
        }
        mapped = (
            performance.narrow_df.with_columns(
                pl.col(cols.IDENTIFIER)
                .replace_strict(to_identifier_by_from)
                .alias(cols.IDENTIFIER)
            )
            .group_by([*cols.DATE_COLUMNS, cols.IDENTIFIER])
            .agg(
                pl.col(cols.WEIGHT).sum(),
                pl.col(cols.CONTRIBUTION).sum(),
                pl.col(cols.QUANTITY_OF_DAYS).first(),
                pl.col(cols.TOTAL_RETURN).first(),
            )
            .with_columns(
                pl.when(pl.col(cols.WEIGHT) != 0.0)
                .then(pl.col(cols.CONTRIBUTION) / pl.col(cols.WEIGHT))
                .when(pl.col(cols.CONTRIBUTION) == 0.0)
                .then(0.0)
                .otherwise(None)
                .alias(cols.RETURN)
            )
            .select(
                *cols.DATE_COLUMNS,
                cols.QUANTITY_OF_DAYS,
                cols.TOTAL_RETURN,
                cols.IDENTIFIER,
                cols.WEIGHT,
                cols.RETURN,
                cols.CONTRIBUTION,
            )
        )

        mapped_performance = Performance(
            mapped.select(
                *cols.DATE_COLUMNS,
                cols.IDENTIFIER,
                cols.WEIGHT,
                cols.RETURN,
            ).with_columns(pl.col(cols.RETURN).fill_null(0.0)),
            name=performance.name,
            classification_name=to_classification_name,
        )
        # A mapped group can have zero net weight but a nonzero contribution
        # when long and short constituents offset. Preserve the aggregated
        # contribution because no finite group return can reconstruct it.
        mapped_performance._replace_calculated_rows(  # pylint: disable=protected-access
            mapped
        )
        mapped_performance.subperiods_have_been_consolidated = True
        return mapped_performance
