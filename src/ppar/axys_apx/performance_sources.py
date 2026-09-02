"""Load normalized Axys portfolio and security performance sources."""

from __future__ import annotations

# Python imports
from collections.abc import Sequence
from typing import Final, Literal

# Third-party imports
import polars as pl

# Project imports
from ppar.axys_apx.specification import _AxysSpecification, _ErrorMessage
from ppar.axys_apx.column_aliases import resolve_column
from ppar.axys_apx.date_ranges import AxysDateRange
from ppar.axys_apx.security_identity import (
    SecurityIdConstruction,
    security_id_construction,
    with_constructed_security_id,
)
from ppar.axys_apx.source_validation import (
    diagnostic_columns,
    normalize_financial_fields,
    sample_rows,
)
import ppar.schema as cols
from ppar.errors import PparError
import ppar.utilities as util

PerformanceSourceType = Literal[
    "portfolio_performance_columns",
    "security_performance_columns",
]
_PERFORMANCE_COLUMN_KEYS: Final[dict[PerformanceSourceType, dict[str, str]]] = {
    "portfolio_performance_columns": {
        cols.FROM_DATE: "from_date",
        cols.THRU_DATE: "thru_date",
        cols.PORTFOLIO_CODE: "portfolio_code",
        cols.PORTFOLIO_NAME: "portfolio_name",
        cols.PORTFOLIO_RETURN: "portfolio_return",
    },
    "security_performance_columns": {
        cols.FROM_DATE: "from_date",
        cols.CONTRIBUTION: "contribution",
        cols.THRU_DATE: "thru_date",
        cols.IDENTIFIER: "identifier",
        cols.PORTFOLIO_CODE: "portfolio_code",
        cols.RETURN: "security_return",
        cols.WEIGHT: "weight",
    },
}
_SHARED_AUDIT_COLUMN_KEYS: Final[dict[PerformanceSourceType, frozenset[str]]] = {
    "portfolio_performance_columns": frozenset(
        {
            "begin_market_value",
            "end_market_value",
            "flow",
            "income",
            "gain_loss",
            "period_id",
            "currency",
            "base_currency",
        }
    ),
    "security_performance_columns": frozenset(
        {
            "security_name",
            "security_symbol",
            "security_type",
            "begin_market_value",
            "end_market_value",
            "income",
            "gain_loss",
            "period_id",
            "currency",
            "base_currency",
        }
    ),
}
_PERFORMANCE_COLUMN_ALIASES: Final[dict[PerformanceSourceType, dict[str, tuple[str, ...]]]] = {
    "portfolio_performance_columns": {
        internal_column: (configuration_key,)
        for internal_column, configuration_key in _PERFORMANCE_COLUMN_KEYS[
            "portfolio_performance_columns"
        ].items()
    },
    "security_performance_columns": {
        internal_column: (configuration_key,)
        for internal_column, configuration_key in _PERFORMANCE_COLUMN_KEYS[
            "security_performance_columns"
        ].items()
    },
}
_PORTFOLIO_PERFORMANCE_REQUIRED_COLUMNS: Final[set[str]] = {
    cols.FROM_DATE,
    cols.THRU_DATE,
    cols.PORTFOLIO_CODE,
    cols.PORTFOLIO_NAME,
    cols.PORTFOLIO_RETURN,
}
_SECURITY_PERFORMANCE_REQUIRED_COLUMNS: Final[set[str]] = {
    cols.FROM_DATE,
    cols.CONTRIBUTION,
    cols.THRU_DATE,
    cols.IDENTIFIER,
    cols.PORTFOLIO_CODE,
    cols.RETURN,
    cols.WEIGHT,
}
_IDENTITY_COLUMNS: Final[set[str]] = {
    cols.IDENTIFIER,
    cols.PORTFOLIO_CODE,
    cols.PORTFOLIO_NAME,
}
_FINANCIAL_COLUMNS: Final[
    dict[PerformanceSourceType, tuple[tuple[str, bool], ...]]
] = {
    "portfolio_performance_columns": ((cols.PORTFOLIO_RETURN, True),),
    "security_performance_columns": (
        (cols.RETURN, True),
        (cols.WEIGHT, False),
        (cols.CONTRIBUTION, False),
    ),
}


