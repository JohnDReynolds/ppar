"""Construct stable ppar security identifiers from Axys/APX source fields."""

from __future__ import annotations

# Python imports
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, cast

# Third-party imports
import polars as pl

# Project imports
from ppar.errors import PparError
import ppar.utilities as util

_SECURITY_ID_KEY: Final = "security_id"
_COMPONENTS_KEY: Final = "components"
_SEPARATOR_KEY: Final = "separator"
_DATASETS_KEY: Final = "datasets"
_DEFAULT_SEPARATOR: Final = ""
_DEFAULT_COMPONENTS: Final = ("security_type", "security_symbol")
_CONFIGURATION_FIELDS: Final = {
    _COMPONENTS_KEY,
    _SEPARATOR_KEY,
    _DATASETS_KEY,
}
_DATASET_FIELDS: Final = {
    _COMPONENTS_KEY,
    _SEPARATOR_KEY,
}
_SECURITY_DATASETS: Final = {
    "security_performance",
    "security_master",
}


@dataclass(frozen=True)
class SecurityIdConstruction:
    """Describe normalized and source fields used to construct a security key.

    Attributes:
        components: Normalized mapping keys, in concatenation order.
        source_columns: Exact-case source CSV columns resolved for the dataset.
        separator: Optional text inserted between adjacent component values.
    """

    components: tuple[str, ...]
    source_columns: tuple[str, ...]
    separator: str

    @property
    def schema_overrides(self) -> dict[str, type[pl.DataType]]:
        """Return CSV schema overrides that preserve component text exactly."""
        return {source_column: pl.String for source_column in self.source_columns}


def security_id_construction(
    values: Mapping[str, object],
    dataset_name: str,
    error_message: Callable[[str], str],
    *,
    file_name: str | None = None,
) -> SecurityIdConstruction | None:
    """Return validated security-ID construction for one source dataset.

    Args:
        values: Axys/APX source settings.
        dataset_name: Normalized source dataset name.
        error_message: Callback that adds product-specific error context.
        file_name: Optional ``files`` dataset-name override. Analytics uses
            ``security_master`` for its security-master source.

    Returns:
        Construction settings for a security-bearing dataset. When
        ``security_id`` is omitted, layouts that do not map ``security_id``
        directly and do map both ``security_type`` and ``security_symbol`` use
        the Axys/APX defaults. Other layouts return ``None``.

    Raises:
        PparError: If the configuration shape, component names, or separator is
            invalid.
    """
    if dataset_name not in _SECURITY_DATASETS:
        return None
    configured_file_name = file_name or dataset_name
    raw_configuration = values.get(_SECURITY_ID_KEY)
    if raw_configuration is None:
        columns = _source_file_columns(
            values,
            configured_file_name,
            error_message,
        )
        if _SECURITY_ID_KEY in columns:
            return None
        if not all(component in columns for component in _DEFAULT_COMPONENTS):
            return None
        return SecurityIdConstruction(
            components=_DEFAULT_COMPONENTS,
            source_columns=_source_columns(
                values,
                configured_file_name,
                _DEFAULT_COMPONENTS,
                error_message,
            ),
            separator=_DEFAULT_SEPARATOR,
        )
    configuration = _require_mapping(
        raw_configuration,
        _SECURITY_ID_KEY,
        error_message,
    )
    _reject_unknown_fields(
        configuration,
        _CONFIGURATION_FIELDS,
        _SECURITY_ID_KEY,
        error_message,
    )

    dataset_configuration: Mapping[str, object] = {}
    raw_datasets = configuration.get(_DATASETS_KEY, {})
    datasets = _require_mapping(
        raw_datasets,
        f"{_SECURITY_ID_KEY}.{_DATASETS_KEY}",
        error_message,
    )
    _reject_unknown_fields(
        datasets,
        _SECURITY_DATASETS,
        f"{_SECURITY_ID_KEY}.{_DATASETS_KEY}",
        error_message,
    )
    raw_dataset_configuration = datasets.get(dataset_name)
    if raw_dataset_configuration is not None:
        dataset_configuration = _require_mapping(
            raw_dataset_configuration,
            f"{_SECURITY_ID_KEY}.{_DATASETS_KEY}.{dataset_name}",
            error_message,
        )
        _reject_unknown_fields(
            dataset_configuration,
            _DATASET_FIELDS,
            f"{_SECURITY_ID_KEY}.{_DATASETS_KEY}.{dataset_name}",
            error_message,
        )

    components_value = dataset_configuration.get(
        _COMPONENTS_KEY,
        configuration.get(_COMPONENTS_KEY),
    )
    components = _validate_components(
        components_value,
        dataset_name,
        error_message,
    )
    separator_value = dataset_configuration.get(
        _SEPARATOR_KEY,
        configuration.get(_SEPARATOR_KEY, _DEFAULT_SEPARATOR),
    )
    separator = _validate_separator(
        separator_value,
        dataset_name,
        error_message,
    )
    source_columns = _source_columns(
        values,
        configured_file_name,
        components,
        error_message,
    )
    return SecurityIdConstruction(
        components=components,
        source_columns=source_columns,
        separator=separator,
    )


