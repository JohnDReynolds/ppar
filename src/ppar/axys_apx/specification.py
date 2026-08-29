"""Read and validate Axys YAML specifications."""

from __future__ import annotations

# Python imports
import datetime as dt
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Callable, Literal, cast

# Third-party imports
import yaml

# Project imports
from ppar.errors import PparError
import ppar.utilities as util

ErrorMessage = Callable[[str], str]
SourceType = Literal["classification", "mapping"]
_DefaultDateKey = Literal["from_date", "thru_date"]
_DEFAULT_FROM_DATE_KEY: _DefaultDateKey = "from_date"
_DEFAULT_THRU_DATE_KEY: _DefaultDateKey = "thru_date"
_DEFAULT_CLASSIFICATION_KEY = "classification"
_AXYS_PORTFOLIO_NAME_SEPARATOR = " - "
_FILES_KEY = "files"
_PATH_KEY = "path"
_COLUMNS_KEY = "columns"
_SUPPORTED_FILE_KEYS = frozenset(
    {
        "portfolio_performance",
        "security_performance",
        "security_master",
        "holdings",
        "transactions",
        "splits",
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
        "annual_minimum_acceptable_return",
        "annual_risk_free_rate",
        "benchmark",
        "classifications",
        "classification",
        "confidence_level",
        "currency_symbol",
        _FILES_KEY,
        "frequency",
        "from_date",
        "holidays",
        "mappings",
        "portfolio",
        "portfolio_value",
        "security_id",
        "source",
        "thru_date",
    }
)


