"""Load normalized Axys classification and mapping sources."""

from __future__ import annotations

# Python imports
from collections.abc import Mapping
from typing import Any, Final, cast

# Third-party imports
import polars as pl

# Project imports
from ppar.axys_apx.specification import AxysSpecification, ErrorMessage, SourceType
from ppar.axys_apx.column_aliases import resolve_column
from ppar.axys_apx.security_identity import (
    SecurityIdConstruction,
    security_id_construction,
    with_constructed_security_id,
)
import ppar.schema as cols
from ppar.errors import PparError
import ppar.utilities as util

_CLASSIFICATION_FIELDS_ALLOWED: Final[set[str]] = {
    "display_name",
    "file_path",
    "identifier_column",
    "name_column",
    "is_security_master",
    "filter_column",
    "filter_value",
    "mapping",
}
_MAPPING_FIELDS_ALLOWED: Final[set[str]] = {
    "classification_column",
    "display_name_column",
}
_FILE_BACKED_CLASSIFICATION_FIELDS_REQUIRED: Final[set[str]] = {
    "file_path",
    "identifier_column",
    "name_column",
}
_CLASSIFICATION_MAPPING_COLUMN_NAMES: Final[set[str]] = {
    "identifier_column",
    "name_column",
    "filter_column",
}
_MAPPING_FIELDS_REQUIRED: Final[set[str]] = {"classification_column"}
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
_NORMALIZED_SOURCE_COLUMNS: Final[tuple[str, str]] = (cols.IDENTIFIER, cols.NAME)


