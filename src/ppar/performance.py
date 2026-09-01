"""Represent and validate narrow periodic performance data.

This module contains the ``Performance`` class, which loads portfolio,
benchmark, or classification-level performance rows, validates dates and
values, and derives contributions, total returns, overall returns, and
linking coefficients.
"""

# Python Imports
import copy as copy_module
import datetime as dt
from pathlib import Path
from typing import cast, Sequence

# Third-Party Imports
import polars as pl

# Project Imports
import ppar.schema as cols
from ppar.errors import PparError
import ppar.utilities as util


_CALCULATED_COLUMNS = (
    *cols.DATE_COLUMNS,
    cols.QUANTITY_OF_DAYS,
    cols.TOTAL_RETURN,
    cols.IDENTIFIER,
    cols.RETURN,
    cols.WEIGHT,
    cols.CONTRIBUTION,
)


class Performance:
    """Hold narrow identifier-level returns and weights for one performance stream.

    Attributes:
        classification_name: Optional name of the classification represented
            by the performance data.
        classification_items: Optional classification identifier/name pairs
            extracted from source-data rows when a ``name`` column is present.
        error_message_context: Context string included in validation errors.
        identifiers: Sorted identifiers present in the performance rows.
        name: Optional descriptive name for the performance stream.
        narrow_df: Calculated long-form Polars DataFrame containing dates,
            identifier, return, weight, contribution, quantity of days, and
            total return.
        subperiods_have_been_consolidated: Indicates whether lower-frequency
            periods have been consolidated into larger reporting periods.
    """

    def __init__(
        self,
        data_source: util.PerformanceDataSource,
        name: str | None = None,
        classification_name: str | None = None,
        from_date: str | dt.date = dt.date.min,
        thru_date: str | dt.date = dt.date.max,
    ):
        """Initialize a ``Performance`` instance from narrow performance rows.

        Args:
            data_source: Performance data source supplied as a CSV path or
                Polars DataFrame.
            name: Descriptive name for the performance stream. If omitted for
                a CSV input, the file basename is used.
            classification_name: Name of the represented classification, such
                as ``"Security"`` or ``"Economic Sector"``.
            from_date: Earliest period ``thru_date`` to retain.
            thru_date: Latest period ``thru_date`` to retain.

        Data Parameters:
            Input must use one row per period and identifier with these columns::

                from_date, thru_date, identifier, return, weight, name
                2024-01-01, 2024-01-31, AAPL, -0.0422272121, 0.4, Apple Inc.
                2024-01-01, 2024-01-31, MSFT,  0.0572811503, 0.6, Microsoft

            The ``name`` column is optional. For each period, weights must sum
            to ``1.0``.

        Raises:
            PparError: If input rows cannot be loaded or converted, required
                columns are absent, values are missing, rows or periods are
                duplicated, dates are invalid or overlapping, or period
                weights do not sum to ``1.0``.
        """
        name = util.normalize_optional_string(name, "name")
        self.classification_name = util.normalize_optional_string(
            classification_name,
            "classification_name",
        )
        from_date = util.convert_to_date(from_date)
        thru_date = util.convert_to_date(thru_date)
        self.subperiods_have_been_consolidated = False
        self.error_message_context = (
            f"in the file {data_source}"
            if isinstance(data_source, str | Path)
            else f"in the dataframe {name}"
        )
        if from_date > thru_date:
            raise PparError(
                f"{self.error_message_context}: "
                f"From date {from_date} is after thru date {thru_date}.",
            )

        self.name, self.narrow_df = self._load_data(name, data_source)
        if self.narrow_df.is_empty():
            raise PparError(f"No performance rows remain {self.error_message_context}.")
        self._clean_and_validate_columns()
        self._cast_and_validate_columns()
        self._filter_date_range(from_date, thru_date)
        if self.narrow_df.is_empty():
            raise PparError(f"No performance rows remain {self.error_message_context}.")
        self._clean_and_validate_dates()
        self._set_classification_items()
        self._calculate_rows()
        self.identifiers = sorted(self.narrow_df[cols.IDENTIFIER].unique().to_list())
        self._df_overall = pl.DataFrame()

    def copy(self) -> "Performance":
        """Return an independent copy of this calculated performance stream.

        Returns:
            Performance object with independent Polars DataFrames and cached
            state. Mutating or realigning the returned object cannot affect the
            source object.
        """
        # ``copy.copy`` preserves all validated scalar metadata. Pylint cannot
        # infer the concrete type of that copy when the independent frames are
        # replaced below.
        # pylint: disable=attribute-defined-outside-init,protected-access
        duplicate = copy_module.copy(self)
        duplicate.classification_items = self.classification_items.clone()
        duplicate.narrow_df = self.narrow_df.clone()
        duplicate.identifiers = list(self.identifiers)
        duplicate._df_overall = self._df_overall.clone()
        # pylint: enable=attribute-defined-outside-init,protected-access
        return duplicate

    def audit(self) -> None:
        """Validate internal consistency of this performance stream.

        Raises:
            PparError: If weights do not sum to ``1.0``, raw contributions do
                not equal weight multiplied by return, or contributions do not
                sum to the period total return.
        """
        period_totals = self.period_totals()
        summed_weights = self.narrow_df.group_by(cols.DATE_COLUMNS).agg(
            pl.col(cols.WEIGHT).sum().alias(cols.WEIGHT)
        )
        if not (summed_weights[cols.WEIGHT].round(8) == 1.0).all():
            raise PparError(
                f"{self.error_message_context}: Perf.audit() weights do not sum to 1.0.")

        if not self.subperiods_have_been_consolidated:
            contributions = self.narrow_df.with_columns(
                (pl.col(cols.WEIGHT) * pl.col(cols.RETURN)).alias("_expected_contribution")
            )
            if not (
                contributions[cols.CONTRIBUTION].round(11)
                == contributions["_expected_contribution"].round(11)
            ).all():
                raise PparError(
                    f"{self.error_message_context}: Perf.audit() weight * return != contrib.")

        summed_contributions = (
            self.narrow_df.group_by(cols.DATE_COLUMNS)
            .agg(pl.col(cols.CONTRIBUTION).sum().alias(cols.CONTRIBUTION))
            .join(period_totals, on=cols.DATE_COLUMNS)
        )
        if not (
            summed_contributions[cols.CONTRIBUTION].round(11)
            == summed_contributions[cols.TOTAL_RETURN].round(11)
        ).all():
            raise PparError(
                f"{self.error_message_context}: Perf.audit() sum of contribs != total return.",
            )

    @staticmethod
    def audit_performances(
        performances: Sequence["Performance"],
        expected_from_date: dt.date,
        expected_thru_date: dt.date,
        common_classification_name: str | None = None,
    ) -> None:
        """Validate a portfolio/benchmark performance pair.

        Args:
            performances: Portfolio and benchmark performance streams.
            expected_from_date: Expected first from date.
            expected_thru_date: Expected final thru date.
            common_classification_name: Optional classification name expected
                on both streams.

        Raises:
            PparError: If either stream fails its audit, dates or day counts
                differ, the date range differs from the expected range, or a
                required classification does not match.
        """
        common_classification_name = util.normalize_optional_string(
            common_classification_name,
            "common_classification_name",
        )
        portfolio, benchmark = util.two_item_tuple(
            performances, "Performance.audit_performances performances"
        )
        portfolio.audit()
        benchmark.audit()
        dates_days = [*cols.DATE_COLUMNS, cols.QUANTITY_OF_DAYS]
        portfolio_periods = portfolio.period_totals().select(dates_days)
        benchmark_periods = benchmark.period_totals().select(dates_days)
        if not portfolio_periods.equals(benchmark_periods):
            raise PparError("audit_perfs(): Portfolio and Benchmark dates are not equal.")
        if not (
            portfolio_periods[cols.FROM_DATE][0] == expected_from_date
            and portfolio_periods[cols.THRU_DATE][-1] == expected_thru_date
        ):
            raise PparError("audit_perfs(): Date logic error.")
        if common_classification_name is not None:
            if (
                portfolio.classification_name != common_classification_name
                or benchmark.classification_name != common_classification_name
            ):
                raise PparError(
                    "audit_perfs(): Requested classification does not match "
                    "both performance sources. "
                    f"Requested={common_classification_name!r}, "
                    f"portfolio={portfolio.classification_name!r}, "
                    f"benchmark={benchmark.classification_name!r}."
                )

    def _calculate_df_overall(self) -> pl.DataFrame:
        """Calculate overall narrow rows for the full performance period.

        Returns:
            One overall-period row per identifier, including linked returns,
            observed-day-weighted weights, linked contributions, and common
            total return.
        """
        overall_from_date = cast(dt.date, self.narrow_df[cols.FROM_DATE].min())
        overall_thru_date = cast(dt.date, self.narrow_df[cols.THRU_DATE].max())
        period_totals = self.period_totals()
        observed_days = cast(int, period_totals[cols.QUANTITY_OF_DAYS].sum())
        overall_total_return = cast(
            float, (period_totals[cols.TOTAL_RETURN] + 1).product() - 1
        )
        period_linking = period_totals.select(*cols.DATE_COLUMNS).with_columns(
            self.linking_coefficients().alias("_linking_coefficient")
        )
        overall = (
            self.narrow_df.join(period_linking, on=cols.DATE_COLUMNS)
            .group_by(cols.IDENTIFIER)
            .agg(
                pl.when(pl.col(cols.RETURN).is_null().any())
                .then(None)
                .otherwise(pl.col(cols.RETURN).add(1).product().sub(1))
                .alias(cols.RETURN),
                (
                    pl.col(cols.WEIGHT)
                    * pl.col(cols.QUANTITY_OF_DAYS)
                    / observed_days
                )
                .sum()
                .alias(cols.WEIGHT),
                (
                    pl.col(cols.CONTRIBUTION)
                    * pl.col("_linking_coefficient")
                )
                .sum()
                .alias(cols.CONTRIBUTION),
            )
            .with_columns(
                pl.lit(overall_from_date).alias(cols.FROM_DATE),
                pl.lit(overall_thru_date).alias(cols.THRU_DATE),
                pl.lit(observed_days).alias(cols.QUANTITY_OF_DAYS),
                pl.lit(overall_total_return).alias(cols.TOTAL_RETURN),
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
            .sort(cols.IDENTIFIER)
        )
        if round(cast(float, overall[cols.WEIGHT].sum()), 8) != 1.0:
            raise PparError(
                f"{self.error_message_context}: overall weights do not sum to 1.0."
            )
        if round(cast(float, overall[cols.CONTRIBUTION].sum()), 11) != round(
            overall_total_return, 11
        ):
            raise PparError(
                f"{self.error_message_context}: overall contributions do not "
                "sum to the linked total return."
            )
        return overall

    def _calculate_rows(self) -> None:
        """Add calculated contribution, elapsed-day, and total-return columns."""
        self.narrow_df = (
            self.narrow_df.with_columns(
                (
                    (pl.col(cols.THRU_DATE) - pl.col(cols.FROM_DATE)).dt.total_days()
                    + 1
                ).alias(cols.QUANTITY_OF_DAYS),
                (pl.col(cols.WEIGHT) * pl.col(cols.RETURN)).alias(cols.CONTRIBUTION),
            )
            .join(
                self.narrow_df.with_columns(
                    (pl.col(cols.WEIGHT) * pl.col(cols.RETURN)).alias(cols.CONTRIBUTION)
                )
                .group_by(cols.DATE_COLUMNS)
                .agg(pl.col(cols.CONTRIBUTION).sum().alias(cols.TOTAL_RETURN)),
                on=cols.DATE_COLUMNS,
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
        weights = self.narrow_df.group_by(cols.DATE_COLUMNS).agg(pl.col(cols.WEIGHT).sum())
        if not (weights[cols.WEIGHT].round(8) == 1.0).all():
            raise PparError(f"Period weights must sum to 1.0 {self.error_message_context}.")

    def _cast_and_validate_columns(self) -> None:
        """Cast required narrow columns and reject missing numeric values.

        Raises:
            PparError: If a required value cannot be converted or is missing.
        """
        dtypes: dict[
            type[pl.Date] | type[pl.Float64] | type[pl.String],
            Sequence[str],
        ] = {
            pl.Date: cols.DATE_COLUMNS,
            pl.Float64: [cols.RETURN, cols.WEIGHT],
            pl.String: [cols.IDENTIFIER]
            + ([cols.NAME] if cols.NAME in self.narrow_df.columns else []),
        }
        for dtype, column_names in dtypes.items():
            for column_name in [
                name for name in column_names if self.narrow_df.schema[name] != dtype
            ]:
                try:
                    self.narrow_df = self.narrow_df.with_columns(pl.col(column_name).cast(dtype))
                except pl.exceptions.InvalidOperationError as exception:
                    raise PparError(
                        f"{self.error_message_context}: Cannot convert the column "
                        f"'{column_name}' to a {dtype}, {str(exception)[:1000]}",
                    ) from exception
        invalid_identifiers = util.invalid_identity_rows(
            self.narrow_df,
            cols.IDENTIFIER,
        )
        if not invalid_identifiers.is_empty():
            affected_rows = invalid_identifiers.select(
                *cols.DATE_COLUMNS,
                cols.IDENTIFIER,
            ).head(10).to_dicts()
            raise PparError(
                f"Identity field {cols.IDENTIFIER!r} {self.error_message_context} "
                "must be non-null, nonblank, and free of surrounding whitespace. "
                f"Affected rows: {affected_rows}",
                context={
                    "boundary": "Performance",
                    "field": cols.IDENTIFIER,
                    "invalid_rows": affected_rows,
                },
            )
        float_columns = dtypes[pl.Float64]
        if self.narrow_df.select(
            pl.any_horizontal(pl.all().is_null().any())
            | pl.any_horizontal(pl.col(float_columns).is_nan().any())
            | pl.any_horizontal(pl.col(float_columns).is_infinite().any())
        ).item():
            raise PparError(
                f"Required performance values must be non-null and finite "
                f"{self.error_message_context}."
            )

    def _clean_and_validate_columns(self) -> None:
        """Retain supported narrow input columns and validate required fields.

        Raises:
            PparError: If any required narrow column is absent.
        """
        required_columns = [*cols.DATE_COLUMNS, cols.IDENTIFIER, cols.RETURN, cols.WEIGHT]
        if not all(column in self.narrow_df.columns for column in required_columns):
            missing = sorted(set(required_columns) - set(self.narrow_df.columns))
            raise PparError(
                f"Missing required performance columns {missing} "
                f"{self.error_message_context}."
            )
        optional_columns = [cols.NAME] if cols.NAME in self.narrow_df.columns else []
        self.narrow_df = self.narrow_df.select(*required_columns, *optional_columns)

    def _clean_and_validate_dates(self) -> None:
        """Sort and validate inclusive narrow period dates.

        Raises:
            PparError: If rows are duplicated, period thru dates conflict,
                from dates are invalid, or periods overlap.
        """
        duplicate_rows = (
            self.narrow_df.group_by([*cols.DATE_COLUMNS, cols.IDENTIFIER])
            .len()
            .filter(pl.col("len") > 1)
        )
        if duplicate_rows.height > 0:
            sample_rows = (
                duplicate_rows.sort([*cols.DATE_COLUMNS, cols.IDENTIFIER]).head(10).to_dicts()
            )
            raise PparError(
                f"Duplicate performance rows {self.error_message_context}: {sample_rows}"
            )

        periods = self.narrow_df.select(cols.DATE_COLUMNS).unique().sort(cols.THRU_DATE)
        if periods[cols.THRU_DATE].n_unique() != periods.height:
            raise PparError(f"Performance thru dates are duplicated {self.error_message_context}.")
        if (periods[cols.FROM_DATE] > periods[cols.THRU_DATE]).any():
            raise PparError(f"A from date exceeds its thru date {self.error_message_context}.")
        if periods.height > 1 and (
            periods[cols.FROM_DATE][1:] <= periods[cols.THRU_DATE][:-1]
        ).any():
            raise PparError(f"Performance periods overlap {self.error_message_context}.")
        self.narrow_df = self.narrow_df.sort([cols.THRU_DATE, cols.IDENTIFIER])

    def _filter_date_range(
        self,
        from_date: dt.date,
        thru_date: dt.date,
    ) -> None:
        """Apply requested bounds after source dates have been normalized.

        Args:
            from_date: Earliest period thru date to retain.
            thru_date: Latest period thru date to retain.
        """
        if from_date != dt.date.min:
            self.narrow_df = self.narrow_df.filter(
                from_date <= pl.col(cols.THRU_DATE)
            )
        if thru_date != dt.date.max:
            self.narrow_df = self.narrow_df.filter(
                pl.col(cols.THRU_DATE) <= thru_date
            )

    def _set_classification_items(self) -> None:
        """Capture identifier/name pairs supplied with narrow source-data rows."""
        if cols.NAME not in self.narrow_df.columns:
            self.classification_items = pl.DataFrame()
            return
        self.classification_items = (
            self.narrow_df.unique(
                subset=[cols.IDENTIFIER],
                keep="last",
                maintain_order=True,
            )
            .select(
                pl.col(cols.IDENTIFIER).alias(cols.CLASSIFICATION_IDENTIFIER),
                pl.col(cols.NAME).alias(cols.CLASSIFICATION_NAME),
            )
            .sort(cols.CLASSIFICATION_IDENTIFIER)
        )
        self.narrow_df = self.narrow_df.drop(cols.NAME)

    def period_totals(self) -> pl.DataFrame:
        """Return one summarized total-return row per reporting period.

        Returns:
            DataFrame containing dates, elapsed days, and total return.
        """
        return self.narrow_df.select(
            *cols.DATE_COLUMNS, cols.QUANTITY_OF_DAYS, cols.TOTAL_RETURN
        ).unique().sort(cols.THRU_DATE)

    def df_overall(self) -> pl.DataFrame:
        """Return cached overall-period narrow identifier rows."""
        if self._df_overall.is_empty():
            self._df_overall = self._calculate_df_overall()
        return self._df_overall.clone()

    def linking_coefficients(self) -> pl.Series:
        """Return logarithmic linking coefficients for each reporting period."""
        return util.logarithmic_linking_coefficients(
            self.overall_return(), self.period_totals()[cols.TOTAL_RETURN]
        )

    @staticmethod
    def _load_data(
        name: str | None,
        data_source: util.PerformanceDataSource,
    ) -> tuple[str | None, pl.DataFrame]:
        """Load performance rows without interpreting their values.

        Args:
            name: Optional descriptive performance name.
            data_source: CSV path or Polars DataFrame.

        Returns:
            Resolved optional name and loaded DataFrame.

        Raises:
            PparError: If a supplied file path does not exist.
        """
        if isinstance(data_source, str | Path):
            if isinstance(data_source, str) and not data_source.strip():
                raise PparError(util.file_path_error(data_source))
            path = Path(data_source)
            if not util.file_path_exists(path):
                raise PparError(util.file_path_error(path))
            if name is None:
                name = util.file_basename_without_extension(path)
            lazy_frame = pl.scan_csv(
                source=path,
                try_parse_dates=True,
                schema_overrides={cols.IDENTIFIER: pl.String},
            )
        elif isinstance(data_source, pl.DataFrame):
            lazy_frame = data_source.lazy()
        else:
            raise PparError(
                "Performance data source must be a CSV path or Polars DataFrame."
            )
        return name, lazy_frame.collect()

    def overall_return(self) -> float:
        """Return linked total return for the full reporting period."""
        return cast(float, (self.period_totals()[cols.TOTAL_RETURN] + 1).product() - 1)

    def _replace_calculated_rows(
        self,
        df: pl.DataFrame,
        *,
        sort_rows: bool = True,
    ) -> None:
        """Take ownership of rows produced by a trusted internal calculation.

        Source loading and production Attribution/Risk audits enforce financial
        invariants. Trusted filters, consolidation, mapping, and zero-row alignment
        use this helper to avoid repeating expensive group-by validation on the same
        rows.
        """
        if len(df.columns) != len(_CALCULATED_COLUMNS) or set(df.columns) != set(
            _CALCULATED_COLUMNS
        ):
            raise PparError(
                f"{self.error_message_context}: calculated performance schema is invalid.",
            )
        replacement = df.select(_CALCULATED_COLUMNS).clone()
        if sort_rows:
            replacement = replacement.sort([cols.THRU_DATE, cols.IDENTIFIER])
        self._df_overall = pl.DataFrame()
        self.narrow_df = replacement
        self.identifiers = sorted(self.narrow_df[cols.IDENTIFIER].unique().to_list())
