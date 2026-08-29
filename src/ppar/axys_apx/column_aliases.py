"""Resolve explicit or exact-default Axys source column names."""

from __future__ import annotations

# Python imports
from collections.abc import Callable

# Project imports
from ppar.errors import PparError

ErrorMessage = Callable[[str], str]


def resolve_column(
    field_name: str,
    aliases: tuple[str, ...],
    available_columns: set[str],
    error_message: ErrorMessage,
    *,
    explicit_column: object | None = None,
    ambiguous_message: str,
) -> str | None:
    """Return an explicit column, exact default, or ``None`` when missing.

    Args:
        field_name: Logical field being resolved.
        aliases: Exact default CSV column names allowed when not configured.
        available_columns: CSV header columns available for matching.
        error_message: Callback adding Axys source context to validation
            details.
        explicit_column: Explicitly configured CSV column name, if present.
        ambiguous_message: Error message prefix used when multiple aliases
            match.

    Returns:
        The explicit or exact-default CSV column name, or ``None`` if no candidate
        matches and no explicit column was supplied.

    Raises:
        PparError: If more than one alias matches the available CSV columns.
    """
    if explicit_column is not None:
        return str(explicit_column) if explicit_column in available_columns else None

    matches = [alias for alias in aliases if alias in available_columns]
    if len(matches) > 1:
        raise PparError(
            error_message(f"{ambiguous_message} for {field_name!r}: {matches}."),
        )
    return matches[0] if matches else None
