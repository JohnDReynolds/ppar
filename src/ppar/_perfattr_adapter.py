"""Adapt prepared ppar attribution rows to the portable pandas calculator."""

from collections.abc import Mapping, Sequence

import pandas as pd
import polars as pl
from perfattr import AttributionError, AttributionResult, calculate_attribution

from ppar._attribution_result import (
    AttributionCalculationResult,
    overall_summary_from_periods,
)
from ppar.errors import PparError
from ppar.performance import Performance
import ppar.schema as cols


_INPUT_COLUMNS = (
    cols.FROM_DATE,
    cols.THRU_DATE,
    cols.IDENTIFIER,
    cols.WEIGHT,
    cols.RETURN,
    cols.CONTRIBUTION,
    cols.QUANTITY_OF_DAYS,
)
_PPAR_RECONCILIATION_TOLERANCE = 5e-9

_PERIOD_DETAIL_COLUMNS = (
    *cols.DATE_COLUMNS,
    cols.CLASSIFICATION_IDENTIFIER,
    *cols.PORTFOLIO_COLUMNS_SIMPLE,
    cols.PORTFOLIO_CONTRIB_SMOOTHED,
    *cols.BENCHMARK_COLUMNS_SIMPLE,
    cols.BENCHMARK_CONTRIB_SMOOTHED,
    *cols.ACTIVE_COLUMNS_SIMPLE,
    cols.ACTIVE_CONTRIB_SMOOTHED,
    *cols.ATTRIBUTION_COLUMNS_SIMPLE,
    *cols.ATTRIBUTION_COLUMNS_SMOOTHED,
)
_PERIOD_DETAIL_NAMES = {
    "identifier": cols.CLASSIFICATION_IDENTIFIER,
    "portfolio_weight": cols.PORTFOLIO_WEIGHT,
    "portfolio_return": cols.PORTFOLIO_RETURN,
    "portfolio_contribution": cols.PORTFOLIO_CONTRIB_SIMPLE,
    "linked_portfolio_contribution": cols.PORTFOLIO_CONTRIB_SMOOTHED,
    "benchmark_weight": cols.BENCHMARK_WEIGHT,
    "benchmark_return": cols.BENCHMARK_RETURN,
    "benchmark_contribution": cols.BENCHMARK_CONTRIB_SIMPLE,
    "linked_benchmark_contribution": cols.BENCHMARK_CONTRIB_SMOOTHED,
    "active_weight": cols.ACTIVE_WEIGHT,
    "active_return": cols.ACTIVE_RETURN,
    "active_contribution": cols.ACTIVE_CONTRIB_SIMPLE,
    "linked_active_contribution": cols.ACTIVE_CONTRIB_SMOOTHED,
    "allocation_effect": cols.ALLOCATION_EFFECT_SIMPLE,
    "selection_effect": cols.SELECTION_EFFECT_SIMPLE,
    "total_effect": cols.TOTAL_EFFECT_SIMPLE,
    "linked_allocation_effect": cols.ALLOCATION_EFFECT_SMOOTHED,
    "linked_selection_effect": cols.SELECTION_EFFECT_SMOOTHED,
    "linked_total_effect": cols.TOTAL_EFFECT_SMOOTHED,
}

_OVERALL_DETAIL_COLUMNS = (
    cols.FROM_DATE,
    cols.THRU_DATE,
    cols.CLASSIFICATION_IDENTIFIER,
    cols.PORTFOLIO_RETURN,
    cols.PORTFOLIO_WEIGHT,
    cols.BENCHMARK_RETURN,
    cols.BENCHMARK_WEIGHT,
    cols.PORTFOLIO_CONTRIB_SMOOTHED,
    cols.BENCHMARK_CONTRIB_SMOOTHED,
    cols.ALLOCATION_EFFECT_SMOOTHED,
    cols.SELECTION_EFFECT_SMOOTHED,
    cols.ACTIVE_RETURN,
    cols.ACTIVE_WEIGHT,
    cols.ACTIVE_CONTRIB_SMOOTHED,
    cols.TOTAL_EFFECT_SMOOTHED,
)
_OVERALL_DETAIL_NAMES = {
    "identifier": cols.CLASSIFICATION_IDENTIFIER,
    "portfolio_weight": cols.PORTFOLIO_WEIGHT,
    "portfolio_return": cols.PORTFOLIO_RETURN,
    "linked_portfolio_contribution": cols.PORTFOLIO_CONTRIB_SMOOTHED,
    "benchmark_weight": cols.BENCHMARK_WEIGHT,
    "benchmark_return": cols.BENCHMARK_RETURN,
    "linked_benchmark_contribution": cols.BENCHMARK_CONTRIB_SMOOTHED,
    "active_weight": cols.ACTIVE_WEIGHT,
    "active_return": cols.ACTIVE_RETURN,
    "linked_active_contribution": cols.ACTIVE_CONTRIB_SMOOTHED,
    "linked_allocation_effect": cols.ALLOCATION_EFFECT_SMOOTHED,
    "linked_selection_effect": cols.SELECTION_EFFECT_SMOOTHED,
    "linked_total_effect": cols.TOTAL_EFFECT_SMOOTHED,
}


def _to_portable_input(performance: Performance) -> pd.DataFrame:
    """Convert one prepared Polars performance frame to the portable input schema."""
    rows = performance.narrow_df.select(_INPUT_COLUMNS).rename(
        {cols.QUANTITY_OF_DAYS: "quantity_of_days"}
    )
    return pd.DataFrame(rows.to_dict(as_series=False))


