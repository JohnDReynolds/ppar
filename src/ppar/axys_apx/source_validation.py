"""Share narrow validation rules across Axys/APX source boundaries."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import polars as pl

import ppar.schema as cols
from ppar.errors import PparError
import ppar.utilities as util


ErrorMessage = Callable[[str], str]
_NORMALIZED_VALUE_COLUMN = "__ppar_normalized_financial_value"


def sample_rows(
    frame: pl.DataFrame,
    column_names: Sequence[str],
) -> list[dict[str, object]]:
    """Return compact diagnostic rows with dates formatted for readability.

    Args:
        frame: Rows containing invalid or conflicting source evidence.
        column_names: Ordered columns to include in the diagnostic sample.

    Returns:
        At most ten rows represented as dictionaries. Date values use ISO format.
    """
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


def diagnostic_columns(frame: pl.DataFrame, value_column: str) -> list[str]:
    """Return available account, period, and offending-value columns.

    Args:
        frame: Source rows used to build a diagnostic sample.
        value_column: Financial or identity field containing invalid evidence.

    Returns:
        Existing context columns in stable order without duplicates.
    """
    return list(
        dict.fromkeys(
            name
            for name in (
                cols.PORTFOLIO_CODE,
                cols.FROM_DATE,
                cols.THRU_DATE,
                value_column,
            )
            if name in frame.columns
        )
    )


def normalize_financial_fields(
    frame: pl.DataFrame,
    dataset_name: str,
    fields: Sequence[tuple[str, bool]],
    error_message: ErrorMessage,
    *,
    source_path: util.PathLike | None = None,
) -> pl.DataFrame:
    """Cast financial fields to ``Float64`` and reject invalid evidence.

    Args:
        frame: Portfolio- or security-performance rows.
        dataset_name: Source kind used in error details.
        fields: Field names paired with whether null values are invalid.
        error_message: Callback adding facade-level source context.
        source_path: Optional source CSV path included in loader errors. Defensive
            in-memory boundaries omit it.

    Returns:
        Frame with validated financial columns represented as ``Float64``.

    Raises:
        PparError: If a required value is null or any non-null value cannot be
            converted to a finite number.
    """
    for column_name, required in fields:
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
            affected_rows = sample_rows(
                invalid_rows,
                diagnostic_columns(invalid_rows, column_name),
            )
            requirement = (
                "a finite numeric value"
                if required
                else "either null or a finite numeric value"
            )
            source_context = (
                f" in {str(source_path)!r}" if source_path is not None else ""
            )
            raise PparError(
                error_message(
                    f"Financial field {column_name!r}{source_context} for "
                    f"{dataset_name} must contain {requirement}. "
                    f"Affected rows: {affected_rows}"
                )
            )
        frame = normalized.with_columns(
            pl.col(_NORMALIZED_VALUE_COLUMN).alias(column_name)
        ).drop(_NORMALIZED_VALUE_COLUMN)
    return frame
