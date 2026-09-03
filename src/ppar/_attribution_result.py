"""Internal numerical-result boundary between calculation and presentation."""

from dataclasses import dataclass

import numpy as np
import polars as pl

import ppar.schema as cols


@dataclass
class AttributionCalculationResult:
    """Hold the numerical frames consumed by attribution presentation.

    Attributes:
        period_summary: Period totals, linked values, and cumulative values.
        period_detail: Per-period identifier attribution values.
        overall_summary: One full-horizon totals row.
        overall_detail: Full-horizon identifier attribution values.

    Notes:
        Frames use the existing ``ppar`` calculation schema. Presentation additions,
        including classification names and total rows, are deliberately excluded.
    """

    period_summary: pl.DataFrame
    period_detail: pl.DataFrame
    overall_summary: pl.DataFrame
    overall_detail: pl.DataFrame


def overall_summary_from_periods(period_summary: pl.DataFrame) -> pl.DataFrame:
    """Build the ppar full-horizon totals row from translated period results."""
    portfolio_overall_return = period_summary[
        -1, cols.CUMULATIVE_PORTFOLIO_RETURN
    ]
    benchmark_overall_return = period_summary[
        -1, cols.CUMULATIVE_BENCHMARK_RETURN
    ]
    overall = period_summary.sum()
    overall[0, cols.FROM_DATE] = period_summary[cols.FROM_DATE][0]
    overall[0, cols.THRU_DATE] = period_summary[cols.THRU_DATE][-1]
    overall[0, cols.PORTFOLIO_RETURN] = portfolio_overall_return
    overall[0, cols.BENCHMARK_RETURN] = benchmark_overall_return
    overall[0, cols.ACTIVE_RETURN] = (
        portfolio_overall_return - benchmark_overall_return
    )
    for column in cols.ALL_CUMULATIVE_COLUMNS:
        overall[0, column] = period_summary[-1, column]
    for column in cols.ALL_SIMPLE_COLUMNS:
        overall[0, column] = np.nan
    return overall
