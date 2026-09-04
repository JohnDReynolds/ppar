"""Provide internal types and helpers shared across ppar modules."""

# Python Imports
import datetime as dt
from enum import Enum
from pathlib import Path
from typing import Sequence, TypeAlias, TypeVar

# Third-Party Imports
import polars as pl

# Project Imports
from ppar.errors import PparError

__all__: list[str] = []

# Types for type-checking.
PathLike: TypeAlias = str | Path

# Miscellaneous Common Constants
ENCODING = "utf-8"
DATE_FORMAT_STRING = "%Y-%m-%d"  # yyyy-mm-dd
DEFAULT_ANNUAL_MINIMUM_ACCEPTABLE_RETURN = 0.0
DEFAULT_ANNUAL_RISK_FREE_RATE = 0.03  # 3%
DEFAULT_CONFIDENCE_LEVEL = 0.95  # 95%
DEFAULT_CURRENCY_SYMBOL = "$"
DEFAULT_PORTFOLIO_VALUE = 100_000  # $100,000
_T = TypeVar("_T")


def file_basename_without_extension(file_path: PathLike) -> str:
    """Return a file name without its directory or final extension."""
    return Path(file_path).stem


def file_path_error(file_path: PathLike) -> str:
    """Return an actionable file-path validation message."""
    is_blank_path = isinstance(file_path, str) and not file_path.strip()
    return (
        "Data source path must not be blank."
        if is_blank_path
        else f"File does not exist: {file_path}"
    )


def file_path_exists(file_path: PathLike) -> bool:
    """Return whether a nonblank path identifies an existing file."""
    if isinstance(file_path, str) and not file_path.strip():
        return False
    return Path(file_path).is_file()


class Tolerance(Enum):
    """Floating-point comparison tolerances.

    Attributes:
        LOW: The loosest comparison tolerance.
        MEDIUM: A moderate comparison tolerance.
        HIGH: The strictest comparison tolerance.
    """

    LOW = 0.00000005
    MEDIUM = 0.0000000005
    HIGH = 0.0000000000005


def two_item_tuple(values: Sequence[_T], context: str) -> tuple[_T, _T]:
    """Normalize and validate a public two-item sequence.

    Args:
        values: Sequence expected to contain exactly two values.
        context: Short description included in validation diagnostics.

    Returns:
        The two values as a tuple.

    Raises:
        PparError: If ``values`` does not contain exactly two items.
    """
    try:
        normalized = tuple(values)
    except TypeError as error:
        raise PparError(
            f"{context} received a non-sequence value.",
            context={"boundary": context, "value": repr(values)},
        ) from error
    if len(normalized) != 2:
        raise PparError(
            f"{context} received {len(normalized)}.",
            context={"boundary": context, "item_count": len(normalized)},
        )
    return normalized


def are_near(f1: float, f2: float, tolerance: Tolerance = Tolerance.HIGH) -> bool:
    """Return whether two floats are within the specified tolerance.

    Args:
        f1: The first value to compare.
        f2: The second value to compare.
        tolerance: The comparison tolerance to apply.

    Returns:
        True if the absolute difference between ``f1`` and ``f2`` is less than
        ``tolerance``; otherwise, False.
    """
    return abs(f1 - f2) < tolerance.value


def convert_to_date(date: str | dt.date | dt.datetime) -> dt.date:
    """Convert a supported date value to a ``datetime.date``.

    Args:
        date: A ``datetime.date``, ``datetime.datetime``, or string in
            ``yyyy-mm-dd`` format.

    Returns:
        The value converted to a ``datetime.date``.

    Raises:
        PparError: If a string value cannot be parsed as ``yyyy-mm-dd``.
    """
    # Return the date if it is already in the proper format.
    if isinstance(date, dt.datetime):
        date = date.date()
    if isinstance(date, dt.date):
        return date

    # Try parsing the string date.
    try:
        return dt.datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as e:
        raise PparError(f"{date!r} must be in the format yyyy-mm-dd") from e


def normalize_optional_string(
    value: str | None,
    parameter_name: str = "value",
) -> str | None:
    """Validate an optional public string without treating blank as omission.

    Args:
        value: Optional string value supplied by the caller.
        parameter_name: Argument name used in validation details.

    Returns:
        ``None`` when omitted; otherwise, the supplied nonblank value.

    Raises:
        PparError: If a supplied string is blank.
    """
    if value is None:
        return None
    if not value.strip():
        raise PparError(
            f"{parameter_name} must not be blank; use None to omit it.",
            context={"parameter": parameter_name, "value": value},
        )
    return value


def invalid_identity_rows(
    frame: pl.DataFrame,
    column_name: str,
) -> pl.DataFrame:
    """Return rows whose textual identity is null or blank after trimming.

    Args:
        frame: Source rows containing a string identity column.
        column_name: Identity column to validate.

    Returns:
        Invalid rows in their original order.
    """
    value = pl.col(column_name)
    stripped_value = value.str.strip_chars()
    return frame.filter(value.is_null() | stripped_value.eq(""))
