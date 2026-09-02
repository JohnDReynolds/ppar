"""Load Axys/APX classification sources from the configured security master."""

from __future__ import annotations

# Python imports
from typing import Any, Final, Literal, cast

# Third-party imports
import polars as pl

# Project imports
from ppar.axys_apx.column_aliases import resolve_column
from ppar.axys_apx.security_identity import (
    SecurityIdConstruction,
    security_id_construction,
    with_constructed_security_id,
)
from ppar.axys_apx.source_validation import sample_rows
from ppar.axys_apx.specification import _AxysSpecification, _ErrorMessage
from ppar.errors import PparError
import ppar.schema as cols
import ppar.utilities as util

_SourceType = Literal["classification", "mapping"]
_SECURITY_MASTER_FIELDS_REQUIRED: Final[set[str]] = {
    "identifier_column",
    "name_column",
}
_SECURITY_MASTER_COLUMN_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "identifier_column": ("security_id",),
    "name_column": ("security_name",),
}
_SECURITY_MASTER_CONFIG_KEYS: Final[dict[str, str]] = {
    "identifier_column": "identifier_column",
    "name_column": "security_name",
}
_SECURITY_MASTER_IDENTITY_KEYS: Final[frozenset[str]] = frozenset(
    {"security_symbol", "security_type"}
)
_SECURITY_MASTER_FILE_KEY: Final[str] = "security_master"
_SECURITY_CLASSIFICATION_NAME: Final[str] = "Security"
_FILTER_TO_SECURITY_IDS: Final[str] = "_filter_to_security_ids"
_SOURCE_FILE_PATH: Final[str] = "_source_file_path"
_SECURITY_ID_CONSTRUCTION: Final[str] = "_security_id_construction"
_CONSTRUCTED_SECURITY_ID_COLUMN: Final[str] = "__ppar_constructed_security_id"


