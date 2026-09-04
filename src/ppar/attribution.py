"""Compute and expose Brinson-Fachler attribution results.

This module defines the :class:`Attribution` class, chart/view enumerations, and
helpers used to calculate portfolio-versus-benchmark contribution, allocation,
selection, total attribution effects, and formatted output.

Attribution instances are normally created by
:meth:`ppar.Analytics.attribution`.
"""

# Overrides for pylint
# pylint: disable=too-many-lines


# Python Imports
from enum import Enum
import datetime as dt
from pathlib import Path
from typing import cast, Sequence

# Third-Party Imports
import polars as pl

# Project Imports
from ppar._perfattr_adapter import calculate_with_perfattr
from ppar.classification import Classification
from ppar.frequency import Frequency
from ppar import tables as html_table
from ppar.performance import Performance
import ppar.schema as cols
from ppar.errors import PparError
import ppar.utilities as util

# Constants
_DEFAULT_OUTPUT_PRECISION = 8

__all__ = ["Attribution", "Chart", "View"]


class Chart(Enum):
    """Attribution chart types supported by :meth:`Attribution.to_chart`.

    Each enum value is the display label used in chart titles.

    Attributes:
        CUMULATIVE_ATTRIBUTION: Cumulative attribution-effects chart.
        CUMULATIVE_CONTRIBUTION: Cumulative contribution chart.
        CUMULATIVE_RETURN: Cumulative returns chart.
        HEATMAP_ACTIVE_CONTRIBUTION: Active-contribution heatmap.
        HEATMAP_ACTIVE_RETURN: Active-return heatmap.
        HEATMAP_ATTRIBUTION: Total-attribution-effects heatmap.
        HEATMAP_PORTFOLIO_CONTRIBUTION: Portfolio-contribution heatmap.
        HEATMAP_PORTFOLIO_RETURN: Portfolio-return heatmap.
        OVERALL_ATTRIBUTION: Overall attribution chart.
        OVERALL_CONTRIBUTION: Overall contribution comparison chart.
        SUBPERIOD_ATTRIBUTION: Subperiod attribution-effects chart.
        SUBPERIOD_RETURN: Subperiod returns chart.
    """

    CUMULATIVE_ATTRIBUTION = "Cumulative Attribution Effects"
    CUMULATIVE_CONTRIBUTION = "Cumulative Contribution"
    CUMULATIVE_RETURN = "Cumulative Returns"
    HEATMAP_ACTIVE_CONTRIBUTION = "Active Contributions"
    HEATMAP_ACTIVE_RETURN = "Active Returns"
    HEATMAP_ATTRIBUTION = "Total Attribution Effects"
    HEATMAP_PORTFOLIO_CONTRIBUTION = "Portfolio Contributions"
    HEATMAP_PORTFOLIO_RETURN = "Portfolio Returns"
    OVERALL_ATTRIBUTION = "Overall Attribution"
    OVERALL_CONTRIBUTION = "Overall Contribution"
    SUBPERIOD_ATTRIBUTION = "Sub-Period Attribution Effects"
    SUBPERIOD_RETURN = "Sub-Period Returns"


class View(Enum):
    """Tabular attribution views supported by the output methods.

    Each enum value is the display label used in table titles and serialized output.

    Attributes:
        CUMULATIVE_ATTRIBUTION: Cumulative attribution view.
        OVERALL_ATTRIBUTION: Overall attribution view.
        SUBPERIOD_ATTRIBUTION: Per-period classified attribution view.
        SUBPERIOD_SUMMARY: Per-period summary view.
    """

    CUMULATIVE_ATTRIBUTION = "Cumulative Attribution"
    OVERALL_ATTRIBUTION = "Overall Attribution"
    SUBPERIOD_ATTRIBUTION = "Sub-Period Attribution"
    SUBPERIOD_SUMMARY = "Sub-Period Summary"


# Column names that should be equivalent between all Attribution instances for a given Analytics.
_EQUIVALENT_COLUMN_NAMES = (
    cols.FROM_DATE,
    cols.THRU_DATE,
    cols.QUANTITY_OF_DAYS,
    cols.TOTAL_RETURN,
)

