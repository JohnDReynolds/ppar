"""Expose portable frequencies while retaining ppar's holiday-file adapter."""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from perfattr import Frequency

from ppar.errors import PparError

__all__ = ["Frequency"]


def load_holidays(data_source: str | Path | None) -> frozenset[dt.date]:
    """Load ppar's optional headerless holiday file.

    File access and the legacy diagnostics remain host responsibilities. The
    normalized dates are passed to ``perfattr`` for calendar-aware preparation.

    Args:
        data_source: Path to a headerless, single-column file containing strict
            ``YYYY-MM-DD`` dates, or ``None`` when no holidays are configured.

    Returns:
        Immutable set of configured holiday dates.

    Raises:
        PparError: If a configured file is missing, empty, malformed, or contains
            duplicate dates.
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
                    f"{path}, line {line_number} must contain exactly one date."
                )
            value = row[0].strip()
            try:
                holiday = dt.date.fromisoformat(value)
            except ValueError as error:
                raise PparError(
                    f"{path}, line {line_number} is not a YYYY-MM-DD date: "
                    f"{value!r}."
                ) from error
            if holiday.isoformat() != value:
                raise PparError(
                    f"{path}, line {line_number} is not a strict YYYY-MM-DD date: "
                    f"{value!r}."
                )
            if holiday in holidays:
                raise PparError(f"{path}, line {line_number} repeats {value}.")
            holidays.add(holiday)

    if not holidays:
        raise PparError(f"{path} contains no holiday dates.")
    return frozenset(holidays)


def periods_per_year(frequency: Frequency) -> int:
    """Return ppar's annual observation count for a fixed portable frequency.

    Args:
        frequency: Reporting frequency used by risk calculations.

    Returns:
        Twelve for monthly, four for quarterly, or one for yearly data.

    Raises:
        PparError: If the native periodic frequency has no fixed annual count.
    """
    counts = {
        Frequency.MONTHLY: 12,
        Frequency.QUARTERLY: 4,
        Frequency.YEARLY: 1,
    }
    try:
        return counts[frequency]
    except KeyError as error:
        raise PparError(f"Unhandled Frequency {frequency}") from error
