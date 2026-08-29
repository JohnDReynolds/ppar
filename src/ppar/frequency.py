"""Define reporting frequencies and calendar-aligned period helpers."""

# Python imports
import calendar
from collections.abc import Collection
import csv
import datetime as dt
from enum import Enum
from pathlib import Path
from typing import Sequence

# Project imports
from ppar.errors import PparError


class Frequency(Enum):
    """Enumeration of supported reporting frequencies.

    The enumeration values are used throughout the analytics pipeline to
    determine how performance data should be grouped and consolidated.

    Attributes:
        AS_OFTEN_AS_POSSIBLE: Use the native frequency of the supplied data
            without additional consolidation.
        MONTHLY: Consolidate data to calendar month-end periods.
        QUARTERLY: Consolidate data to calendar quarter-end periods.
        YEARLY: Consolidate data to calendar year-end periods.
    """

    AS_OFTEN_AS_POSSIBLE = "Periodic"  # As often as possible based on the frequency of the data.
    MONTHLY = "Monthly"  # Calendar months with conservative weekend-end support.
    QUARTERLY = "Quarterly"  # Calendar quarters.
    YEARLY = "Yearly"  # Calendar years.


def load_holidays(data_source: str | Path | None) -> frozenset[dt.date]:
    """Load an optional headerless file containing one holiday date per line.

    Args:
        data_source: Path to a headerless, single-column file containing strict
            ``YYYY-MM-DD`` dates, or ``None`` when no holidays are configured.

    Returns:
        Immutable set of configured holiday dates.

    Raises:
        PparError: If a configured file is missing, empty, contains extra
            columns, has an invalid date, or repeats a date.
    """
    if data_source is None:
        return frozenset()
    if isinstance(data_source, str) and not data_source.strip():
        raise PparError("path must not be blank.")

    path = Path(data_source)
    if not path.is_file():
        raise PparError(f"file does not exist: {path}.")

    holidays: set[dt.date] = set()
    with path.open("r", encoding="utf-8", newline="") as file:
        for line_number, row in enumerate(csv.reader(file), start=1):
            if not row or all(not value.strip() for value in row):
                continue
            if len(row) != 1:
                raise PparError(
                    f"{path}, line {line_number} must contain exactly one date.",
                )
            value = row[0].strip()
            try:
                holiday = dt.date.fromisoformat(value)
            except ValueError as error:
                raise PparError(
                    f"{path}, line {line_number} is not a YYYY-MM-DD date: "
                    f"{value!r}.",
                ) from error
            if holiday.isoformat() != value:
                raise PparError(
                    f"{path}, line {line_number} is not a strict YYYY-MM-DD "
                    f"date: {value!r}.",
                )
            if holiday in holidays:
                raise PparError(
                    f"{path}, line {line_number} repeats {value}.",
                )
            holidays.add(holiday)

    if not holidays:
        raise PparError(f"{path} contains no holiday dates.")
    return frozenset(holidays)


def date_matches_frequency(
    date: dt.date,
    frequency: Frequency,
    holidays: Collection[dt.date] = frozenset(),
) -> bool:
    """Determine whether a date can close a reporting-frequency bucket.

    Args:
        date: The date to evaluate.
        frequency: The reporting frequency to test against.
        holidays: Optional dates treated as nonbusiness days.

    Returns:
        ``True`` when ``date`` is either the literal calendar endpoint or the
        effective endpoint after rolling backward over weekends and configured
        holidays. A configured holiday is never accepted as the literal
        endpoint.

    Notes:
        Without ``holidays``, this is deliberately a last-weekday rule rather
        than a market-calendar rule.
    """
    if frequency == Frequency.AS_OFTEN_AS_POSSIBLE:
        return True

    bucket = frequency_bucket(date, frequency)
    calendar_endpoint = frequency_bucket_end(bucket, frequency)
    return (
        date == calendar_endpoint
        and calendar_endpoint not in holidays
    ) or date == frequency_bucket_effective_end(
        bucket,
        frequency,
        holidays,
    )


def frequency_bucket(date: dt.date, frequency: Frequency) -> int:
    """Return the ordered reporting bucket containing a date.

    Args:
        date: Date assigned to a reporting bucket.
        frequency: Frequency defining the bucket.

    Returns:
        Integer bucket identifier that increases by one for each consecutive
        reporting period.
    """
    if frequency == Frequency.MONTHLY:
        return date.year * 12 + date.month - 1
    if frequency == Frequency.QUARTERLY:
        return date.year * 4 + (date.month - 1) // 3
    if frequency == Frequency.YEARLY:
        return date.year
    return date.toordinal()