# Various pairs of simple columns that should be equal to each other.
_SIMPLE_COLUMN_PAIRS_THAT_SHOULD_BE_EQUAL = (
    (cols.PORTFOLIO_RETURN, cols.PORTFOLIO_CONTRIB_SIMPLE),
    (cols.BENCHMARK_RETURN, cols.BENCHMARK_CONTRIB_SIMPLE),
    (cols.ACTIVE_RETURN, cols.ACTIVE_CONTRIB_SIMPLE),
    (cols.ACTIVE_RETURN, cols.TOTAL_EFFECT_SIMPLE),
)

# The column names associated with each View.
_VIEW_COLUMN_NAMES = {
    # View.CUMULATIVE_ATTRIBUTION
    View.CUMULATIVE_ATTRIBUTION: cols.DATE_COLUMNS + cols.VIEW_CUMULATIVE_ATTRIBUTION_COLUMNS,
    # View.OVERALL_ATTRIBUTION
    View.OVERALL_ATTRIBUTION: cols.CLASSIFICATION_COLUMNS + cols.VIEW_OVERALL_ATTRIBUTION_COLUMNS,
    # View.SUBPERIOD_ATTRIBUTION
    View.SUBPERIOD_ATTRIBUTION: cols.DATE_COLUMNS
    + cols.CLASSIFICATION_COLUMNS
    + cols.VIEW_SUBPERIOD_ATTRIBUTION_COLUMNS,
    # View.SUBPERIOD_SUMMARY
    View.SUBPERIOD_SUMMARY: cols.DATE_COLUMNS + cols.VIEW_SUBPERIOD_SUMMARY_COLUMNS,
}


