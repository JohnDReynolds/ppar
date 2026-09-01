"""Reconcile Axys portfolio and security performance data.

This module operates on normalized Axys performance frames. It aligns common
portfolio/security periods and derives evidence-based signed security weights
whose weighted return matches the reported portfolio return.
"""

from __future__ import annotations

# Python imports
import datetime as dt
import math
from typing import Callable, Final, Sequence

# Third-party imports
import polars as pl

# Project imports
import ppar.schema as cols
from ppar.axys_apx.weight_solver import derive_reconciled_weights
from ppar.errors import PparError

ErrorMessage = Callable[[str], str]
ReconciliationPeriod = tuple[tuple[str, dt.date, dt.date], float, float]

_FATAL_PERIOD_TOLERANCE = 0.0001
_PERIOD_TOLERANCE: Final[float] = 0.0000001
_PERIOD_UNIQUE_KEY_COLUMNS: Final[tuple[str, ...]] = (
    cols.PORTFOLIO_CODE,
    cols.FROM_DATE,
    cols.THRU_DATE,
)
_SECURITY_UNIQUE_KEY_COLUMNS: Final[tuple[str, ...]] = (
    *_PERIOD_UNIQUE_KEY_COLUMNS,
    cols.IDENTIFIER,
)
_NORMALIZED_VALUE_COLUMN: Final[str] = "__ppar_normalized_financial_value"


def _sample_rows(
    frame: pl.DataFrame,
    column_names: Sequence[str],
) -> list[dict[str, object]]:
    """Return compact error rows with dates formatted for readability."""
    sample = frame.select(column_names).head(10)
    date_columns = [
        column_name
        for column_name in cols.DATE_COLUMNS
        if column_name in sample.columns and sample.schema[column_name] == pl.Date
    ]
    if date_columns:
        sample = sample.with_columns(
            pl.col(column_name).dt.to_string("%Y-%m-%d")
            for column_name in date_columns
        )
    return sample.to_dicts()


def _normalize_financial_values(
    frame: pl.DataFrame,
    dataset_name: str,
    columns: tuple[tuple[str, bool], ...],
    error_message: ErrorMessage,
) -> pl.DataFrame:
    """Return a numeric frame after defensive finite-value validation.

    Args:
        frame: Portfolio- or security-performance rows.
        dataset_name: Source kind used in error details.
        columns: Column names paired with whether null values are invalid.
        error_message: Callback that adds facade-level source context.

    Returns:
        Frame with validated financial columns represented as ``Float64``.

    Raises:
        PparError: If a required value is null or any non-null value cannot be
            converted to a finite number.
    """
    for column_name, required in columns:
        normalized = frame.with_columns(
            pl.col(column_name)
            .cast(pl.Float64, strict=False)
            .alias(_NORMALIZED_VALUE_COLUMN)
        )
        normalized_value = pl.col(_NORMALIZED_VALUE_COLUMN)
        invalid_value = (
            normalized_value.is_nan().fill_null(False)
            | normalized_value.is_infinite().fill_null(False)
        )
        if required:
            invalid_value = invalid_value | normalized_value.is_null()
        else:
            invalid_value = invalid_value | (
                pl.col(column_name).is_not_null()
                & normalized_value.is_null()
            )
        invalid_rows = normalized.filter(invalid_value)
        if not invalid_rows.is_empty():
            sample_columns = list(
                dict.fromkeys(
                    name
                    for name in (
                        cols.PORTFOLIO_CODE,
                        cols.FROM_DATE,
                        cols.THRU_DATE,
                        column_name,
                    )
                    if name in invalid_rows.columns
                )
            )
            sample_rows = _sample_rows(invalid_rows, sample_columns)
            requirement = (
                "a finite numeric value"
                if required
                else "either null or a finite numeric value"
            )
            raise PparError(
                error_message(
                    f"Financial field {column_name!r} for {dataset_name} must "
                    f"contain {requirement}. Affected rows: {sample_rows}"
                )
            )
        frame = normalized.with_columns(
            pl.col(_NORMALIZED_VALUE_COLUMN).alias(column_name)
        ).drop(_NORMALIZED_VALUE_COLUMN)
    return frame