class AxysClassificationSourceLoader:
    """Normalize Axys classification and mapping CSV sources.

    Attributes:
        _specification: Parsed Axys source configuration.
        _error_message: Callback used to add facade-level validation context.
    """

    def __init__(
        self,
        specification: AxysSpecification,
        error_message: ErrorMessage,
        source_path_overrides: Mapping[str, util.PathLike] | None = None,
    ) -> None:
        """Initialize a classification/mapping source loader.

        Args:
            specification: Parsed Axys configuration.
            error_message: Callback that adds facade-level source context to
                validation messages.
            source_path_overrides: Optional source file paths keyed by
                configured classification source name.

        Raises:
            PparError: If a source path override references an unknown
                classification source.
        """
        self._specification = specification
        self._error_message = error_message
        self._source_path_overrides = dict(source_path_overrides or {})
        self._validate_source_path_overrides()

    def load(
        self,
        source_type: SourceType,
        source_name: str | None,
        unique_security_ids: list[str],
    ) -> pl.DataFrame:
        """Load a normalized classification or mapping source.

        Args:
            source_type: Kind of supporting source to load.
            source_name: Configured source name, or ``None`` to return an empty
                DataFrame.
            unique_security_ids: Security identifiers retained in loaded
                portfolio output.

        Returns:
            Two-column DataFrame containing normalized identifier/name pairs.

        Raises:
            PparError: If the source is unknown, its specification is invalid,
                its CSV does not exist, or its declared columns do not exist.
        """
        if not source_name:
            return pl.DataFrame()

        data_source = self._source_definition(source_type, source_name)
        if data_source is None:
            raise PparError(
                self._error_message(f"Unknown {source_type} {source_name!r}"),
            )

        self._validate_source_definition(source_type, source_name, data_source)
        effective_source = self._effective_source_definition(
            source_type,
            source_name,
            data_source,
        )

        file_path = self._source_file_path(source_type, source_name, effective_source)
        if not util.file_path_exists(file_path):
            raise PparError(self._error_message(util.file_path_error(file_path)))

        construction = cast(
            SecurityIdConstruction | None,
            effective_source.get(_SECURITY_ID_CONSTRUCTION),
        )
        if construction is None:
            lazy_frame = pl.scan_csv(file_path)
        else:
            source_frame = pl.read_csv(
                file_path,
                schema_overrides=construction.schema_overrides,
            )
            source_frame = with_constructed_security_id(
                source_frame,
                construction,
                output_column=_CONSTRUCTED_SECURITY_ID_COLUMN,
                dataset_name="security_master",
                source_path=file_path,
                error_message=self._error_message,
            )
            lazy_frame = source_frame.lazy()
        self._validate_csv_columns(source_type, source_name, effective_source, lazy_frame)

        if effective_source.get(_FILTER_TO_SECURITY_IDS, False):
            lazy_frame = lazy_frame.filter(
                pl.col(effective_source["identifier_column"]).is_in(unique_security_ids)
            )
        if {"filter_column", "filter_value"}.issubset(effective_source):
            lazy_frame = lazy_frame.filter(
                pl.col(effective_source["filter_column"])
                == effective_source["filter_value"]
            )

        rename_mappings = {
            effective_source["identifier_column"]: cols.IDENTIFIER,
            effective_source["name_column"]: cols.NAME,
        }
        return (
            lazy_frame.collect()
            .rename(rename_mappings)
            .select(_NORMALIZED_SOURCE_COLUMNS)
            .unique(subset=[cols.IDENTIFIER], keep="any")
        )

    def _source_definition(
        self,
        source_type: SourceType,
        source_name: str,
    ) -> dict[str, Any] | None:
        """Return an explicit source definition or synthesized classification.

        Args:
            source_type: Kind of supporting source being loaded.
            source_name: Configured source name being loaded.

        Returns:
            Source definition from the Axys specification, a synthesized
            mapping-backed classification definition, or ``None`` when the
            source is unknown.
        """
        data_sources = (
            self._specification.classifications
            if source_type == "classification"
            else self._specification.mappings
        )
        data_source = data_sources.get(source_name)
        if data_source is not None:
            return data_source

        if source_type == "classification":
            if source_name == _SECURITY_CLASSIFICATION_NAME:
                return {"is_security_master": True}
            mapping_source = self._specification.mappings.get(source_name)
            if (
                isinstance(mapping_source, dict)
                and "display_name_column" in mapping_source
            ):
                return {
                    "mapping": source_name,
                    "name_column": mapping_source["display_name_column"],
                }
            if isinstance(mapping_source, dict):
                raise PparError(
                    self._error_message(
                        f"Mapping {source_name!r} cannot be used as a classification "
                        "without display_name_column."
                    ),
                )
        return None

    def _validate_csv_columns(
        self,
        source_type: SourceType,
        source_name: str,
        data_source: dict[str, Any],
        lazy_frame: pl.LazyFrame,
    ) -> None:
        """Validate that configured source columns exist in the CSV.

        Args:
            source_type: Kind of supporting source being loaded.
            source_name: Configured source name being loaded.
            data_source: Source definition from the Axys specification.
            lazy_frame: Lazy CSV scan used to inspect available columns.

        Raises:
            PparError: If any configured CSV column name does not exist.
        """
        specified_column_names = {
            data_source[field]
            for field in _CLASSIFICATION_MAPPING_COLUMN_NAMES
            if field in data_source
        }
        nonexistent_column_names = specified_column_names - set(
            lazy_frame.collect_schema().names()
        )
        if nonexistent_column_names:
            raise PparError(
                self._error_message(
                    f"Nonexistent column names for {source_type} {source_name!r}: "
                    f"{nonexistent_column_names}"
                ),
            )

    def _validate_source_definition(
        self,
        source_type: SourceType,
        source_name: str,
        data_source: dict[str, Any],
    ) -> None:
        """Validate a classification or mapping source specification.

        Args:
            source_type: Kind of supporting source being loaded.
            source_name: Configured source name being loaded.
            data_source: Source definition from the Axys specification.

        Raises:
            PparError: If required fields are missing, unknown fields are
                present, ``is_security_master`` is not boolean, required
                source fields are missing, or a non-security-master
                classification does not identify a configured mapping.
        """
        allowed_fields = (
            _CLASSIFICATION_FIELDS_ALLOWED
            if source_type == "classification"
            else _MAPPING_FIELDS_ALLOWED
        )
        unknown_fields = set(data_source) - allowed_fields
        if unknown_fields:
            raise PparError(
                self._error_message(
                    f"Unknown fields for {source_type} {source_name!r}: {unknown_fields}"
                ),
            )

        is_security_master = data_source.get("is_security_master", False)
        if not isinstance(is_security_master, bool):
            raise PparError(
                self._error_message(
                    f"Invalid is_security_master value for {source_type} {source_name!r}: "
                    f"{is_security_master!r} must be a boolean."
                ),
            )

        if source_type == "mapping":
            self._validate_mapping_definition(source_name, data_source)
            return

        if is_security_master:
            return

        mapping_name = data_source.get("mapping")
        self._validate_classification_mapping(source_name, mapping_name)
        self._validate_classification_source_fields(source_name, data_source)

    def _validate_mapping_definition(
        self,
        source_name: str,
        data_source: dict[str, Any],
    ) -> None:
        """Validate a mapping definition that points into the security master.

        Args:
            source_name: Configured mapping source name.
            data_source: Mapping definition from the Axys specification.

        Raises:
            PparError: If the required ``classification_column`` field is
                missing.
        """
        missing_fields = _MAPPING_FIELDS_REQUIRED - set(data_source)
        if missing_fields:
            raise PparError(
                self._error_message(
                    f"Missing fields for mapping {source_name!r}: {missing_fields}"
                ),
            )

    def _validate_classification_source_fields(
        self,
        source_name: str,
        data_source: dict[str, Any],
    ) -> None:
        """Validate explicit or security-master-backed classification fields.

        Args:
            source_name: Configured classification source name.
            data_source: Classification definition from the Axys specification.

        Raises:
            PparError: If the classification has neither a complete explicit
                source definition nor a security-master-backed definition.
        """
        has_file_path = "file_path" in data_source
        if has_file_path:
            missing_fields = _FILE_BACKED_CLASSIFICATION_FIELDS_REQUIRED - set(
                data_source
            )
            if missing_fields:
                raise PparError(
                    self._error_message(
                        f"Missing fields for classification {source_name!r}: "
                        f"{missing_fields}"
                    ),
                )
            return

        if "identifier_column" in data_source:
            raise PparError(
                self._error_message(
                    f"Missing fields for classification {source_name!r}: "
                    "{'file_path'}"
                ),
            )

        missing_fields = {"name_column"} - set(data_source)
        if missing_fields:
            raise PparError(
                self._error_message(
                    f"Missing fields for classification {source_name!r}: "
                    f"{missing_fields}"
                ),
            )

    def _validate_classification_mapping(
        self,
        source_name: str,
        mapping_name: object,
    ) -> None:
        """Validate a non-security-master classification mapping reference.

        Args:
            source_name: Configured classification source name.
            mapping_name: Mapping reference from the classification source
                definition.

        Raises:
            PparError: If the classification does not reference a configured
                mapping.
        """
        if not isinstance(mapping_name, str) or not mapping_name:
            raise PparError(
                self._error_message(
                    f"Missing mapping for classification {source_name!r}. "
                    "Non-security-master classifications must specify a mapping."
                ),
            )
        if mapping_name not in self._specification.mappings:
            raise PparError(
                self._error_message(
                    f"Unknown mapping {mapping_name!r} for classification {source_name!r}"
                ),
            )

    def _source_file_path(
        self,
        source_type: SourceType,
        source_name: str,
        data_source: dict[str, Any],
    ) -> util.PathLike:
        """Return the override or configured default path for a source.

        Args:
            source_type: Kind of supporting source being loaded.
            source_name: Configured classification or mapping source name.
            data_source: Source definition from the Axys specification.

        Returns:
            Resolved source file path.
        """
        override_path = (
            self._source_path_overrides.get(source_name)
            if source_type == "classification"
            else None
        )
        file_path = override_path if override_path is not None else data_source[_SOURCE_FILE_PATH]
        return self._specification.resolve_path(file_path)

    def _effective_source_definition(
        self,
        source_type: SourceType,
        source_name: str,
        data_source: dict[str, Any],
    ) -> dict[str, Any]:
        """Return inherited path and column settings for a loadable source.

        Args:
            source_type: Kind of supporting source being loaded.
            source_name: Configured source name being loaded.
            data_source: Raw source definition from the Axys specification.

        Returns:
            Source definition with explicit file path, identifier column, name
            column, and security-ID filtering behavior.

        Raises:
            PparError: If required security master settings are missing.
        """
        if source_type == "mapping":
            security_master = self._security_master_definition(source_name)
            return {
                _SOURCE_FILE_PATH: security_master[_SOURCE_FILE_PATH],
                "identifier_column": security_master["identifier_column"],
                "name_column": data_source["classification_column"],
                _FILTER_TO_SECURITY_IDS: True,
                **self._security_id_construction_fields(security_master),
            }

        if data_source.get("is_security_master", False):
            security_master = self._security_master_definition(source_name)
            return {
                _SOURCE_FILE_PATH: self._explicit_or_security_master_path(
                    data_source,
                    security_master,
                ),
                "identifier_column": (
                    security_master["identifier_column"]
                    if _SECURITY_ID_CONSTRUCTION in security_master
                    else data_source.get(
                        "identifier_column",
                        security_master["identifier_column"],
                    )
                ),
                "name_column": data_source.get(
                    "name_column", security_master["name_column"]
                ),
                _FILTER_TO_SECURITY_IDS: True,
                **self._security_id_construction_fields(security_master),
            }

        if "file_path" in data_source:
            return {
                **data_source,
                _SOURCE_FILE_PATH: data_source["file_path"],
                _FILTER_TO_SECURITY_IDS: False,
            }

        mapping_name = cast(str, data_source["mapping"])
        mapping = self._specification.mappings[mapping_name]
        security_master = self._security_master_definition(source_name)
        return {
            **data_source,
            _SOURCE_FILE_PATH: security_master[_SOURCE_FILE_PATH],
            "identifier_column": mapping["classification_column"],
            _FILTER_TO_SECURITY_IDS: False,
        }

    def _security_master_definition(self, source_name: str) -> dict[str, Any]:
        """Return validated top-level security master path and columns.

        Args:
            source_name: Source requiring security master settings, used for
                validation context.

        Returns:
            Source definition containing the security master path and columns.

        Raises:
            PparError: If the security master path or required columns are not
                configured.
        """
        security_master_path = self._specification.file_path(
            _SECURITY_MASTER_FILE_KEY
        )
        configured_columns_value = self._specification.file_columns(
            _SECURITY_MASTER_FILE_KEY
        )
        if not security_master_path:
            raise PparError(
                self._error_message(
                    "files.security_master.path is required for source "
                    f"{source_name!r}."
                ),
            )
        if not isinstance(configured_columns_value, dict):
            raise PparError(
                self._error_message("files.security_master.columns must be a mapping."),
            )
        configured_columns = configured_columns_value
        supported_config_keys = (
            set(_SECURITY_MASTER_CONFIG_KEYS.values())
            | set(_SECURITY_MASTER_IDENTITY_KEYS)
        )
        unsupported_config_keys = sorted(
            str(key) for key in configured_columns if key not in supported_config_keys
        )
        if unsupported_config_keys:
            raise PparError(
                self._error_message(
                    "files.security_master.columns has unsupported keys: "
                    + ", ".join(unsupported_config_keys)
                    + "."
                ),
            )
        construction = security_id_construction(
            self._specification.values,
            "security_master",
            self._error_message,
            file_name=_SECURITY_MASTER_FILE_KEY,
        )

        security_master_columns = self._resolve_security_master_columns(
            source_name,
            security_master_path,
            configured_columns,
            composite_identifier=construction is not None,
        )
        definition: dict[str, Any] = {
            _SOURCE_FILE_PATH: security_master_path,
            "identifier_column": security_master_columns["identifier_column"],
            "name_column": security_master_columns["name_column"],
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
        """Return explicit or exact-default security master column names.

        Args:
            source_name: Source requiring security master settings, used for
                validation context.
            security_master_path: Configured security master source path.
            configured_columns: Explicit YAML security master column mappings.
            composite_identifier: Whether ``security_id`` construction replaces
                a single identifier source column.

        Returns:
            Mapping for ``identifier_column`` and ``name_column``.

        Raises:
            PparError: If a column cannot be resolved or if multiple candidates
                match the security master header.
        """
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
            if source_column is None:
                missing_fields.append(
                    f"{config_key!r}"
                )
                continue
            if source_column not in available_columns:
                missing_fields.append(
                    f"{config_key!r} configured as {source_column!r}"
                )
                continue
            resolved_columns[field_name] = source_column

        if missing_fields:
            raise PparError(
                self._error_message(
                    "Missing "
                    f"{missing_fields} for files.security_master.columns. "
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

    @staticmethod
    def _explicit_or_security_master_path(
        data_source: dict[str, Any],
        security_master: dict[str, Any],
    ) -> util.PathLike:
        """Return an explicit source path or inherited security master path."""
        return cast(
            util.PathLike,
            data_source.get("file_path", security_master[_SOURCE_FILE_PATH]),
        )

    def _validate_source_path_overrides(self) -> None:
        """Validate that file path overrides reference configured sources.

        Raises:
            PparError: If any override key is not a configured classification
                source name.
        """
        configured_source_names = set(self._specification.classifications)
        unknown_source_names = set(self._source_path_overrides) - configured_source_names
        if unknown_source_names:
            raise PparError(
                self._error_message(
                    f"Unknown source path override names: {unknown_source_names}"
                ),
            )
