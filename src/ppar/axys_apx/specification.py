"""Validate Axys/APX source settings expressed as Python values."""

from __future__ import annotations

# Python imports
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Callable, Literal, cast

# Project imports
from ppar.errors import PparError
import ppar.utilities as util

_ErrorMessage = Callable[[str], str]
_FILES_KEY = "files"
_PATH_KEY = "path"
_COLUMNS_KEY = "columns"
_SUPPORTED_FILE_KEYS = frozenset(
    {
        "portfolio_performance",
        "security_performance",
        "security_master",
    }
)
_SUPPORTED_FILE_FIELDS = frozenset({_PATH_KEY, _COLUMNS_KEY})
_DEFAULT_FILE_PATHS: dict[str, str] = {
    "portfolio_performance": "portperf.csv",
    "security_performance": "secperf.csv",
    "security_master": "secmast.csv",
}
_SUPPORTED_ROOT_KEYS = frozenset(
    {
        _FILES_KEY,
        "mappings",
        "security_id",
    }
)
_SUPPORTED_MAPPING_FIELDS = frozenset(
    {"classification_column", "display_name_column"}
)


class _AxysSpecification:
    """Validate Axys source settings and resolve referenced source paths.

    Attributes:
        base_directory: Directory against which relative source paths resolve.
        values: Validated source settings.
    """

    def __init__(
        self,
        base_directory: util.PathLike,
        error_message: _ErrorMessage,
        values: Mapping[str, object],
    ) -> None:
        """Initialize and validate Axys source settings.

        Args:
            base_directory: Directory against which relative source paths are
                resolved.
            error_message: Callback that adds facade-level source context to
                validation messages.
            values: Source paths, column mappings, security-master classification
                mappings, and security-identity settings.

        Raises:
            PparError: If ``values`` is not a mapping or has an invalid shape.
        """
        self.base_directory = Path(base_directory).expanduser().resolve()
        self._error_message = error_message
        if not isinstance(values, Mapping):
            raise PparError(error_message("Source settings must be a mapping."))
        self.values: dict[str, Any] = dict(values)
        self._validate_root_keys()
        self._validate_files()
        self._validate_mappings()

    def resolve_path(self, file_path: util.PathLike) -> Path:
        """Return an absolute or base-directory-relative source path.

        Args:
            file_path: Source path from an argument or configured setting.

        Returns:
            Absolute paths unchanged; relative paths resolved from the configured
            base directory.
        """
        if isinstance(file_path, str) and not file_path.strip():
            raise PparError(
                self._error_message(
                    "Source path must not be blank; use None to omit an override."
                ),
            )
        path = Path(file_path)
        return path if path.is_absolute() else self.base_directory / path

    def performance_path(
        self,
        specification_key: Literal[
            "portfolio_performance",
            "security_performance",
        ],
    ) -> Path:
        """Resolve a configured or conventional performance path.

        Args:
            specification_key: Dataset key inside the ``files`` section.

        Returns:
            Resolved portfolio- or security-performance source path.
        """
        return self.resolve_path(self.file_path(specification_key))

    def file_path(self, file_name: str) -> str:
        """Return a configured or conventional source-file path.

        Args:
            file_name: Dataset key inside the ``files`` section.

        Returns:
            Configured relative or absolute path, or the dataset default.
        """
        definition = self._file_definition(file_name)
        return cast(str, definition.get(_PATH_KEY, _DEFAULT_FILE_PATHS[file_name]))

    def file_columns(self, file_name: str) -> dict[str, Any]:
        """Return configured source-column mappings for one dataset.

        Args:
            file_name: Dataset key inside the ``files`` section.

        Returns:
            Column mappings keyed by normalized field name.
        """
        definition = self._file_definition(file_name)
        return cast(dict[str, Any], definition.get(_COLUMNS_KEY, {}))

    @property
    def mappings(self) -> dict[str, dict[str, Any]]:
        """Return configured Axys security-to-grouping mappings.

        Returns:
            Mapping definitions keyed by user-facing configuration name.
            Missing sections are treated as empty.
        """
        return cast(dict[str, dict[str, Any]], self.values.get("mappings", {}))

    def _validate_files(self) -> None:
        """Validate the shared nested source-file configuration shape."""
        files = self.values.get(_FILES_KEY, {})
        if not isinstance(files, dict):
            raise PparError(self._error_message("files must be a mapping."))
        unsupported_files = sorted(
            str(key) for key in files if key not in _SUPPORTED_FILE_KEYS
        )
        if unsupported_files:
            raise PparError(
                self._error_message(
                    "files has unsupported datasets: " + ", ".join(unsupported_files) + "."
                ),
            )
        for file_name, raw_definition in files.items():
            if not isinstance(raw_definition, dict):
                raise PparError(
                    self._error_message(f"files.{file_name} must be a mapping."),
                )
            unsupported_fields = sorted(
                str(key) for key in raw_definition if key not in _SUPPORTED_FILE_FIELDS
            )
            if unsupported_fields:
                raise PparError(
                    self._error_message(
                        f"files.{file_name} has unsupported keys: "
                        + ", ".join(unsupported_fields)
                        + "."
                    ),
                )
            path = raw_definition.get(_PATH_KEY)
            if path is not None and (
                not isinstance(path, str) or not path.strip()
            ):
                raise PparError(
                    self._error_message(
                        f"files.{file_name}.path must be a nonblank string."
                    ),
                )
            columns = raw_definition.get(_COLUMNS_KEY, {})
            if not isinstance(columns, dict):
                raise PparError(
                    self._error_message(f"files.{file_name}.columns must be a mapping."),
                )

    def _validate_root_keys(self) -> None:
        """Reject unknown or non-source top-level Axys settings."""
        unsupported = sorted(
            str(key) for key in self.values if key not in _SUPPORTED_ROOT_KEYS
        )
        if unsupported:
            raise PparError(
                self._error_message(
                    "Source settings have unsupported top-level keys: "
                    + ", ".join(unsupported)
                    + "."
                ),
            )

    def _validate_mappings(self) -> None:
        """Validate security-master classification mappings.

        Raises:
            PparError: If mappings are not a mapping, a name or source column is
                blank, or a definition has missing or unsupported fields.
        """
        mappings = self.values.get("mappings", {})
        if not isinstance(mappings, dict):
            raise PparError(self._error_message("mappings must be a mapping."))
        for raw_name, raw_definition in mappings.items():
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise PparError(
                    self._error_message("mapping names must be nonblank strings."),
                )
            if not isinstance(raw_definition, dict):
                raise PparError(
                    self._error_message(f"mapping {raw_name!r} must be a mapping."),
                )
            unsupported = sorted(
                str(key)
                for key in raw_definition
                if key not in _SUPPORTED_MAPPING_FIELDS
            )
            if unsupported:
                raise PparError(
                    self._error_message(
                        f"mapping {raw_name!r} has unsupported keys: "
                        + ", ".join(unsupported)
                        + "."
                    ),
                )
            missing = sorted(_SUPPORTED_MAPPING_FIELDS - set(raw_definition))
            if missing:
                raise PparError(
                    self._error_message(
                        f"mapping {raw_name!r} is missing required keys: "
                        + ", ".join(missing)
                        + "."
                    ),
                )
            for field_name in _SUPPORTED_MAPPING_FIELDS:
                value = raw_definition[field_name]
                if not isinstance(value, str) or not value.strip():
                    raise PparError(
                        self._error_message(
                            f"mappings.{raw_name}.{field_name} must be a "
                            "nonblank string."
                        ),
                    )

    def _file_definition(self, file_name: str) -> dict[str, Any]:
        """Return one previously validated source-file definition."""
        files = cast(dict[str, dict[str, Any]], self.values.get(_FILES_KEY, {}))
        return files.get(file_name, {})