def with_constructed_security_id(
    frame: pl.DataFrame,
    construction: SecurityIdConstruction,
    *,
    output_column: str,
    dataset_name: str,
    source_path: util.PathLike,
    error_message: Callable[[str], str],
) -> pl.DataFrame:
    """Add a validated composite security identifier to a source frame.

    Args:
        frame: Raw source CSV frame.
        construction: Ordered source columns and separator.
        output_column: Temporary or normalized constructed-ID column name.
        dataset_name: Normalized source dataset name for errors.
        source_path: Source CSV path for errors.
        error_message: Callback that adds product-specific error context.

    Returns:
        A new frame containing ``output_column``.

    Raises:
        PparError: If a component column is missing or blank after trimming, or
            produces an ambiguous composite identifier.

    Notes:
        Symbols may contain the configured separator. ppar therefore checks
        the observed component tuples for ambiguous concatenation instead of
        rejecting legitimate Axys/APX symbols such as ``FUND_A``.
    """
    missing_columns = set(construction.source_columns) - set(frame.columns)
    if missing_columns:
        raise PparError(
            error_message(
                f"Missing security_id component columns {sorted(missing_columns)} "
                f"in {str(source_path)!r} for {dataset_name}. CSV columns "
                f"available are: {sorted(frame.columns)}"
            ),
        )

    string_expressions = {
        component: pl.col(source_column).cast(pl.String, strict=False).str.strip_chars()
        for component, source_column in zip(
            construction.components,
            construction.source_columns,
            strict=True,
        )
    }
    for component, source_column in zip(
        construction.components,
        construction.source_columns,
        strict=True,
    ):
        string_expression = string_expressions[component]
        invalid_rows = frame.filter(
            string_expression.is_null()
            | string_expression.eq("")
        )
        if not invalid_rows.is_empty():
            value = invalid_rows.get_column(source_column)[0]
            raise PparError(
                error_message(
                    f"security_id component {component!r}, mapped to source column "
                    f"{source_column!r}, contains a blank or null value "
                    f"{value!r} after surrounding whitespace is removed in "
                    f"{str(source_path)!r} "
                    f"for {dataset_name}."
                ),
            )
    result = frame.with_columns(
        string_expressions[component].alias(source_column)
        for component, source_column in zip(
            construction.components,
            construction.source_columns,
            strict=True,
        )
    ).with_columns(
        pl.concat_str(
            [pl.col(source_column) for source_column in construction.source_columns],
            separator=construction.separator,
        ).alias(output_column)
    )
    collisions = (
        result.select((*construction.source_columns, output_column))
        .unique()
        .group_by(output_column)
        .len()
        .filter(pl.col("len") > 1)
    )
    if not collisions.is_empty():
        identifier = collisions.get_column(output_column)[0]
        raise PparError(
            error_message(
                f"Distinct security_id component tuples produce ambiguous "
                f"identifier {identifier!r} in {str(source_path)!r} for "
                f"{dataset_name}. Choose a different separator."
            ),
        )
    return result


