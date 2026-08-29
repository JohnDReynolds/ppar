"""Utility functions, type aliases, and constants used across the package.

Public helpers in this module support package users that need the same date,
path, tolerance, data-source, and linking semantics used internally.
"""

# Python Imports
import datetime as dt
from enum import Enum
import math
from pathlib import Path
from typing import Sequence, TypeAlias, TypeVar

# Third-Party Imports
import numpy as np
import polars as pl

# Project Imports
from ppar.errors import PparError

__all__ = [
    "PathLike",
    "AllDataSources",
    "ClassificationDataSource",
    "MappingDataSource",
    "PerformanceDataSource",
    "DATE_FORMAT_STRING",
    "DEFAULT_ANNUAL_MINIMUM_ACCEPTABLE_RETURN",
    "DEFAULT_ANNUAL_RISK_FREE_RATE",
    "DEFAULT_CONFIDENCE_LEVEL",
    "DEFAULT_CURRENCY_SYMBOL",
    "DEFAULT_PORTFOLIO_VALUE",
    "ENCODING",
    "Tolerance",
    "are_near",
    "carino_linking_coefficient",
    "convert_to_date",
    "date_str",
    "file_basename_without_extension",
    "file_path_error",
    "file_path_exists",
    "normalize_optional_string",
    "load_datasource",
    "logarithmic_linking_coefficients",
    "logarithmic_linking_coefficient_series",
    "logarithmic_smoothing_coefficients",
    "near_zero",
    "two_item_tuple",
]

# Types for type-checking.
PathLike: TypeAlias = str | Path
AllDataSources: TypeAlias = PathLike | pl.DataFrame
ClassificationDataSource: TypeAlias = AllDataSources
MappingDataSource: TypeAlias = AllDataSources
PerformanceDataSource: TypeAlias = PathLike | pl.DataFrame

# Miscellaneous Common Constants
ENCODING = "utf-8"
DATE_FORMAT_STRING = "%Y-%m-%d"  # yyyy-mm-dd
DEFAULT_ANNUAL_MINIMUM_ACCEPTABLE_RETURN = 0.0
DEFAULT_ANNUAL_RISK_FREE_RATE = 0.03  # 3%
DEFAULT_CONFIDENCE_LEVEL = 0.95  # 95%
DEFAULT_CURRENCY_SYMBOL = "$"
DEFAULT_PORTFOLIO_VALUE = 100_000  # $100,000
_UNDEFINED_RETURN = -1.0
_T = TypeVar("_T")


def file_basename_without_extension(file_path: PathLike) -> str:
    """Return a file name without its directory or first extension."""
    return Path(file_path).name.split(".")[0]


def file_path_error(file_path: PathLike) -> str:
    """Return an actionable file-path validation message."""
    is_blank_path = isinstance(file_path, str) and not file_path.strip()
    return "Missing data source." if is_blank_path else f"File does not exist: {file_path}"


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


def carino_linking_coefficient(portfolio_return: float, benchmark_return: float) -> float:
    """Calculate the Carino linking coefficient for two returns.

    Args:
        portfolio_return: The portfolio return expressed as a decimal.
        benchmark_return: The benchmark return expressed as a decimal.

    Returns:
        The Carino linking coefficient.

    Raises:
        PparError: If either return is less than or equal to -100%, because the
            logarithmic calculation would be undefined.
    """
    # Check for invalid returns.  The Log of a number <= 0 is undefined.
    if portfolio_return <= _UNDEFINED_RETURN:
        raise PparError(f"The portfolio has a return of {portfolio_return:.6f}")
    if benchmark_return <= _UNDEFINED_RETURN:
        raise PparError(f"The benchmark has a return of {benchmark_return:.6f}")

    # Get the difference between the portfolio_return and the benchmark_return
    return_difference = portfolio_return - benchmark_return

    # If the portfolio and benchmark returns are almost identical, then the standard formula below
    # will give non-sensical results with a tiny-tiny denominator.  So return an alternate formula.
    if near_zero(return_difference):
        return 1.0 / (1.0 + portfolio_return)

    # Return the carino k-factor.
    return (
        math.log(1.0 + portfolio_return) - math.log(1.0 + benchmark_return)
    ) / return_difference


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


def date_str(date: dt.date) -> str:
    """Format a date using the package date format.

    Args:
        date: The date to format.

    Returns:
        The date formatted as ``yyyy-mm-dd``.
    """
    return date.strftime(DATE_FORMAT_STRING)


def normalize_optional_string(value: str | None) -> str | None:
    """Normalize optional public string arguments to ``None``.

    Args:
        value: Optional string value supplied by the caller.

    Returns:
        ``None`` for omitted or blank strings; otherwise, ``value``.
    """
    if value is None or not value.strip():
        return None
    return value