def frequency_bucket_end(bucket: int, frequency: Frequency) -> dt.date:
    """Return the nominal calendar endpoint for a reporting bucket.

    Args:
        bucket: Ordered bucket identifier returned by
            :func:`frequency_bucket`.
        frequency: Frequency defining the bucket.

    Returns:
        Calendar endpoint for the reporting bucket.
    """
    if frequency == Frequency.MONTHLY:
        year, zero_based_month = divmod(bucket, 12)
        month = zero_based_month + 1
        return dt.date(year, month, calendar.monthrange(year, month)[1])
    if frequency == Frequency.QUARTERLY:
        year, zero_based_quarter = divmod(bucket, 4)
        month = (zero_based_quarter + 1) * 3
        return dt.date(year, month, calendar.monthrange(year, month)[1])
    if frequency == Frequency.YEARLY:
        return dt.date(bucket, 12, 31)
    return dt.date.fromordinal(bucket)


def frequency_bucket_effective_end(
    bucket: int,
    frequency: Frequency,
    holidays: Collection[dt.date] = frozenset(),
) -> dt.date:
    """Return the effective business endpoint for a reporting bucket.

    Args:
        bucket: Ordered bucket identifier returned by
            :func:`frequency_bucket`.
        frequency: Frequency defining the bucket.
        holidays: Optional dates treated as nonbusiness days.

    Returns:
        Calendar endpoint rolled backward over Saturdays, Sundays, and
        configured holidays.
    """
    endpoint = frequency_bucket_end(bucket, frequency)
    while endpoint.weekday() >= 5 or endpoint in holidays:
        endpoint -= dt.timedelta(days=1)
    return endpoint


def frequency_bucket_label(bucket: int, frequency: Frequency) -> str:
    """Return a human-readable label for a reporting bucket.

    Args:
        bucket: Ordered bucket identifier returned by
            :func:`frequency_bucket`.
        frequency: Frequency defining the bucket.

    Returns:
        Calendar month, quarter, year, or date label.
    """
    if frequency == Frequency.MONTHLY:
        year, zero_based_month = divmod(bucket, 12)
        return f"{year:04d}-{zero_based_month + 1:02d}"
    if frequency == Frequency.QUARTERLY:
        year, zero_based_quarter = divmod(bucket, 4)
        return f"{year:04d}-Q{zero_based_quarter + 1}"
    if frequency == Frequency.YEARLY:
        return str(bucket)
    return frequency_bucket_end(bucket, frequency).isoformat()


def periods_per_year(frequency: Frequency) -> int:
    """Return the number of reporting periods in a calendar year.

    Args:
        frequency: The reporting frequency.

    Returns:
        The number of periods per calendar year for the specified frequency.

    Raises:
        PparError: If ``frequency`` is
            ``Frequency.AS_OFTEN_AS_POSSIBLE`` because a fixed annual period
            count cannot be determined for that frequency.
    """
    match frequency:
        case Frequency.MONTHLY:
            return 12
        case Frequency.QUARTERLY:
            return 4
        case Frequency.YEARLY:
            return 1
        case _:  # Frequency.AS_OFTEN_AS_POSSIBLE
            # This method requires a fixed reporting frequency.
            raise PparError(f"Unhandled Frequency {frequency}")


def validate_frequency_coverage(
    periods: Sequence[tuple[dt.date, dt.date]],
    frequency: Frequency,
) -> None:
    """Validate that fixed-frequency source data skips no reporting bucket.

    Args:
        periods: Ordered inclusive source ``(from_date, thru_date)`` periods.
        frequency: Frequency that the dates must follow.

    Raises:
        PparError: If no source period overlaps a required calendar month,
            quarter, or year between the first and last source periods.

    Notes:
        A source period need not end on a calendar boundary, and business-day
        data legitimately omits weekends and holidays. Coverage is therefore
        evaluated at the requested reporting frequency rather than by requiring
        adjacent calendar dates.
    """
    if frequency == Frequency.AS_OFTEN_AS_POSSIBLE or not periods:
        return

    covered_buckets: set[int] = set()
    for from_date, thru_date in periods:
        covered_buckets.update(
            range(
                frequency_bucket(from_date, frequency),
                frequency_bucket(thru_date, frequency) + 1,
            )
        )
    first_bucket = min(
        frequency_bucket(from_date, frequency) for from_date, _ in periods
    )
    last_bucket = max(
        frequency_bucket(thru_date, frequency) for _, thru_date in periods
    )
    missing_buckets = [
        bucket
        for bucket in range(first_bucket, last_bucket + 1)
        if bucket not in covered_buckets
    ]
    if missing_buckets:
        missing_labels = [
            frequency_bucket_label(bucket, frequency)
            for bucket in missing_buckets
        ]
        raise PparError(
            f"missing {frequency.value.lower()} coverage for {missing_labels}.",
            context={
                "frequency": frequency.value,
                "missing_periods": missing_labels,
            },
        )