class Attribution:
    """Store, audit, and format an attribution result returned by Analytics.

    Application code normally obtains an instance from
    :meth:`ppar.Analytics.attribution` or
    :meth:`ppar.Analytics.attribution_for`. Results are available as Polars
    DataFrames, HTML, PNG charts, and CSV. The constructor composes package-prepared
    sources and is not the normal application entry point.
    """

    def __init__(
        self,
        performances: Sequence[Performance],
        classification_name: str | None,
        classification_data_source: str | Path | pl.DataFrame | None,
        frequency: Frequency,
        classification_label: str | None = None,
    ):
        """Initialize an attribution result from package-prepared sources.

        Args:
            performances: A two-item sequence containing the portfolio ``Performance`` at
                index 0 and the benchmark ``Performance`` at index 1.
            classification_name: Optional classification name for which
                contribution and attribution effects are calculated.
            classification_data_source: Optional classification source. May be a CSV
                file path or Polars DataFrame. If
                omitted, classification display data is inferred from the performances.
            frequency: Frequency associated with the attribution periods.
            classification_label: Optional label displayed in tables and charts. If
                supplied, this overrides the classification name for presentation.
                If omitted, the classification name is used.

        Raises:
            PparError: If classification setup, performance alignment, linking, or
                attribution calculation fails validation.
        """
        classification_label = util.normalize_optional_string(
            classification_label,
            "classification_label",
        )
        classification_name = util.normalize_optional_string(
            classification_name,
            "classification_name",
        )
        performance_pair = util.two_item_tuple(performances, "Attribution performances")

        # Attribution owns independent calculated performances. Identifier
        # equalization must never alter caller- or Analytics-owned inputs.
        self._performances = tuple(performance.copy() for performance in performance_pair)

        if classification_name is not None and any(
            performance.classification_name != classification_name
            for performance in self._performances
        ):
            raise PparError(
                "Requested attribution classification does not match both "
                "performance sources. "
                f"Requested={classification_name!r}, "
                f"portfolio={self._performances[0].classification_name!r}, "
                f"benchmark={self._performances[1].classification_name!r}."
            )

        # Set internal instance variables from the constructor parameters.
        self._classification = Classification(
            classification_name,
            classification_data_source,
            self._performances,
        )
        self._requested_classification_name = classification_name
        self._frequency = frequency
        self._classification_label = (
            self._classification.name
            if classification_label is None
            else classification_label
        )

        # Establish one numerical-result boundary before presentation is applied.
        self._result = calculate_with_perfattr(self._performances)

        # Attribution is a financial calculation boundary. Run its inexpensive
        # conservation checks before any report can expose the result.
        self._audit()

    def _add_total_row(
        self,
        df: pl.DataFrame,
        label_total: bool = False,
    ) -> pl.DataFrame:
        """Return a DataFrame with a total row appended.

        Args:
            df: DataFrame to summarize.
            label_total: Whether presentation output should convert date columns
                to strings and display ``"Total"`` in the final thru-date cell.

        Returns:
            DataFrame with one additional bottom row containing totals or
            linked return values, depending on the available columns.
        """
        # Start the total_row as a sum of df.
        total_row = df.sum()

        # The classification identifier will have 'None', so make it blank.
        if cols.CLASSIFICATION_IDENTIFIER in df.columns:
            total_row[0, cols.CLASSIFICATION_IDENTIFIER] = None
            total_row[0, cols.CLASSIFICATION_NAME] = "Total"

        # Add the "Total" label to the total row.
        if cols.FROM_DATE in df.columns:
            total_row[0, cols.FROM_DATE] = None
            total_row[0, cols.THRU_DATE] = None

        # Override the returns since they should be linked, not summed.
        if cols.ACTIVE_RETURN in df.columns:
            total_row[0, cols.PORTFOLIO_RETURN] = self._result.overall_summary.item(
                0, cols.PORTFOLIO_RETURN
            )
            total_row[0, cols.BENCHMARK_RETURN] = self._result.overall_summary.item(
                0, cols.BENCHMARK_RETURN
            )
            total_row[0, cols.ACTIVE_RETURN] = (
                total_row.item(0, cols.PORTFOLIO_RETURN)
                - total_row.item(0, cols.BENCHMARK_RETURN)
            )

        # The cumulative column totals are the values in the last row.
        if cols.CUMULATIVE_TOTAL_EFFECT in df.columns:
            for cum_col_name in cols.ALL_CUMULATIVE_COLUMNS:
                total_row[0, cum_col_name] = df[-1, cum_col_name]

        # Concatenate the total row without weakening machine-readable dtypes.
        result = df.vstack(total_row)
        if label_total and cols.FROM_DATE in result.columns:
            result = result.with_columns(
                pl.col([cols.FROM_DATE, cols.THRU_DATE]).dt.strftime(
                    util.DATE_FORMAT_STRING
                )
            )
            result[-1, cols.THRU_DATE] = "Total"
        return result

    def _audit(self) -> None:
        """Audit this attribution instance for internal consistency.

        Raises:
            PparError: If the underlying performances are invalid, detailed and overall
                DataFrames have different columns, or attribution columns fail footing
                checks.
        """
        # Audit the portfolio/benchmark pair of performance objects.
        Performance.audit_performances(
            self._performances,
            self._from_date(),
            self._thru_date(),
            (
                self._requested_classification_name
                if self._requested_classification_name is not None
                else self._classification.name
            ),
        )

        # Assert that df and df_overall have the same columns.
        if set(self._result.period_summary.columns) != set(
            self._result.overall_summary.columns
        ):
            raise PparError(
                "Attribution detail and overall results contain different columns."
            )

        # Audit all columns.
        Attribution._audit_columns(
            self._result.period_summary,
            self._result.overall_summary,
        )

    @staticmethod
    def _audit_columns(
        df: pl.DataFrame, df_overall: pl.DataFrame, do_assert_simple_column_pairs: bool = True
    ) -> None:
        """Audit calculated attribution columns.

        Args:
            df: Detailed attribution DataFrame.
            df_overall: Overall attribution DataFrame containing the total row. May be
                empty for views that do not include an overall row.
            do_assert_simple_column_pairs: Whether to assert equality for simple column
                pairs such as active return and simple total effect.

        Raises:
            PparError: If expected column pairs are not equal or smoothed columns do not
                sum to their overall values.
        """
        # Assert that certain simple column pairs in df should be equal.
        if do_assert_simple_column_pairs:
            for col1, col2 in _SIMPLE_COLUMN_PAIRS_THAT_SHOULD_BE_EQUAL:
                if col1 in df.columns and col2 in df.columns:
                    if not df[col1].round(7).equals(df[col2].round(7)):
                        raise PparError(
                            "Attribution columns do not reconcile: "
                            f"{col1!r} differs from {col2!r}."
                        )

        # Audit df_overall.
        if not df_overall.is_empty():
            # Assert that certain column pairs in df_overall should be equal.
            # Assert that the vertical sum of the smoothed columns of df is equal to df_overall.
            for col_name in cols.ALL_SMOOTHED_COLUMNS:
                if not util.are_near(
                    float(df[col_name].sum()),
                    float(df_overall[col_name].item(0)),
                    util.Tolerance.MEDIUM,
                ):
                    raise PparError(
                        f"Attribution column {col_name!r} does not reconcile to its total."
                    )

    def _from_date(self) -> dt.date:
        """Return the first from date in the attribution period.

        Returns:
            Overall from date.
        """
        return cast(dt.date, self._performances[0].narrow_df[cols.FROM_DATE].item(0))

    def _construct_df_for_detail_views(self, view: View) -> pl.LazyFrame:
        """Construct the DataFrame used by detailed attribution views.

        Args:
            view: Detailed view to construct. Supported values are
                ``View.SUBPERIOD_ATTRIBUTION`` and ``View.OVERALL_ATTRIBUTION``.

        Returns:
            LazyFrame containing dates, classification identifiers, classification
            names, weights, returns, contributions, and attribution effects.

        Raises:
            PparError: If ``view`` is not a supported detailed attribution view.
        """
        match view:
            case View.SUBPERIOD_ATTRIBUTION:
                detail = self._result.period_detail
            case View.OVERALL_ATTRIBUTION:
                detail = self._result.overall_detail
            case _:
                raise PparError(f"Unsupported attribution view: {view!r}.")

        return (
            detail.lazy()
            .join(
                self._classification.df.lazy(),
                on=cols.CLASSIFICATION_IDENTIFIER,
                how="left",
            )
            .with_columns(
                pl.col(cols.CLASSIFICATION_NAME).fill_null(pl.col(cols.CLASSIFICATION_IDENTIFIER))
            )
            .sort(cols.FROM_DATE, cols.CLASSIFICATION_IDENTIFIER)
        )

    def _thru_date(self) -> dt.date:
        """Return the last thru date in the attribution period.

        Returns:
            Overall thru date.
        """
        return cast(dt.date, self._performances[0].narrow_df[cols.THRU_DATE].item(-1))

    def _fetch_dataframe(
        self,
        view: View,
        columns_to_sort: str | Sequence[str] | None = None,
        sort_descendings: bool | Sequence[bool] = False,
        label_total: bool = False,
    ) -> pl.DataFrame:
        """Fetch the DataFrame for a view.

        Args:
            view: View to fetch.
            columns_to_sort: Optional column name or sequence of column names to sort
                by. Sorting is ignored for cumulative attribution.
            sort_descendings: Boolean or sequence of booleans indicating whether the
                corresponding sort columns should be sorted descending.
            label_total: Whether to add presentation text to a total-row date.

        Returns:
            DataFrame for the requested view, optionally sorted and with a total row
            added for views that require one.

        Raises:
            PparError: If constructing a detailed view fails validation.
        """
        if not isinstance(view, View):
            raise PparError(
                repr(view),
                context={"view": repr(view)},
            )
        normalized_sort_columns: tuple[str, ...] = ()
        if columns_to_sort is not None:
            if isinstance(columns_to_sort, str):
                if not columns_to_sort.strip():
                    raise PparError(
                        "columns_to_sort must not be blank; use None to omit it.",
                        context={"option": "columns_to_sort", "value": columns_to_sort},
                    )
                normalized_sort_columns = (columns_to_sort,)
            else:
                try:
                    normalized_sort_columns = tuple(columns_to_sort)
                except TypeError as error:
                    raise PparError(
                        "columns_to_sort must be a column name or sequence of names.",
                        context={
                            "option": "columns_to_sort",
                            "value": repr(columns_to_sort),
                        },
                    ) from error
            invalid_columns = [
                column
                for column in normalized_sort_columns
                if not isinstance(column, str) or column not in _VIEW_COLUMN_NAMES[view]
            ]
            if invalid_columns:
                raise PparError(
                    f"columns_to_sort contains {invalid_columns!r} for {view.value}.",
                    context={
                        "option": "columns_to_sort",
                        "view": view.value,
                        "invalid_columns": invalid_columns,
                    },
                )
        if isinstance(sort_descendings, bool):
            normalized_sort_descendings: bool | tuple[bool, ...] = sort_descendings
        else:
            try:
                normalized_sort_descendings = tuple(sort_descendings)
            except TypeError as error:
                raise PparError(
                    "sort_descendings must be a boolean or sequence of booleans.",
                    context={
                        "option": "sort_descendings",
                        "value": repr(sort_descendings),
                    },
                ) from error
            if (
                len(normalized_sort_descendings) != len(normalized_sort_columns)
                or any(not isinstance(value, bool) for value in normalized_sort_descendings)
            ):
                raise PparError(
                    "sort_descendings must be a boolean or one boolean per sort column.",
                    context={
                        "option": "sort_descendings",
                        "sort_column_count": len(normalized_sort_columns),
                        "value_count": len(normalized_sort_descendings),
                    },
                )

        # Get the base dataframe associated with the view.
        match view:
            case View.CUMULATIVE_ATTRIBUTION | View.SUBPERIOD_SUMMARY:
                lf = self._result.period_summary.lazy()
            case _:  # View.SUBPERIOD_ATTRIBUTION | View.OVERALL_ATTRIBUTION
                lf = self._construct_df_for_detail_views(view)

        # Select only the needed columns.
        lf = lf.select(_VIEW_COLUMN_NAMES[view])

        # Sort the dataframe.  View.CUMULATIVE_ATTRIBUTION is not sortable, because it has
        # "cumulative" columns that are implicitly chronological.
        if (
            normalized_sort_columns
            and view != View.CUMULATIVE_ATTRIBUTION
        ):
            lf = lf.sort(
                by=normalized_sort_columns,
                descending=normalized_sort_descendings,
            )

        # Must collect() before adding the total_row
        df = lf.collect()

        # Add the total_row
        if view in (View.CUMULATIVE_ATTRIBUTION, View.OVERALL_ATTRIBUTION):
            df = self._add_total_row(df, label_total)

        # Return the dataframe.
        return df

    def _title_lines(self, chart_or_view: Chart | View) -> tuple[str, str]:
        """Return title and subtitle text for a chart or view.

        Args:
            chart_or_view: Chart or View whose display value is used in the subtitle.

        Returns:
            Two-item tuple containing the title and subtitle.
        """
        # Determine if chart_or_view is a Chart or a View
        is_view = isinstance(chart_or_view, View)

        # Line 1: Portfolio Name (vs Benchmark Name)
        portfolio_name = self._performances[0].name or "Portfolio"
        benchmark_name = self._performances[1].name or "Benchmark"
        line1 = (
            portfolio_name
            if (
                chart_or_view
                in (Chart.HEATMAP_PORTFOLIO_CONTRIBUTION, Chart.HEATMAP_PORTFOLIO_RETURN)
            )
            else f"{portfolio_name} vs {benchmark_name}"
        )

        # Get the classification description if it is relevant.
        classification_description = (
            f" by {self._classification_label}"
            if (
                (
                    is_view
                    or "Attribution" in chart_or_view.value
                    or "Contribution" in chart_or_view.value
                )
                and self._classification_label is not None
            )
            else ""
        )

        # Line 2: Chart/View name, classification, frequency, dates.
        line2 = (
            f"{chart_or_view.value}{classification_description}: {self._frequency.value}"
            f" from {self._from_date()} to {self._thru_date()}"
        )

        # Return the title and subtitle.
        return (line1, line2)

    def to_chart(
        self,
        chart: Chart,
    ) -> bytes:
        """Return a PNG chart for the requested attribution chart type.

        Args:
            chart: Chart type to render.

        Returns:
            In-memory PNG bytes for the requested chart.

        Raises:
            PparError: If the underlying view construction or table retrieval fails
                validation.
        """
        if not isinstance(chart, Chart):
            raise PparError(
                repr(chart),
                context={"chart": repr(chart)},
            )
        from ppar import charts as format_chart  # pylint: disable=import-outside-toplevel

        # Get the title_lines.
        title_lines = self._title_lines(chart)

        # Get the chart.
        match chart:
            case (
                Chart.CUMULATIVE_ATTRIBUTION
                | Chart.CUMULATIVE_CONTRIBUTION
                | Chart.CUMULATIVE_RETURN
            ):
                # Set the DataFrame and remove the last "Total" row.  Note that sorting is not
                # valid for these line charts.
                df = self.to_polars(View.CUMULATIVE_ATTRIBUTION)[:-1]
                # Set the labels and column names.
                match chart:
                    case Chart.CUMULATIVE_ATTRIBUTION:
                        y_axis_label = "Effect"
                        column_names = cols.CUMULATIVE_ATTRIBUTION_COLUMNS
                    case Chart.CUMULATIVE_CONTRIBUTION:
                        y_axis_label = "Contribution"
                        column_names = cols.CUMULATIVE_CONTRIBUTION_COLUMNS
                    case Chart.CUMULATIVE_RETURN:
                        y_axis_label = "Return"
                        column_names = cols.CUMULATIVE_RETURN_COLUMNS
                # Get the chart png
                png = format_chart.cumulative_lines(df, column_names, title_lines, y_axis_label)

            case (
                Chart.HEATMAP_ACTIVE_CONTRIBUTION
                | Chart.HEATMAP_ACTIVE_RETURN
                | Chart.HEATMAP_ATTRIBUTION
                | Chart.HEATMAP_PORTFOLIO_CONTRIBUTION
                | Chart.HEATMAP_PORTFOLIO_RETURN
            ):
                # Set the DataFrame.  Note that sorting is done below in format_chart.heatmap().
                df = self.to_polars(View.SUBPERIOD_ATTRIBUTION)
                # Set the labels and column names.
                match chart:
                    case Chart.HEATMAP_ACTIVE_CONTRIBUTION:
                        column_name = cols.ACTIVE_CONTRIB_SIMPLE
                    case Chart.HEATMAP_ACTIVE_RETURN:
                        column_name = cols.ACTIVE_RETURN
                    case Chart.HEATMAP_ATTRIBUTION:
                        column_name = cols.TOTAL_EFFECT_SIMPLE
                    case Chart.HEATMAP_PORTFOLIO_CONTRIBUTION:
                        column_name = cols.PORTFOLIO_CONTRIB_SIMPLE
                    case Chart.HEATMAP_PORTFOLIO_RETURN:
                        column_name = cols.PORTFOLIO_RETURN
                # Get the sorted chart png.
                png = format_chart.heatmap(df, column_name, title_lines)

            case Chart.SUBPERIOD_ATTRIBUTION | Chart.SUBPERIOD_RETURN:
                # Set the DataFrame.  Note that sorting is not valid for these bar charts.
                df = self.to_polars(View.SUBPERIOD_SUMMARY)
                # Set the labels and column names.
                match chart:
                    case Chart.SUBPERIOD_ATTRIBUTION:
                        y_axis_label = "Effect"
                        column_names = cols.ATTRIBUTION_COLUMNS_SIMPLE
                    case Chart.SUBPERIOD_RETURN:
                        y_axis_label = "Return"
                        column_names = cols.RETURN_COLUMNS
                # Get the chart png
                png = format_chart.vertical_bars(df, column_names, title_lines, y_axis_label)

            case Chart.OVERALL_ATTRIBUTION:
                # Set the DataFrame and remove the last "Total" row.
                df = self.to_polars(
                    View.OVERALL_ATTRIBUTION,
                    cols.TOTAL_EFFECT_SMOOTHED,
                    True,
                )[:-1]
                # Get the chart png
                png = format_chart.overall_attribution(df, title_lines)

            case _:  # Chart.OVERALL_CONTRIBUTION:
                # Set the DataFrame and remove the last "Total" row.
                df = self.to_polars(
                    View.OVERALL_ATTRIBUTION,
                    cols.PORTFOLIO_CONTRIB_SMOOTHED,
                    True,
                )[:-1]
                # Get the chart png
                png = format_chart.overall_contribution(
                    df,
                    title_lines,
                    self._performances[0].name or "",
                    self._performances[1].name or "",
                )

        # Return the chart png
        return png

    def to_html(
        self,
        view: View,
        columns_to_sort: str | Sequence[str] | None = None,
        sort_descendings: bool | Sequence[bool] = False,
    ) -> str:
        """Return a view as an HTML document string.

        Args:
            view: View to render.
            columns_to_sort: Optional column name or sequence of column names to sort
                by.
            sort_descendings: Boolean or sequence of booleans indicating whether the
                corresponding sort columns should be sorted descending.

        Returns:
            HTML string containing the rendered table.

        Raises:
            PparError: If view construction fails validation.
        """
        df = self._fetch_dataframe(
            view,
            columns_to_sort,
            sort_descendings,
            label_total=True,
        )
        return html_table.attribution_html(
            df,
            view.value,
            self._title_lines(view),
            self._classification_label,
        )

    def to_polars(
        self,
        view: View,
        columns_to_sort: str | Sequence[str] | None = None,
        sort_descendings: bool | Sequence[bool] = False,
    ) -> pl.DataFrame:
        """Return a view as a Polars DataFrame.

        Args:
            view: View to return.
            columns_to_sort: Optional column name or sequence of column names to sort
                by.
            sort_descendings: Boolean or sequence of booleans indicating whether the
                corresponding sort columns should be sorted descending.

        Returns:
            Polars DataFrame for the requested view.

        Raises:
            PparError: If view construction fails validation.
        """
        return self._fetch_dataframe(view, columns_to_sort, sort_descendings)

    def write_csv(
        self,
        view: View,
        file_path: str | Path,
        columns_to_sort: str | Sequence[str] | None = None,
        sort_descendings: bool | Sequence[bool] = False,
        float_precision: int = _DEFAULT_OUTPUT_PRECISION,
    ) -> None:
        """Write a view to a CSV file.

        Args:
            view: View to write.
            file_path: Path of the CSV file to write.
            columns_to_sort: Optional column name or sequence of column names to sort
                by.
            sort_descendings: Boolean or sequence of booleans indicating whether the
                corresponding sort columns should be sorted descending.
            float_precision: Number of decimal places to write for floating-point
                values.

        Raises:
            PparError: If view construction fails validation.
        """
        if not isinstance(float_precision, int) or isinstance(float_precision, bool):
            raise PparError("float_precision must be an integer from 0 through 15.")
        if not 0 <= float_precision <= 15:
            raise PparError("float_precision must be an integer from 0 through 15.")
        output = self._fetch_dataframe(
            view,
            columns_to_sort,
            sort_descendings,
            label_total=True,
        )
        float_columns = [
            name for name, data_type in output.schema.items() if data_type.is_float()
        ]
        output.with_columns(
            pl.when(pl.col(column).round(float_precision) == 0.0)
            .then(0.0)
            .otherwise(pl.col(column))
            .alias(column)
            for column in float_columns
        ).write_csv(
            Path(file_path),
            float_precision=float_precision,
        )
