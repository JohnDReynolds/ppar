"""Represent Axys reporting date windows."""

from __future__ import annotations

# Python imports
from dataclasses import dataclass
import datetime as dt

# Third-party imports
import polars as pl

# Project imports
import ppar.schema as cols


@dataclass(frozen=True)
class AxysDateRange:
    """Hold the inclusive Axys reporting date window for a load request.

    Attributes:
        from_date: Optional inclusive earliest reporting date to retain.
        thru_date: Optional inclusive latest thru date to retain.
    """

    from_date: dt.date | None = None
    thru_date: dt.date | None = None

    def filter_performance(self, lazy_frame: pl.LazyFrame) -> pl.LazyFrame:
        """Apply this date range to normalized Axys performance rows.

        Args:
            lazy_frame: Lazy performance rows with normalized date columns.

        Returns:
            Rows filtered to the requested inclusive date range.
        """
        if self.from_date is not None:
            lazy_frame = lazy_frame.filter(pl.lit(self.from_date) <= pl.col(cols.THRU_DATE))
        if self.thru_date is not None:
            lazy_frame = lazy_frame.filter(pl.col(cols.THRU_DATE) <= pl.lit(self.thru_date))
        return lazy_frame
