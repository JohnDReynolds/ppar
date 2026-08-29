"""Reconcile Axys portfolio and security performance data.

This module operates on normalized Axys performance frames. It aligns common
portfolio/security periods and derives nonnegative security weights whose
weighted return approximates the reported portfolio return.
"""

from __future__ import annotations

# Python imports
import datetime as dt
import math
from typing import Callable, Final

# Third-party imports
import polars as pl

# Project imports
import ppar.schema as cols
from ppar.axys_apx.weight_solver import derive_reconciled_weights
from ppar.errors import PparError

ErrorMessage = Callable[[str], str]
UnreconciledPeriod = tuple[tuple[str, dt.date, dt.date], float, float]

_FATAL_PERIOD_TOLERANCE = 0.0001
_PERIOD_TOLERANCE: Final[float] = 0.0000001
_PERIOD_UNIQUE_KEY_COLUMNS: Final[tuple[str, ...]] = (
    cols.PORTFOLIO_CODE,
    cols.FROM_DATE,
    cols.THRU_DATE,
)


def filter_to_common_periods(
    portfolio_performance: pl.DataFrame,
    security_performance: pl.DataFrame,
    error_message: ErrorMessage,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Keep only periods represented in both performance sources.

    Args:
        portfolio_performance: Portfolio-level performance rows.
        security_performance: Security-level performance rows.
        error_message: Callback that adds facade-level source context to error
            messages.

    Returns:
        Tuple containing portfolio and security rows restricted to common
        portfolio code, from date, and thru date keys.

    Raises:
        PparError: If the sources do not have any common periods.
    """
    portfolio_performance_periods = portfolio_performance.select(
        _PERIOD_UNIQUE_KEY_COLUMNS
    ).unique()
    security_performance_periods = security_performance.select(
        _PERIOD_UNIQUE_KEY_COLUMNS
    ).unique()
    common_periods = portfolio_performance_periods.join(
        security_performance_periods,
        on=_PERIOD_UNIQUE_KEY_COLUMNS,
        how="inner",
    )
    if common_periods.is_empty():
        raise PparError(
            error_message(
                "Portfolio and security performance have no common reporting periods."
            )
        )
    return (
        portfolio_performance.join(common_periods, on=_PERIOD_UNIQUE_KEY_COLUMNS, how="inner"),
        security_performance.join(common_periods, on=_PERIOD_UNIQUE_KEY_COLUMNS, how="inner"),
    )


# pylint: disable-next=too-many-locals
def derive_security_performance_for_all_periods(
    portfolio_performance: pl.DataFrame,
    security_performance: pl.DataFrame,
    error_message: ErrorMessage,
) -> tuple[pl.DataFrame, set[UnreconciledPeriod]]:
    """Return security performance with reconciled weights for every period.

    Args:
        portfolio_performance: Portfolio-level performance rows with one row
            per period.
        security_performance: Security-level performance rows for the
            portfolio periods.
        error_message: Callback that adds facade-level source context to error
            messages.

    Returns:
        Tuple containing security rows with derived weights and a set of
        periods whose achieved returns differ from reported returns by more
        than the ordinary-period tolerance but less than the fatal tolerance.

    Raises:
        PparError: If portfolio periods are duplicated, a portfolio period has
            no security rows, a derived period return is materially different
            from its portfolio return, or a security row is not assigned a
            weight.
    """
    duplicate_periods = (
        portfolio_performance.group_by(_PERIOD_UNIQUE_KEY_COLUMNS)
        .len()
        .filter(pl.col("len") > 1)
    )
    if not duplicate_periods.is_empty():
        raise PparError(
            error_message(
                "Duplicate portfolio performance periods: "
                f"{duplicate_periods.head(10).to_dicts()}"
            ),
        )

    security_performance_with_row_index = security_performance.with_row_index(name="_ROW_IDX")
    security_performance_lookup = security_performance_with_row_index.partition_by(
        _PERIOD_UNIQUE_KEY_COLUMNS,
        as_dict=True,
    )
    adjusted_weight_values: list[float] = [float("nan")] * security_performance.height
    unreconciled_periods: set[UnreconciledPeriod] = set()

    for portfolio_code, from_date, thru_date, port_return in portfolio_performance.select(
        [
            cols.PORTFOLIO_CODE,
            cols.FROM_DATE,
            cols.THRU_DATE,
            cols.PORTFOLIO_RETURN,
        ]
    ).iter_rows():
        key = (str(portfolio_code), from_date, thru_date)
        target_return = float(port_return)
        security_performance_period = security_performance_lookup.get(key)
        if security_performance_period is None or security_performance_period.is_empty():
            raise PparError(
                error_message(f"No security performance rows for period {key}"),
            )

        adjusted_weights, achieved_return = derive_reconciled_weights(
            security_performance_period,
            target_return,
        )
        for row_index, adjusted_weight in zip(
            security_performance_period["_ROW_IDX"].to_list(), adjusted_weights
        ):
            adjusted_weight_values[int(row_index)] = adjusted_weight

        difference = abs(achieved_return - target_return)
        if _FATAL_PERIOD_TOLERANCE < difference:
            raise PparError(
                error_message(f"Return off by {difference} for period {key}"),
            )
        if _PERIOD_TOLERANCE < difference:
            unreconciled_periods.add((key, target_return, achieved_return))

    if any(math.isnan(weight) for weight in adjusted_weight_values):
        raise PparError(
            error_message(
                f"Incomplete {cols.WEIGHT} assignment. One or more security "
                "performance rows were not "
                "assigned a derived weight."
            ),
        )
    reconciled_security_performance = security_performance.with_columns(
        pl.Series(name=cols.WEIGHT, values=adjusted_weight_values, dtype=pl.Float64)
    )
    return reconciled_security_performance, unreconciled_periods


def unreconciled_difference(unreconciled_periods: set[UnreconciledPeriod]) -> float:
    """Return absolute aggregate difference across unreconciled periods.

    Args:
        unreconciled_periods: Period keys with target and achieved returns.

    Returns:
        Absolute difference between summed target returns and summed achieved
        returns.
    """
    return abs(
        sum(target for _, target, _ in unreconciled_periods)
        - sum(achieved for _, _, achieved in unreconciled_periods)
    )


def exceeds_fatal_tolerance(difference: float) -> bool:
    """Return whether a return difference exceeds the fatal threshold.

    Args:
        difference: Absolute aggregate reconciliation difference.

    Returns:
        ``True`` if ``difference`` is larger than the fatal period tolerance;
        otherwise, ``False``.
    """
    return _FATAL_PERIOD_TOLERANCE < difference