def _collect_performance_source(lazy_frame: pl.LazyFrame) -> pl.DataFrame:
    """Materialize one projected and filtered performance-source query."""
    return lazy_frame.collect()


class AxysPerformanceSourceLoader:
    """Normalize Axys portfolio- and security-performance CSV sources.

    Attributes:
        _specification: Parsed Axys source configuration.
        _error_message: Callback used to add facade-level validation context.
        _date_range: Inclusive period ``thru_date`` bounds to retain.
    """

    def __init__(
        self,
        specification: _AxysSpecification,
        error_message: _ErrorMessage,
        date_range: AxysDateRange | None = None,
    ) -> None:
        """Initialize a performance source loader.

        Args:
            specification: Parsed Axys configuration.
            error_message: Callback that adds facade-level source context to
                validation messages.
            date_range: Optional inclusive period ``thru_date`` bounds to retain.
        """
        self._specification = specification
        self._error_message = error_message
        self._date_range = date_range or AxysDateRange()

    def load(
        self,
        file_path: util.PathLike,
        column_name_mappings_name: PerformanceSourceType,
        portfolio_code: str | Sequence[str] | None = None,
    ) -> pl.DataFrame:
        """Load a performance CSV with normalized columns and date filters.

        Args:
            file_path: Path to the portfolio- or security-performance CSV.
            column_name_mappings_name: Specification section defining the
                source-to-package column mapping.
            portfolio_code: Optional portfolio code or codes used to filter
                source rows.

        Returns:
            Normalized performance rows containing the columns required for the
            selected source kind.

        Raises:
            PparError: If the source path does not exist or required mapped
                columns are missing from the specification or CSV file, or a
                required textual value is invalid.
        """
        path = self._specification.resolve_path(file_path)
        if not util.file_path_exists(path):
            raise PparError(self._error_message(util.file_path_error(path)))

        required_columns = (
            _PORTFOLIO_PERFORMANCE_REQUIRED_COLUMNS
            if column_name_mappings_name == "portfolio_performance_columns"
            else _SECURITY_PERFORMANCE_REQUIRED_COLUMNS
        )
        dataset_name = (
            "security_performance"
            if column_name_mappings_name == "security_performance_columns"
            else "portfolio_performance"
        )
        construction = security_id_construction(
            self._specification.values,
            dataset_name,
            self._error_message,
        )
        mapped_required_columns = set(required_columns)
        if construction is not None:
            mapped_required_columns.remove(cols.IDENTIFIER)
        csv_to_internal_mappings = self._csv_to_internal_mappings(
            path,
            column_name_mappings_name,
            mapped_required_columns,
        )
        schema_overrides = self._schema_overrides(
            csv_to_internal_mappings,
            construction,
        )

        selected_columns = set(mapped_required_columns)
        if construction is not None:
            selected_columns.update(construction.source_columns)
        text_columns = selected_columns & _IDENTITY_COLUMNS
        if construction is not None:
            text_columns.update(construction.source_columns)
        lazy_frame = (
            pl.scan_csv(
                path,
                schema_overrides=schema_overrides,
            )
            .rename(csv_to_internal_mappings)
            .select(selected_columns)
            .with_columns(
                pl.col(cols.FROM_DATE).str.strptime(pl.Date, "%Y-%m-%d", strict=True),
                pl.col(cols.THRU_DATE).str.strptime(pl.Date, "%Y-%m-%d", strict=True),
            )
        )
        if isinstance(portfolio_code, str):
            lazy_frame = lazy_frame.filter(
                pl.col(cols.PORTFOLIO_CODE).str.strip_chars() == portfolio_code
            )
        elif portfolio_code is not None:
            lazy_frame = lazy_frame.filter(
                pl.col(cols.PORTFOLIO_CODE).str.strip_chars().is_in(portfolio_code)
            )
        lazy_frame = lazy_frame.with_columns(
            pl.col(column_name).str.strip_chars()
            for column_name in sorted(text_columns)
        )
        frame = _collect_performance_source(
            self._date_range.filter_performance(lazy_frame)
        )
        if construction is not None:
            frame = with_constructed_security_id(
                frame,
                construction,
                output_column=cols.IDENTIFIER,
                dataset_name=dataset_name,
                source_path=path,
                error_message=self._error_message,
            )
        frame = self._validate_text_columns(frame, dataset_name, path)
        frame = normalize_financial_fields(
            frame,
            dataset_name,
            _FINANCIAL_COLUMNS[column_name_mappings_name],
            self._error_message,
            source_path=path,
        )
        return frame.select(required_columns)

    @staticmethod
    def _schema_overrides(
        csv_to_internal_mappings: dict[str, str],
        construction: SecurityIdConstruction | None,
    ) -> dict[str, type[pl.DataType]]:
        """Return source-column types that preserve textual identities.

        Args:
            csv_to_internal_mappings: Source columns mapped to normalized
                performance columns.
            construction: Optional composite security-identifier definition.

        Returns:
            Partial Polars CSV schema keyed by source column.
        """
        overrides = dict(construction.schema_overrides) if construction else {}
        overrides.update(
            {
                source_column: pl.String
                for source_column, internal_column in csv_to_internal_mappings.items()
                if internal_column in _IDENTITY_COLUMNS
            }
        )
        return overrides

    def _validate_text_columns(
        self,
        frame: pl.DataFrame,
        dataset_name: str,
        path: util.PathLike,
    ) -> pl.DataFrame:
        """Reject null or blank normalized identities and portfolio display names.

        Args:
            frame: Selected and normalized source rows.
            dataset_name: Source kind used in error details.
            path: Source CSV path used in error details.

        Returns:
            The unchanged validated frame.

        Raises:
            PparError: If a required textual value is null or blank after trimming.
        """
        text_columns = [cols.PORTFOLIO_CODE]
        text_columns.append(
            cols.PORTFOLIO_NAME
            if dataset_name == "portfolio_performance"
            else cols.IDENTIFIER
        )
        for column_name in text_columns:
            invalid_rows = util.invalid_identity_rows(frame, column_name)
            if invalid_rows.is_empty():
                continue
            affected_rows = sample_rows(
                invalid_rows,
                diagnostic_columns(invalid_rows, column_name),
            )
            field_kind = (
                "Display-name"
                if column_name == cols.PORTFOLIO_NAME
                else "Identity"
            )
            raise PparError(
                self._error_message(
                    f"{field_kind} field {column_name!r} in {str(path)!r} for "
                    f"{dataset_name} must be non-null and nonblank after "
                    f"surrounding whitespace is removed. Affected rows: "
                    f"{affected_rows}"
                )
            )
        return frame

    def _csv_to_internal_mappings(
        self,
        path: util.PathLike,
        column_name_mappings_name: PerformanceSourceType,
        required_columns: set[str],
    ) -> dict[str, str]:
        """Return CSV-to-internal column mappings for a performance source.

        Args:
            path: Source CSV path used for validation context and header
                inspection.
            column_name_mappings_name: Specification section defining the
                source-to-package column mapping.
            required_columns: Internal columns required for the source kind.

        Returns:
            Mapping from source CSV column names to internal package column
            names.

        Raises:
            PparError: If required mapped columns are missing from either the
                specification or the CSV header.
        """
        file_name = column_name_mappings_name.removesuffix("_columns")
        configured_column_mappings = self._specification.file_columns(file_name)
        column_mappings = self._normalize_column_mapping_keys(
            configured_column_mappings,
            column_name_mappings_name,
        )
        header = pl.read_csv(path, n_rows=0)
        available_columns = set(header.columns)
        missing_columns: list[str] = []
        csv_to_internal_mappings: dict[str, str] = {}

        for internal_column in required_columns:
            source_column = self._resolve_source_column(
                path,
                column_name_mappings_name,
                internal_column,
                available_columns,
                column_mappings.get(internal_column),
            )
            if source_column is None:
                explicit_column = column_mappings.get(internal_column)
                missing_columns.append(
                    (
                        f"{internal_column!r} configured as {explicit_column!r}"
                        if explicit_column is not None
                        else self._missing_column_message(
                            column_name_mappings_name,
                            internal_column,
                        )
                    )
                )
                continue
            csv_to_internal_mappings[source_column] = internal_column

        if missing_columns:
            raise PparError(
                self._error_message(
                    f"Missing {missing_columns} in {str(path)!r}.  |  "
                    f"CSV columns available are: {sorted(available_columns)}"
                ),
            )

        return csv_to_internal_mappings

    def _normalize_column_mapping_keys(
        self,
        column_mappings: object,
        column_name_mappings_name: PerformanceSourceType,
    ) -> dict[str, str]:
        """Return configured source columns keyed by internal package column.

        Args:
            column_mappings: Raw source-column mapping section.
            column_name_mappings_name: Specification section being normalized.

        Returns:
            Mapping from internal package column names to configured CSV
            column names.
        """
        canonical_keys = _PERFORMANCE_COLUMN_KEYS[column_name_mappings_name]
        key_to_internal_column = {
            configuration_key: internal_column
            for internal_column, configuration_key in canonical_keys.items()
        }
        if not isinstance(column_mappings, dict):
            raise PparError(
                self._error_message(
                    f"files.{column_name_mappings_name.removesuffix('_columns')}."
                    "columns must be a mapping."
                ),
            )
        supported_keys = set(key_to_internal_column) | set(
            _SHARED_AUDIT_COLUMN_KEYS[column_name_mappings_name]
        )
        unsupported_keys = sorted(
            str(key) for key in column_mappings if key not in supported_keys
        )
        if unsupported_keys:
            raise PparError(
                self._error_message(
                    "files."
                    f"{column_name_mappings_name.removesuffix('_columns')}.columns "
                    "has unsupported keys: "
                    + ", ".join(unsupported_keys)
                    + "."
                ),
            )
        invalid_values = sorted(
            str(key)
            for key, value in column_mappings.items()
            if not isinstance(value, str) or not value.strip()
        )
        if invalid_values:
            raise PparError(
                self._error_message(
                    "files."
                    f"{column_name_mappings_name.removesuffix('_columns')}.columns "
                    "values must be non-empty strings: "
                    + ", ".join(invalid_values)
                    + "."
                ),
            )
        return {
            key_to_internal_column[key]: value
            for key, value in column_mappings.items()
            if key in key_to_internal_column
        }

    def _resolve_source_column(
        self,
        path: util.PathLike,
        column_name_mappings_name: PerformanceSourceType,
        internal_column: str,
        available_columns: set[str],
        explicit_column: str | None,
    ) -> str | None:
        """Resolve a configured source column or its exact normalized name.

        Args:
            path: Source CSV path used for error context.
            column_name_mappings_name: Specification section being loaded.
            internal_column: Internal package column to resolve.
            available_columns: CSV header columns.
            explicit_column: Explicit source column from the settings, if any.

        Returns:
            The explicit or exact-default CSV column, or ``None`` when not found.

        Raises:
            PparError: If more than one candidate exists for the same internal
                column.
        """
        configuration_key = _PERFORMANCE_COLUMN_KEYS[column_name_mappings_name][
            internal_column
        ]
        aliases = _PERFORMANCE_COLUMN_ALIASES[column_name_mappings_name][internal_column]
        resolved_column = resolve_column(
            internal_column,
            aliases,
            available_columns,
            self._error_message,
            explicit_column=explicit_column,
            ambiguous_message=(
                f"Ambiguous source columns in {str(path)!r}. "
                f"Configure {configuration_key!r} explicitly"
            ),
        )
        return resolved_column

    @staticmethod
    def _missing_column_message(
        column_name_mappings_name: PerformanceSourceType,
        internal_column: str,
    ) -> str:
        """Return an error fragment for a missing performance source column."""
        configuration_key = _PERFORMANCE_COLUMN_KEYS[column_name_mappings_name][
            internal_column
        ]
        return f"{configuration_key!r} for {internal_column!r}"
