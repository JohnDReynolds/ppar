"""Provide internal types and helpers shared across ppar modules."""

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

__all__: list[str] = []

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


def normalize_text_columns(
    frame: pl.DataFrame,
    column_names: Sequence[str],
) -> pl.DataFrame:
    """Remove surrounding whitespace from textual source values.

    Args:
        frame: Source rows containing string columns.
        column_names: Columns to normalize.

    Returns:
        A new DataFrame with normalized columns. Null values remain null and
        meaningful internal whitespace is unchanged.
    """
    return frame.with_columns(
        pl.col(column_name).str.strip_chars().alias(column_name)
        for column_name in column_names
    )


def load_datasource(
    data_source: AllDataSources,
    column_names: Sequence[str],
    needed_items: Sequence[str],
    error_message: str,
    source_description: str = "Data source",
    identity_column_indices: Sequence[int] = (),
) -> pl.DataFrame:
    """Load a two-column data source into a normalized Polars DataFrame.

    Args:
        data_source: CSV file path or Polars DataFrame containing source rows.
        column_names: The two output column names to assign to the DataFrame.
        needed_items: The allowed values for the first output column. Rows with
            other first-column values are filtered out.
        error_message: Message used when the source does not contain two columns.
        source_description: Short source description used in conflict errors.
        identity_column_indices: Zero-based columns containing identities that
            must be validated before unused source rows are filtered.

    Returns:
        A two-column Polars DataFrame with normalized column names and surrounding
        whitespace removed, exact duplicate pairs removed, values cast to strings
        for non-file inputs, and rows filtered to ``needed_items``.

    Raises:
        PparError: If ``data_source`` is a file path that does not point to an
            existing file, if the loaded source does not contain exactly two
            columns, if a selected identity is invalid, or if one identifier
            has conflicting values.
    """
    # Get the 2-column dataframe.
    is_file_source = isinstance(data_source, str | Path)
    if isinstance(data_source, str | Path):
        if isinstance(data_source, str) and not data_source.strip():
            raise PparError(file_path_error(data_source))
        data_source = Path(data_source)
        # Assert that the data file path exists.
        if not file_path_exists(data_source):
            raise PparError(file_path_error(data_source))
        # ``infer_schema=False`` preserves identity text such as leading zeroes.
        lf = pl.scan_csv(data_source, has_header=False, infer_schema=False)
        column0_name = list(lf.collect_schema().keys())[0]
        lf = lf.with_columns(pl.all().str.strip_chars())
        # Mapping identities must be validated before filtering so an invalid source
        # cannot disappear and silently become a self-mapping. Other two-column
        # sources retain the inexpensive lazy filter.
        df = (
            lf.collect()
            if identity_column_indices
            else lf.filter(pl.col(column0_name).is_in(needed_items)).collect()
        )
    elif isinstance(data_source, pl.DataFrame):
        df = data_source.clone()
    else:
        raise PparError("Data source must be a CSV path or Polars DataFrame.")

    # Assert that you have 2 columns.
    if len(df.columns) != 2:
        raise PparError(error_message)

    # Give the columns consistent names.
    df.columns = column_names

    # Cast to strings, remove surrounding whitespace, and filter on needed_items.
    if not is_file_source:
        # All identifiers need to be strings for classifications, mappings, performances, etc.
        for column_name in df.columns:
            if not isinstance(df.schema[column_name], pl.String):
                df = df.with_columns(df[column_name].cast(pl.String))
    df = normalize_text_columns(df, df.columns)
    # Filter on only the needed_items after any identity validation below.
    if identity_column_indices:
        for column_index in identity_column_indices:
            column_name = df.columns[column_index]
            invalid_rows = invalid_identity_rows(df, column_name)
            if invalid_rows.is_empty():
                continue
            affected_rows = invalid_rows.head(10).to_dicts()
            raise PparError(
                f"{source_description} identity field {column_name!r} must be "
                "non-null and nonblank after surrounding whitespace is removed. "
                f"Affected rows: {affected_rows}",
                context={
                    "boundary": source_description,
                    "field": column_name,
                    "invalid_rows": affected_rows,
                },
            )
        df = df.filter(pl.col(df.columns[0]).is_in(needed_items))
    elif not is_file_source:
        df = df.filter(pl.col(df.columns[0]).is_in(needed_items))

    return _deduplicate_identifier_pairs(df, source_description)


def _deduplicate_identifier_pairs(
    frame: pl.DataFrame,
    source_description: str,
) -> pl.DataFrame:
    """Return deterministic pairs after rejecting conflicting identifier values.

    Exact duplicate pairs are harmless and collapse to one row. An identifier
    associated with more than one value is ambiguous and therefore rejected rather
    than resolved according to physical row order.

    Args:
        frame: Two-column identifier/value pairs.
        source_description: Short source description used in validation errors.

    Returns:
        Unique pairs sorted by identifier and value.

    Raises:
        PparError: If one identifier is associated with conflicting values.
    """
    identifier_column, value_column = frame.columns
    conflicts = (
        frame.group_by(identifier_column)
        .agg(
            pl.col(value_column).unique().sort().alias(value_column),
            pl.col(value_column).n_unique().alias("_value_count"),
        )
        .filter(pl.col("_value_count") > 1)
        .drop("_value_count")
        .sort(identifier_column)
    )
    if not conflicts.is_empty():
        sample_rows = conflicts.head(10).to_dicts()
        raise PparError(
            f"{source_description} has conflicting values for the same identifier: "
            f"{sample_rows}",
            context={
                "boundary": source_description,
                "conflicts": sample_rows,
            },
        )
    return frame.unique().sort([identifier_column, value_column])


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