def load_datasource(
    data_source: AllDataSources,
    column_names: Sequence[str],
    needed_items: Sequence[str],
    error_message: str,
) -> pl.DataFrame:
    """Load a two-column data source into a normalized Polars DataFrame.

    Args:
        data_source: CSV file path or Polars DataFrame containing source rows.
        column_names: The two output column names to assign to the DataFrame.
        needed_items: The allowed values for the first output column. Rows with
            other first-column values are filtered out.
        error_message: The error message to use if the loaded source does not
            contain exactly two columns.

    Returns:
        A two-column Polars DataFrame with normalized column names, duplicate
        first-column values removed, values cast to strings for non-file inputs,
        and rows filtered to ``needed_items``.

    Raises:
        PparError: If ``data_source`` is a file path that does not point to an
            existing file, or if the loaded source does not contain exactly two
            columns.
    """
    # Get the 2-column dataframe.
    is_file_source = isinstance(data_source, str | Path)
    if isinstance(data_source, str | Path):
        data_source = Path(data_source)
        # Assert that the data file path exists.
        if not file_path_exists(data_source):
            raise PparError(file_path_error(data_source))
        # Load the data_source in lazy-mode.  infer_schema=False will force both columns to be the
        # default strings (Utf8).  Then filter on needed_items.
        lf = pl.scan_csv(data_source, has_header=False, infer_schema=False)
        column0_name = list(lf.collect_schema().keys())[0]
        df = lf.filter(pl.col(column0_name).is_in(needed_items)).collect()
    elif isinstance(data_source, pl.DataFrame):
        df = data_source.clone()
    else:
        raise PparError("Data source must be a CSV path or Polars DataFrame.")

    # Assert that you have 2 columns.
    if len(df.columns) != 2:
        raise PparError(error_message)

    # Give the columns consistent names.
    df.columns = column_names

    # Remove duplicates.
    df = df.unique(subset=[df.columns[0]], keep="last")

    # Cast to strings and filter on needed_items.  Note that this was done above in pl.scan_scv
    if not is_file_source:
        # All identifiers need to be strings for classifications, mappings, performances, etc.
        for column_name in df.columns:
            if not isinstance(df.schema[column_name], pl.String):
                df = df.with_columns(df[column_name].cast(pl.String))
        # Filter on only the needed_items.
        df = df.filter(pl.col(df.columns[0]).is_in(needed_items))

    # Return the dataframe.
    return df


def logarithmic_linking_coefficients(overall_return: float, returns: pl.Series) -> pl.Series:
    """Calculate logarithmic linking coefficients for subperiod returns.

    Args:
        overall_return: The total return for the full period, expressed as a
            decimal.
        returns: The subperiod returns, expressed as decimals.

    Returns:
        A Polars Series containing the linking coefficient for each subperiod
        return.

    Raises:
        PparError: If ``overall_return`` is less than or equal to -100%, or if
            any value in ``returns`` is less than or equal to -100%.
    """
    # A return < -1.0 is undefined.  And the log of a negative number is undefined.  So valiadte
    # that the return is greater than -1.0.  Note that this logic exactly mimics the logic in
    # logarithmic_smoothing_coefficients(), only it is done for a single value.
    if overall_return <= _UNDEFINED_RETURN:
        raise PparError(
            f"Overall return used for logarithmic linking must exceed -100%; "
            f"received {overall_return}."
        )
    denominator = np.log(1.0 + overall_return) / overall_return if overall_return != 0.0 else 1.0

    # Return the logarithmic_linking_coefficients
    return logarithmic_smoothing_coefficients(returns) / denominator


def logarithmic_linking_coefficient_series(
    overall_returns: pl.Series, returns: pl.Series
) -> pl.Series:
    """Calculate linking coefficients from series-level overall returns.

    Args:
        overall_returns: The full-period returns to use as denominators,
            expressed as decimals.
        returns: The subperiod returns to link, expressed as decimals.

    Returns:
        A Polars Series containing the linking coefficient for each return.

    Raises:
        PparError: If any value in ``overall_returns`` or ``returns`` is less
            than or equal to -100%.
    """
    return logarithmic_smoothing_coefficients(returns) / logarithmic_smoothing_coefficients(
        overall_returns
    )


def logarithmic_smoothing_coefficients(returns: pl.Series) -> pl.Series:
    """Calculate logarithmic smoothing coefficients for returns.

    Args:
        returns: The returns to smooth, expressed as decimals.

    Returns:
        A Polars Series containing the logarithmic smoothing coefficient for
        each return.

    Raises:
        PparError: If any return is less than or equal to -100%.
    """
    # A return < -1.0 is undefined.  And the log of a negative number is undefined.  So validate
    # that the returns are greater than -1.0.
    if not (returns > _UNDEFINED_RETURN).all():
        raise PparError("Returns used for logarithmic smoothing must exceed -100%.")

    ## Method 1: This method works great, but is a little slower than Method 2 below.
    # If the return is 0.0, then dividing by 0.0 will give nan.
    # So a return of 0.0 will correctly yield a coeficient of 1.0.
    # return (returns.log1p() / returns).fill_nan(1)  # pl.log1p() is the same as log(1 + value)

    ## Method 2: This method is slightly faster than Method 1.  And takes advantage of lazy.
    return (
        pl.LazyFrame(returns)
        .with_columns(
            pl.when(pl.col(returns.name) == 0.0)
            .then(1.0)
            .otherwise(pl.col(returns.name).log1p() / pl.col(returns.name))
            .alias(returns.name)
        )
        .collect()
    )[returns.name]


def near_zero(f: float, tolerance: Tolerance = Tolerance.HIGH) -> bool:
    """Return whether a float is near zero within the specified tolerance.

    Args:
        f: The value to compare with zero.
        tolerance: The comparison tolerance to apply.

    Returns:
        True if ``f`` is within ``tolerance`` of zero; otherwise, False.
    """
    return are_near(f, 0, tolerance)
