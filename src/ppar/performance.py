"""Provide ppar's internal container for perfattr-prepared performance."""

from __future__ import annotations

import copy as copy_module
import datetime as dt
from pathlib import Path
from typing import Sequence

import polars as pl

from ppar._perfattr_adapter import (
    _PPAR_PERFORMANCE_COLUMNS,
)
from ppar.errors import PparError
import ppar.schema as cols
import ppar.utilities as util


class Performance:
    """Hold one translated performance stream prepared by ``perfattr``.

    This class preserves ppar's internal Polars-facing object boundary. The adapter
    delegates source loading, validation, date filtering, contribution derivation, and
    preparation to ``perfattr`` before constructing this container. It owns only
    translated rows, display metadata, and output checks.

    Attributes:
        classification_name: Optional classification represented by the rows.
        classification_items: Optional identifier/name display metadata.
        error_message_context: Context retained for ppar diagnostics.
        identifiers: Sorted identifiers present in the prepared rows.
        name: Optional descriptive name for the stream.
        narrow_df: Prepared rows in ppar's established Polars schema.
    """

    classification_name: str | None
    classification_items: pl.DataFrame
    error_message_context: str
    identifiers: list[str]
    name: str | None
    narrow_df: pl.DataFrame

    def __init__(self) -> None:
        """Prevent construction outside the trusted prepared-data factory."""
        raise TypeError("Performance is an internal prepared-data container.")

    def copy(self) -> "Performance":
        """Return an independent copy of this translated performance stream."""
        duplicate = copy_module.copy(self)
        duplicate.classification_items = self.classification_items.clone()
        duplicate.narrow_df = self.narrow_df.clone()
        duplicate.identifiers = list(self.identifiers)
        return duplicate

    @classmethod
    def _from_prepared_rows(
        cls,
        frame: pl.DataFrame,
        *,
        data_source: str | Path | pl.DataFrame,
        name: str | None,
        classification_name: str | None,
        classification_items: pl.DataFrame,
    ) -> "Performance":
        """Construct a host container from an already prepared portable side.

        Args:
            frame: Prepared rows translated to ppar's established schema.
            data_source: Original source retained for host error context.
            name: Optional stream display name.
            classification_name: Optional classification represented by the rows.
            classification_items: Optional identifier/name presentation metadata.

        Returns:
            Host container that owns independent copies of its rows and metadata.

        Notes:
            The caller must supply rows produced by the trusted portable boundary.
        """
        result = object.__new__(cls)
        result.classification_name = classification_name
        result.error_message_context = (
            f"in the file {data_source}"
            if isinstance(data_source, str | Path)
            else f"in the dataframe {name}"
        )
        if name is None and isinstance(data_source, str | Path):
            name = util.file_basename_without_extension(data_source)
        result.name = name
        result.classification_items = classification_items.clone()
        result.narrow_df = frame.clone()
        result.identifiers = sorted(frame[cols.IDENTIFIER].unique().to_list())
        return result

    def audit(self) -> None:
        """Validate the translated ppar representation of portable prepared rows.

        Raises:
            PparError: If host-schema weights or contributions no longer reconcile.
        """
        period_totals = self.period_totals()
        summed_weights = self.narrow_df.group_by(cols.DATE_COLUMNS).agg(
            pl.col(cols.WEIGHT).sum().alias(cols.WEIGHT)
        )
        if not (summed_weights[cols.WEIGHT].round(8) == 1.0).all():
            raise PparError(
                f"{self.error_message_context}: Perf.audit() weights do not sum to 1.0."
            )
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
                f"{self.error_message_context}: Perf.audit() sum of contribs != "
                "total return."
            )

    @staticmethod
    def audit_performances(
        performances: Sequence["Performance"],
        expected_from_date: dt.date,
        expected_thru_date: dt.date,
        common_classification_name: str | None = None,
    ) -> None:
        """Validate a translated portfolio/benchmark pair and its host metadata."""
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
            raise PparError("Portfolio and benchmark performance periods do not match.")
        if not (
            portfolio_periods[cols.FROM_DATE][0] == expected_from_date
            and portfolio_periods[cols.THRU_DATE][-1] == expected_thru_date
        ):
            raise PparError(
                "Portfolio and benchmark performance do not match the expected date range."
            )
        if common_classification_name is not None and (
            portfolio.classification_name != common_classification_name
            or benchmark.classification_name != common_classification_name
        ):
            raise PparError(
                "Requested classification does not match both performance sources. "
                f"Requested={common_classification_name!r}, "
                f"portfolio={portfolio.classification_name!r}, "
                f"benchmark={benchmark.classification_name!r}."
            )

    def period_totals(self) -> pl.DataFrame:
        """Return one translated total-return row per reporting period."""
        return (
            self.narrow_df.select(
                *cols.DATE_COLUMNS,
                cols.QUANTITY_OF_DAYS,
                cols.TOTAL_RETURN,
            )
            .unique()
            .sort(cols.THRU_DATE)
        )

    def _replace_calculated_rows(
        self,
        df: pl.DataFrame,
        *,
        sort_rows: bool = True,
    ) -> None:
        """Take ownership of rows returned by the trusted portable boundary."""
        if len(df.columns) != len(_PPAR_PERFORMANCE_COLUMNS) or set(df.columns) != set(
            _PPAR_PERFORMANCE_COLUMNS
        ):
            raise PparError(
                f"{self.error_message_context}: calculated performance schema is invalid."
            )
        replacement = df.select(_PPAR_PERFORMANCE_COLUMNS).clone()
        if sort_rows:
            replacement = replacement.sort([cols.THRU_DATE, cols.IDENTIFIER])
        self.narrow_df = replacement
        self.identifiers = sorted(self.narrow_df[cols.IDENTIFIER].unique().to_list())