def _require_mapping(
    value: object,
    field_path: str,
    error_message: Callable[[str], str],
) -> Mapping[str, object]:
    """Return ``value`` as a mapping or raise a configuration error."""
    if not isinstance(value, Mapping):
        raise PparError(error_message(f"{field_path} must be a mapping."))
    return cast(Mapping[str, object], value)


def _reject_unknown_fields(
    values: Mapping[str, object],
    allowed_fields: set[str],
    field_path: str,
    error_message: Callable[[str], str],
) -> None:
    """Raise when a security-ID configuration mapping has unknown fields."""
    unknown_fields = set(values) - allowed_fields
    if unknown_fields:
        raise PparError(
            error_message(
                f"Unknown fields for {field_path}: "
                f"{sorted(map(str, unknown_fields))}"
            ),
        )


def _validate_components(
    value: object,
    dataset_name: str,
    error_message: Callable[[str], str],
) -> tuple[str, ...]:
    """Return validated ordered normalized security-ID component names."""
    if not isinstance(value, list) or len(value) < 2:
        raise PparError(
            error_message(
                f"security_id components for {dataset_name} must be a list of "
                "at least two normalized field names."
            ),
        )
    if any(
        not isinstance(component, str) or not component.strip()
        for component in value
    ):
        raise PparError(
            error_message(
                f"security_id components for {dataset_name} must be nonempty strings."
            ),
        )
    components = tuple(value)
    if len(set(components)) != len(components):
        raise PparError(
            error_message(
                f"security_id components for {dataset_name} must be distinct: "
                f"{list(components)}"
            ),
        )
    invalid_components = [
        component
        for component in components
        if not component.isidentifier() or component.lower() != component
    ]
    if invalid_components:
        raise PparError(
            error_message(
                f"security_id components for {dataset_name} must use normalized "
                f"field names: {invalid_components}"
            ),
        )
    return components


def _source_columns(
    values: Mapping[str, object],
    file_name: str,
    components: tuple[str, ...],
    error_message: Callable[[str], str],
) -> tuple[str, ...]:
    """Resolve normalized identity components through one file layout."""
    section = _source_file_columns(
        values,
        file_name,
        error_message,
    )
    source_columns: list[str] = []
    for component in components:
        source_column = section.get(component, component)
        if not isinstance(source_column, str) or not source_column.strip():
            raise PparError(
                error_message(
                    f"files.{file_name}.columns.{component} must be a nonempty "
                    "source column name."
                ),
            )
        source_columns.append(source_column)
    if len(set(source_columns)) != len(source_columns):
        raise PparError(
            error_message(
                f"security_id components for files.{file_name}.columns must map "
                f"to distinct source columns: {source_columns}"
            ),
        )
    return tuple(source_columns)


def _validate_separator(
    value: object,
    dataset_name: str,
    error_message: Callable[[str], str],
) -> str:
    """Return a validated composite security-ID separator."""
    if not isinstance(value, str) or "\n" in value or "\r" in value:
        raise PparError(
            error_message(
                f"security_id separator for {dataset_name} must be a single-line "
                "string."
            ),
        )
    return value


def _source_file_columns(
    values: Mapping[str, object],
    file_name: str,
    error_message: Callable[[str], str],
) -> Mapping[str, object]:
    """Return one configured source file's normalized column mapping."""
    files = values.get("files", {})
    if not isinstance(files, Mapping):
        raise PparError(error_message("files must be a mapping."))
    definition = files.get(file_name, {})
    if not isinstance(definition, Mapping):
        raise PparError(error_message(f"files.{file_name} must be a mapping."))
    columns = definition.get("columns", {})
    if not isinstance(columns, Mapping):
        raise PparError(
            error_message(f"files.{file_name}.columns must be a mapping.")
        )
    return cast(Mapping[str, object], columns)
