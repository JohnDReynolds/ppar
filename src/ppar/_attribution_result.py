"""Internal numerical-result boundary for attribution calculation engines."""

from dataclasses import dataclass

import polars as pl


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