class AxysClassificationSourceLoader:
    """Normalize security and security-master classification sources.

    Attributes:
        _specification: Validated focused Axys/APX source configuration.
        _error_message: Callback used to add facade-level source context.
    """

    def __init__(
        self,
        specification: _AxysSpecification,
        error_message: _ErrorMessage,
    ) -> None:
        """Initialize a security-master source loader.

        Args:
            specification: Validated focused Axys/APX source configuration.
            error_message: Callback that adds facade-level source context to
                validation messages.
        """
        self._specification = specification
        self._error_message = error_message

    def load(
        self,
        source_type: _SourceType,
        source_name: str | None,
        unique_security_ids: list[str],
    ) -> pl.DataFrame:
        """Load one normalized classification or security-to-group mapping.

        Args:
            source_type: Whether to produce classification items or a mapping.
            source_name: ``Security`` or a configured security-master mapping name.
            unique_security_ids: Security identifiers retained in portfolio output.

        Returns:
            Two-column DataFrame containing normalized identifier/name pairs.

        Raises:
            PparError: If the source name, security master, or configured columns are
                invalid.
        """
        if not source_name:
            return pl.DataFrame()

        source = self._effective_source_definition(source_type, source_name)
        file_path = self._specification.resolve_path(source[_SOURCE_FILE_PATH])
        if not util.file_path_exists(file_path):
            raise PparError(self._error_message(util.file_path_error(file_path)))

        construction = cast(
            SecurityIdConstruction | None,
            source.get(_SECURITY_ID_CONSTRUCTION),
        )
        schema_overrides = self._schema_overrides(source, construction)
        if construction is None:
            lazy_frame = pl.scan_csv(file_path, schema_overrides=schema_overrides)
        else:
            source_frame = with_constructed_security_id(
                pl.read_csv(file_path, schema_overrides=schema_overrides),
                construction,
                output_column=_CONSTRUCTED_SECURITY_ID_COLUMN,
                dataset_name="security_master",
                source_path=file_path,
                error_message=self._error_message,
            )
            lazy_frame = source_frame.lazy()
        self._validate_csv_columns(source_type, source_name, source, lazy_frame)

        text_columns = {
            cast(str, source["identifier_column"]),
            cast(str, source["name_column"]),
        }
        source_lazy_frame = lazy_frame
        if source[_FILTER_TO_SECURITY_IDS]:
            lazy_frame = lazy_frame.filter(
                pl.col(source["identifier_column"]).is_in(unique_security_ids)
            )
        source_frame = lazy_frame.collect()
        if source[_FILTER_TO_SECURITY_IDS]:
            identifier_column = cast(str, source["identifier_column"])
            matched_ids = set(source_frame[identifier_column].unique().to_list())
            if not set(unique_security_ids).issubset(matched_ids):
                # Preserve predicate pushdown for exact identifiers. Only missing
                # matches require a normalized fallback scan of the source.
                normalized_ids = source_lazy_frame.with_columns(
                    pl.col(identifier_column).str.strip_chars()
                ).filter(pl.col(identifier_column).is_in(unique_security_ids))
                source_frame = normalized_ids.collect()
        source_frame = util.normalize_text_columns(source_frame, sorted(text_columns))
        self._validate_identity_columns(
            source_frame,
            source_type,
            source_name,
            source,
            file_path,
        )
        normalized = source_frame.select(
            pl.col(source["identifier_column"]).alias(cols.IDENTIFIER),
            pl.col(source["name_column"]).alias(cols.NAME),
        )
        return util._deduplicate_identifier_pairs(  # pylint: disable=protected-access
            normalized,
            f"Axys {source_type} {source_name!r} from {str(file_path)!r}",
        )

    def _effective_source_definition(
        self,
        source_type: _SourceType,
        source_name: str,
    ) -> dict[str, Any]:
        """Return security-master fields for one supported source request.

        Args:
            source_type: Whether to produce classification items or a mapping.
            source_name: ``Security`` or a configured mapping name.

        Returns:
            Internal source definition containing its path and two selected columns.

        Raises:
            PparError: If ``source_name`` is not supported.
        """
        if source_type == "classification" and source_name == _SECURITY_CLASSIFICATION_NAME:
            security_master = self._security_master_definition(source_name)
            return {
                _SOURCE_FILE_PATH: security_master[_SOURCE_FILE_PATH],
                "identifier_column": security_master["identifier_column"],
                "name_column": security_master["name_column"],
                _FILTER_TO_SECURITY_IDS: True,
                **self._security_id_construction_fields(security_master),
            }

        mapping = self._specification.mappings.get(source_name)
        if mapping is None:
            raise PparError(
                self._error_message(f"Unknown {source_type} {source_name!r}"),
            )
        security_master = self._security_master_definition(source_name)
        if source_type == "classification":
            return {
                _SOURCE_FILE_PATH: security_master[_SOURCE_FILE_PATH],
                "identifier_column": mapping["classification_column"],
                "name_column": mapping["display_name_column"],
                _FILTER_TO_SECURITY_IDS: False,
            }
        return {
            _SOURCE_FILE_PATH: security_master[_SOURCE_FILE_PATH],
            "identifier_column": security_master["identifier_column"],
            "name_column": mapping["classification_column"],
            _FILTER_TO_SECURITY_IDS: True,
            **self._security_id_construction_fields(security_master),
        }

    @staticmethod
    def _schema_overrides(
        source: dict[str, Any],
        construction: SecurityIdConstruction | None,
    ) -> dict[str, type[pl.DataType]]:
        """Return CSV types that preserve identifiers and names as text."""
        overrides = dict(construction.schema_overrides) if construction else {}
        for field_name in ("identifier_column", "name_column"):
            source_column = source[field_name]
            if source_column != _CONSTRUCTED_SECURITY_ID_COLUMN:
                overrides[source_column] = pl.String
        return overrides

    def _validate_csv_columns(
        self,
        source_type: _SourceType,
        source_name: str,
        source: dict[str, Any],
        lazy_frame: pl.LazyFrame,
    ) -> None:
        """Reject configured source columns absent from the security master."""
        required = {source["identifier_column"], source["name_column"]}
        nonexistent = required - set(lazy_frame.collect_schema().names())
        if nonexistent:
            raise PparError(
                self._error_message(
                    f"Nonexistent column names for {source_type} {source_name!r}: "
                    f"{nonexistent}"
                ),
            )

    def _validate_identity_columns(
        self,
        frame: pl.DataFrame,
        source_type: _SourceType,
        source_name: str,
        source: dict[str, Any],
        file_path: util.PathLike,
    ) -> None:
        """Reject null or blank identities in normalized supporting sources."""
        field_names = ["identifier_column", "name_column"]
        for field_name in field_names:
            column_name = cast(str, source[field_name])
            invalid_rows = util.invalid_identity_rows(frame, column_name)
            if invalid_rows.is_empty():
                continue
            raise PparError(
                self._error_message(
                    f"Identity field {column_name!r} in {str(file_path)!r} for "
                    f"{source_type} {source_name!r} must be non-null and nonblank "
                    "after surrounding whitespace is removed. "
                    f"Affected rows: {sample_rows(invalid_rows, [column_name])}"
                )
            )

    def _security_master_definition(self, source_name: str) -> dict[str, Any]:
        """Return validated security-master path, identity, and name columns."""
        security_master_path = self._specification.file_path(
            _SECURITY_MASTER_FILE_KEY
        )
        configured_columns = self._specification.file_columns(
            _SECURITY_MASTER_FILE_KEY
        )
        supported_keys = (
            set(_SECURITY_MASTER_CONFIG_KEYS.values())
            | set(_SECURITY_MASTER_IDENTITY_KEYS)
        )
        unsupported = sorted(
            str(key) for key in configured_columns if key not in supported_keys
        )
        if unsupported:
            raise PparError(
                self._error_message(
                    "files.security_master.columns has unsupported keys: "
                    + ", ".join(unsupported)
                    + "."
                ),
            )
        construction = security_id_construction(
            self._specification.values,
            "security_master",
            self._error_message,
            file_name=_SECURITY_MASTER_FILE_KEY,
        )
        resolved_columns = self._resolve_security_master_columns(
            source_name,
            security_master_path,
            configured_columns,
            composite_identifier=construction is not None,
        )
        definition: dict[str, Any] = {
            _SOURCE_FILE_PATH: security_master_path,
            "identifier_column": resolved_columns["identifier_column"],
            "name_column": resolved_columns["name_column"],
        }
        if construction is not None:
            definition[_SECURITY_ID_CONSTRUCTION] = construction
        return definition

    def _resolve_security_master_columns(
        self,
        source_name: str,
        security_master_path: util.PathLike,
        configured_columns: dict[str, Any],
        *,
        composite_identifier: bool,
    ) -> dict[str, str]:
        """Resolve required security-master columns from explicit or exact names."""
        path = self._specification.resolve_path(security_master_path)
        if not util.file_path_exists(path):
            raise PparError(self._error_message(util.file_path_error(path)))

        available_columns = set(pl.read_csv(path, n_rows=0).columns)
        resolved_columns: dict[str, str] = {}
        missing_fields: list[str] = []
        required_fields = set(_SECURITY_MASTER_FIELDS_REQUIRED)
        if composite_identifier:
            required_fields.remove("identifier_column")
            resolved_columns["identifier_column"] = _CONSTRUCTED_SECURITY_ID_COLUMN
        for field_name in required_fields:
            config_key = _SECURITY_MASTER_CONFIG_KEYS[field_name]
            source_column = resolve_column(
                field_name,
                _SECURITY_MASTER_COLUMN_ALIASES[field_name],
                available_columns,
                self._error_message,
                explicit_column=configured_columns.get(config_key),
                ambiguous_message=(
                    "Ambiguous security master column. "
                    f"Configure {config_key!r} explicitly. "
                    f"Source requiring security master: {source_name!r}"
                ),
            )
            if source_column is None or source_column not in available_columns:
                configured_as = (
                    f" configured as {source_column!r}" if source_column else ""
                )
                missing_fields.append(f"{config_key!r}{configured_as}")
            else:
                resolved_columns[field_name] = source_column

        if missing_fields:
            raise PparError(
                self._error_message(
                    f"Missing {missing_fields} for files.security_master.columns. "
                    f"CSV columns available are: {sorted(available_columns)}. "
                    f"Source requiring security master: {source_name!r}"
                ),
            )
        return resolved_columns

    @staticmethod
    def _security_id_construction_fields(
        security_master: dict[str, Any],
    ) -> dict[str, SecurityIdConstruction]:
        """Return internal composite-ID settings inherited from the master."""
        construction = security_master.get(_SECURITY_ID_CONSTRUCTION)
        if construction is None:
            return {}
        return {_SECURITY_ID_CONSTRUCTION: cast(SecurityIdConstruction, construction)}