def _to_polars(
    frame: pd.DataFrame,
    names: Mapping[str, str],
    columns: Sequence[str],
) -> pl.DataFrame:
    """Translate one portable result frame without requiring PyArrow."""
    renamed = frame.rename(columns=names)
    translated = pl.DataFrame(
        {column: renamed[column].tolist() for column in columns}
    ).with_columns(pl.col(cols.DATE_COLUMNS).cast(pl.Date))
    nullable_returns = [
        column for column in cols.RETURN_COLUMNS if column in translated.columns
    ]
    if nullable_returns:
        translated = translated.with_columns(pl.col(nullable_returns).fill_nan(None))
    return translated


def _period_summary(result: AttributionResult) -> pl.DataFrame:
    """Translate portable period and cumulative totals to the ppar summary schema."""
    summary = result.period_summary
    cumulative = result.cumulative
    values = {
        cols.FROM_DATE: summary["from_date"].tolist(),
        cols.THRU_DATE: summary["thru_date"].tolist(),
        cols.PORTFOLIO_CONTRIB_SIMPLE: summary["portfolio_contribution"].tolist(),
        cols.BENCHMARK_CONTRIB_SIMPLE: summary["benchmark_contribution"].tolist(),
        cols.PORTFOLIO_CONTRIB_SMOOTHED: summary[
            "linked_portfolio_contribution"
        ].tolist(),
        cols.BENCHMARK_CONTRIB_SMOOTHED: summary[
            "linked_benchmark_contribution"
        ].tolist(),
        cols.ALLOCATION_EFFECT_SIMPLE: summary["allocation_effect"].tolist(),
        cols.SELECTION_EFFECT_SIMPLE: summary["selection_effect"].tolist(),
        cols.ALLOCATION_EFFECT_SMOOTHED: summary[
            "linked_allocation_effect"
        ].tolist(),
        cols.SELECTION_EFFECT_SMOOTHED: summary[
            "linked_selection_effect"
        ].tolist(),
        cols.PORTFOLIO_RETURN: summary["portfolio_return"].tolist(),
        cols.BENCHMARK_RETURN: summary["benchmark_return"].tolist(),
        cols.ACTIVE_RETURN: summary["active_return"].tolist(),
        cols.ACTIVE_CONTRIB_SIMPLE: summary["active_contribution"].tolist(),
        cols.ACTIVE_CONTRIB_SMOOTHED: summary[
            "linked_active_contribution"
        ].tolist(),
        cols.TOTAL_EFFECT_SIMPLE: summary["total_effect"].tolist(),
        cols.TOTAL_EFFECT_SMOOTHED: summary["linked_total_effect"].tolist(),
        cols.CUMULATIVE_PORTFOLIO_RETURN: cumulative[
            "cumulative_portfolio_return"
        ].tolist(),
        cols.CUMULATIVE_BENCHMARK_RETURN: cumulative[
            "cumulative_benchmark_return"
        ].tolist(),
        cols.CUMULATIVE_PORTFOLIO_CONTRIB: cumulative[
            "cumulative_portfolio_contribution"
        ].tolist(),
        cols.CUMULATIVE_BENCHMARK_CONTRIB: cumulative[
            "cumulative_benchmark_contribution"
        ].tolist(),
        cols.CUMULATIVE_ALLOCATION_EFFECT: cumulative[
            "cumulative_allocation_effect"
        ].tolist(),
        cols.CUMULATIVE_SELECTION_EFFECT: cumulative[
            "cumulative_selection_effect"
        ].tolist(),
        cols.CUMULATIVE_TOTAL_EFFECT: cumulative[
            "cumulative_total_effect"
        ].tolist(),
        cols.CUMULATIVE_ACTIVE_RETURN: cumulative[
            "cumulative_active_return"
        ].tolist(),
        cols.CUMULATIVE_ACTIVE_CONTRIB: cumulative[
            "cumulative_active_contribution"
        ].tolist(),
    }
    return pl.DataFrame(values).with_columns(pl.col(cols.DATE_COLUMNS).cast(pl.Date))


def calculate_with_perfattr(
    performances: Sequence[Performance],
) -> AttributionCalculationResult:
    """Calculate prepared ppar performance rows with the portable pandas engine.

    Args:
        performances: Portfolio and benchmark performance streams after all ppar
            loading, alignment, consolidation, and classification mapping.

    Returns:
        The portable result translated to ppar's established Polars boundary.

    Raises:
        PparError: If the portable calculator rejects the prepared financial input or
            cannot satisfy one of its reconciliation invariants.
    """
    portfolio, benchmark = performances
    try:
        portable_result = calculate_attribution(
            _to_portable_input(portfolio),
            _to_portable_input(benchmark),
            reconciliation_tolerance=_PPAR_RECONCILIATION_TOLERANCE,
        )
    except AttributionError as error:
        raise PparError(f"perfattr calculation failed: {error}") from error

    period_summary = _period_summary(portable_result)
    return AttributionCalculationResult(
        period_summary=period_summary,
        period_detail=_to_polars(
            portable_result.period_detail,
            _PERIOD_DETAIL_NAMES,
            _PERIOD_DETAIL_COLUMNS,
        ),
        overall_summary=overall_summary_from_periods(period_summary),
        overall_detail=_to_polars(
            portable_result.overall_detail,
            _OVERALL_DETAIL_NAMES,
            _OVERALL_DETAIL_COLUMNS,
        ),
    )