class AxysSpecification:
    """Read Axys YAML settings and resolve referenced source paths.

    Attributes:
        path: Filesystem path to the YAML specification.
        base_directory: Directory against which relative source paths resolve.
        values: Parsed YAML settings dictionary.
    """

    def __init__(
        self,
        path: util.PathLike,
        error_message: ErrorMessage,
        values: Mapping[str, object] | None = None,
    ) -> None:
        """Read and validate an Axys YAML specification.

        Args:
            path: Path to the YAML specification file.
            error_message: Callback that adds facade-level source context to
                validation messages.
            values: Already-loaded canonical configuration. When supplied,
                the specification does not read YAML again.

        Raises:
            PparError: If the YAML cannot be parsed or its root object is not a
                dictionary.
        """
        self.path = Path(path)
        self.base_directory = self.path.parent
        self._error_message = error_message
        if values is None:
            with open(self.path, "r", encoding=util.ENCODING) as file:
                try:
                    loaded_yaml: Any = yaml.safe_load(file)
                except (OSError, yaml.YAMLError) as error:
                    raise PparError(error_message(f"Invalid YAML: {error}")) from error
        else:
            loaded_yaml = dict(values)
        if not isinstance(loaded_yaml, dict):
            raise PparError(error_message("YAML must be a dictionary"))
        self.values: dict[str, Any] = loaded_yaml
        self._validate_root_keys()
        self._validate_files()

    @classmethod
    def from_values(
        cls,
        base_directory: util.PathLike,
        error_message: ErrorMessage,
        values: Mapping[str, object],
    ) -> AxysSpecification:
        """Create a specification directly from Python values.

        Args:
            base_directory: Directory against which relative source paths are
                resolved.
            error_message: Callback that adds facade-level source context to
                validation messages.
            values: Source paths, column mappings, classifications, and other
                Axys/APX loading settings.

        Returns:
            Validated specification that does not read a YAML file.

        Raises:
            PparError: If the values have an invalid structure or unsupported
                keys.
        """
        instance = cls.__new__(cls)
        instance.path = Path(base_directory).expanduser().resolve()
        instance.base_directory = instance.path
        instance._error_message = error_message
        instance.values = dict(values)
        instance._validate_root_keys()
        instance._validate_files()
        return instance

    def resolve_path(self, file_path: util.PathLike) -> Path:
        """Return an absolute or specifications-relative source path.

        Args:
            file_path: Source path from an argument or specification setting.

        Returns:
            Absolute paths unchanged; relative paths resolved beside the
            specification file.
        """
        path = Path(file_path)
        return path if path.is_absolute() else self.base_directory / path

    def performance_path(
        self,
        argument_path: util.PathLike | None,
        specification_key: Literal[
            "portfolio_performance",
            "security_performance",
        ],
    ) -> Path:
        """Resolve an explicit, configured, or conventional performance path.

        Args:
            argument_path: Explicit source path provided to ``AxysData``, if
                any.
            specification_key: Dataset key inside the ``files`` section.

        Returns:
            Resolved portfolio- or security-performance source path.
        """
        file_path = argument_path or self.file_path(specification_key)
        return self.resolve_path(file_path)

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
    def prefix_portfolio_code(self) -> str | None:
        """Return Axys account-code separator for report display names.

        Returns:
            Separator text inserted between the Axys account code and account
            name.
        """
        return _AXYS_PORTFOLIO_NAME_SEPARATOR

    @property
    def default_from_date(self) -> dt.date | None:
        """Return the optional default earliest Axys reporting date.

        Returns:
            Configured default ``from_date``, or ``None`` when omitted.

        Raises:
            PparError: If the configured value is not a date or ISO date string.
        """
        return self._default_date(_DEFAULT_FROM_DATE_KEY)

    @property
    def default_thru_date(self) -> dt.date | None:
        """Return the optional default latest Axys thru date.

        Returns:
            Configured default ``thru_date``, or ``None`` when omitted.

        Raises:
            PparError: If the configured value is not a date or ISO date string.
        """
        return self._default_date(_DEFAULT_THRU_DATE_KEY)

    @property
    def default_classification_name(self) -> str | None:
        """Return the optional default Axys classification name.

        Returns:
            Configured default classification, or ``None`` when omitted.

        Raises:
            PparError: If the configured value is not a string.
        """
        value = self.values.get(_DEFAULT_CLASSIFICATION_KEY)
        if value is None:
            return None
        if not isinstance(value, str):
            raise PparError(
                self._error_message(
                    f"{_DEFAULT_CLASSIFICATION_KEY} must be a string."
                ),
            )
        return value or None

    @property
    def classifications(self) -> dict[str, dict[str, Any]]:
        """Return configured Axys classification definitions.

        Returns:
            Classification definitions keyed by user-facing configuration
            name. Missing sections are treated as empty.
        """
        return cast(dict[str, dict[str, Any]], self.values.get("classifications", {}))

    @property
    def mappings(self) -> dict[str, dict[str, Any]]:
        """Return configured Axys security-to-grouping mappings.

        Returns:
            Mapping definitions keyed by user-facing configuration name.
            Missing sections are treated as empty.
        """
        return cast(dict[str, dict[str, Any]], self.values.get("mappings", {}))

    def is_security_master(self, classification_name: str) -> bool:
        """Return whether a configured classification is the security master.

        Args:
            classification_name: Configured classification to inspect.

        Returns:
            ``True`` if the classification is marked as the security master;
            otherwise, ``False``.

        Notes:
            ``Security`` is a built-in security-master classification when it
            is not explicitly configured.
        """
        if classification_name == "Security":
            return True
        return bool(
            self.classifications.get(classification_name, {}).get(
                "is_security_master",
                False,
            )
        )

    def _default_date(self, key: Literal["from_date", "thru_date"]) -> dt.date | None:
        """Return an optional default date from a YAML date or ISO string."""
        value = self.values.get(key)
        if value is None:
            return None
        if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
            return value
        if isinstance(value, str):
            try:
                return dt.date.fromisoformat(value)
            except ValueError as error:
                raise PparError(
                    self._error_message(
                        f"{key} must be an ISO date like 2024-01-01."
                    ),
                ) from error
        raise PparError(
            self._error_message(
                f"{key} must be a date or ISO date string."
            ),
        )

    def _validate_files(self) -> None:
        """Validate the shared nested source-file configuration shape."""
        files = self.values.get(_FILES_KEY, {})
        if not isinstance(files, dict):
            raise PparError(self._error_message("files must be a mapping."))
        unsupported_files = sorted(str(key) for key in files if key not in _SUPPORTED_FILE_KEYS)
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
            if path is not None and (not isinstance(path, str) or not path):
                raise PparError(
                    self._error_message(f"files.{file_name}.path must be a string."),
                )
            columns = raw_definition.get(_COLUMNS_KEY, {})
            if not isinstance(columns, dict):
                raise PparError(
                    self._error_message(f"files.{file_name}.columns must be a mapping."),
                )

    def _validate_root_keys(self) -> None:
        """Reject unknown top-level Analytics configuration keys."""
        unsupported = sorted(
            str(key) for key in self.values if key not in _SUPPORTED_ROOT_KEYS
        )
        if unsupported:
            raise PparError(
                self._error_message(
                    "YAML has unsupported top-level keys: "
                    + ", ".join(unsupported)
                    + "."
                ),
            )

    def _file_definition(self, file_name: str) -> dict[str, Any]:
        """Return one previously validated source-file definition."""
        files = cast(dict[str, dict[str, Any]], self.values.get(_FILES_KEY, {}))
        return files.get(file_name, {})
