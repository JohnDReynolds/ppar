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

# Third-Party Imports
import polars as pl

# Project Imports
from ppar.attribution import Attribution
from ppar._perfattr_adapter import prepare_performance_sources, prepare_performances
from ppar.frequency import Frequency, load_holidays
from ppar.performance import Performance
from ppar.risk import RiskStatistics
import ppar.schema as cols
from ppar.errors import PparError
import ppar.utilities as util


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

        # Load both host sources, then align and consolidate them in one portable call.
        self._performances = prepare_performance_sources(
            (portfolio_data_source, benchmark_data_source),
            names=(portfolio_name, benchmark_name),
            classification_names=(
                portfolio_classification_name,
                benchmark_classification_name,
            ),
            from_date=from_date,
            thru_date=thru_date,
            frequency=self._frequency,
            holidays=self._holidays,
        )
        self._subperiod_dates = [
            (cast(dt.date, from_date), cast(dt.date, thru_date))
            for from_date, thru_date in self._performances[0]
            .period_totals()
            .select(cols.DATE_COLUMNS)
            .iter_rows()
        ]

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
                classification name is supplied, or if portable preparation,
                Performance, or Attribution raises ``PparError``.
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
        elif all(
            performance.classification_name == classification_name
            for performance in self._performances
        ):
            attribution_performances = list(self._performances)
        else:
            requested_mappings = tuple(
                None
                if performance.classification_name == classification_name
                else mapping_data_sources[index]
                for index, performance in enumerate(self._performances)
            )
            if any(
                mapping is None
                and performance.classification_name != classification_name
                for performance, mapping in zip(
                    self._performances, requested_mappings, strict=True
                )
            ):
                raise PparError(util.file_path_error(""))
            attribution_performances = list(
                prepare_performances(
                    self._performances,
                    frequency=Frequency.AS_OFTEN_AS_POSSIBLE,
                    holidays=(),
                    mapping_data_sources=requested_mappings,
                    classification_name=classification_name,
                )
            )

        # Now that both attribution performances are of the same common Classification,
        # calculate the Attribution.
        return Attribution(
            (attribution_performances[0], attribution_performances[1]),
            classification_name,
            classification_data_source,
            self._frequency,
            classification_label,
        )

    def attribution_for(
        self,
        sources: AttributionSources,
        classification_label: str | None = None,
    ) -> Attribution:
        """Return an Attribution instance from a bundled source object.

        Args:
            sources: Object containing a classification name, classification data
                source, and optional mapping data sources. Axys classification
                source bundles implement this shape.
            classification_label: Optional label displayed in tables and charts. If
                supplied, this overrides the classification name from ``sources`` for
                presentation.

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