def filter_to_common_periods(
    portfolio_performance: pl.DataFrame,
    security_performance: pl.DataFrame,
    error_message: ErrorMessage,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Require identical period keys in both performance sources.

    Args:
        portfolio_performance: Portfolio-level performance rows.
        security_performance: Security-level performance rows.
        error_message: Callback that adds facade-level source context to error
            messages.

    Returns:
        The unchanged portfolio and security rows after validation.

    Raises:
        PparError: If either source is empty or its period-key set differs
            from the other source.
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
    missing_from_security = portfolio_performance_periods.join(
        security_performance_periods,
        on=_PERIOD_UNIQUE_KEY_COLUMNS,
        how="anti",
    )
    missing_from_portfolio = security_performance_periods.join(
        portfolio_performance_periods,
        on=_PERIOD_UNIQUE_KEY_COLUMNS,
        how="anti",
    )
    if not missing_from_security.is_empty() or not missing_from_portfolio.is_empty():
        key_columns = list(_PERIOD_UNIQUE_KEY_COLUMNS)
        raise PparError(
            error_message(
                "Portfolio and security performance period keys differ. "
                "Missing from security_performance: "
                f"{_sample_rows(missing_from_security, key_columns)}. "
                "Missing from portfolio_performance: "
                f"{_sample_rows(missing_from_portfolio, key_columns)}."
            )
        )
    return portfolio_performance, security_performance


# pylint: disable-next=too-many-locals
def derive_security_performance_for_all_periods(
    portfolio_performance: pl.DataFrame,
    security_performance: pl.DataFrame,
    error_message: ErrorMessage,
) -> tuple[pl.DataFrame, set[ReconciliationPeriod]]:
    """Return security performance with reconciled weights for every period.

    Args:
        portfolio_performance: Portfolio-level performance rows with one row
            per period.
        security_performance: Security-level performance rows for the
            portfolio periods.
        error_message: Callback that adds facade-level source context to error
            messages.

    Returns:
        Tuple containing security rows with derived weights and every period's
        target and achieved returns for independent geometric linking.

    Raises:
        PparError: If financial values are invalid, portfolio periods are
            duplicated, security identifiers repeat within a portfolio period,
            a portfolio period has no security rows, weight evidence cannot be
            reconciled, a derived period return is materially different from
            its portfolio return, or a security row is not assigned a weight.
    """
    portfolio_performance = _normalize_financial_values(
        portfolio_performance,
        "portfolio_performance",
        ((cols.PORTFOLIO_RETURN, True),),
        error_message,
    )
    security_performance = _normalize_financial_values(
        security_performance,
        "security_performance",
        (
            (cols.RETURN, True),
            (cols.WEIGHT, False),
            (cols.CONTRIBUTION, False),
        ),
        error_message,
    )
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

    duplicate_security_rows = (
        security_performance.group_by(_SECURITY_UNIQUE_KEY_COLUMNS)
        .len()
        .filter(pl.col("len") > 1)
    )
    if not duplicate_security_rows.is_empty():
        sample_columns = [*_SECURITY_UNIQUE_KEY_COLUMNS, "len"]
        raise PparError(
            error_message(
                "Duplicate security performance rows are ambiguous and cannot "
                "be reconciled safely. Affected keys: "
                f"{_sample_rows(duplicate_security_rows, sample_columns)}"
            )
        )

    security_performance_with_row_index = security_performance.with_row_index(name="_ROW_IDX")
    security_performance_lookup = security_performance_with_row_index.partition_by(
        _PERIOD_UNIQUE_KEY_COLUMNS,
        as_dict=True,
    )
    adjusted_weight_values: list[float] = [float("nan")] * security_performance.height
    reconciliation_periods: set[ReconciliationPeriod] = set()

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

        try:
            adjusted_weights, achieved_return = derive_reconciled_weights(
                security_performance_period,
                target_return,
            )
        except ValueError as error:
            raise PparError(
                error_message(
                    f"Cannot reconcile security weights for period {key}: {error}"
                )
            ) from error
        for row_index, adjusted_weight in zip(
            security_performance_period["_ROW_IDX"].to_list(), adjusted_weights
        ):
            adjusted_weight_values[int(row_index)] = adjusted_weight

        difference = abs(achieved_return - target_return)
        if _FATAL_PERIOD_TOLERANCE < difference:
            raise PparError(
                error_message(f"Return off by {difference} for period {key}"),
            )
        reconciliation_periods.add((key, target_return, achieved_return))

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
    return reconciled_security_performance, reconciliation_periods


def unreconciled_difference(
    reconciliation_periods: set[ReconciliationPeriod],
) -> float:
    """Return the difference between independently linked return paths.

    Args:
        reconciliation_periods: Period keys with target and achieved returns.

    Returns:
        Absolute difference between geometrically linked target and achieved
        returns.
    """
    ordered_periods = sorted(reconciliation_periods, key=lambda period: period[0])
    linked_target = math.prod(1.0 + target for _, target, _ in ordered_periods)
    linked_achieved = math.prod(
        1.0 + achieved for _, _, achieved in ordered_periods
    )
    return abs(linked_target - linked_achieved)


def material_reconciliation_periods(
    reconciliation_periods: set[ReconciliationPeriod],
) -> list[ReconciliationPeriod]:
    """Return period residuals above the unchanged ordinary tolerance.

    Args:
        reconciliation_periods: Period keys with target and achieved returns.

    Returns:
        Material period residuals in chronological key order.
    """
    return sorted(
        (
            period
            for period in reconciliation_periods
            if abs(period[1] - period[2]) > _PERIOD_TOLERANCE
        ),
        key=lambda period: period[0],
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
