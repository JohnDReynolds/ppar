"""Translate between ppar host objects and the sole portable perfattr engine."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import polars as pl
from perfattr import (
    AttributionError,
    AttributionResult,
    Frequency as PortableFrequency,
    PreparationError,
    calculate_attribution,
    normalize_classification,
    normalize_mapping,
    prepare_attribution,
    read_classification_csv,
    read_mapping_csv,
    read_performance_csv,
)

from ppar._attribution_result import (
    AttributionCalculationResult,
    overall_summary_from_periods,
)
from ppar.errors import PparError
import ppar.schema as cols

if TYPE_CHECKING:
    from ppar.performance import Performance


_INPUT_COLUMNS = (
    cols.FROM_DATE,
    cols.THRU_DATE,
    cols.IDENTIFIER,
    cols.WEIGHT,
    cols.RETURN,
    cols.CONTRIBUTION,
    cols.QUANTITY_OF_DAYS,
)
_PPAR_RECONCILIATION_TOLERANCE = 5e-9
_PPAR_PERFORMANCE_COLUMNS = (
    *cols.DATE_COLUMNS,
    cols.QUANTITY_OF_DAYS,
    cols.TOTAL_RETURN,
    cols.IDENTIFIER,
    cols.RETURN,
    cols.WEIGHT,
    cols.CONTRIBUTION,
)

_PERIOD_DETAIL_COLUMNS = (
    *cols.DATE_COLUMNS,
    cols.CLASSIFICATION_IDENTIFIER,
    *cols.PORTFOLIO_COLUMNS_SIMPLE,
    cols.PORTFOLIO_CONTRIB_SMOOTHED,
    *cols.BENCHMARK_COLUMNS_SIMPLE,
    cols.BENCHMARK_CONTRIB_SMOOTHED,
    *cols.ACTIVE_COLUMNS_SIMPLE,
    cols.ACTIVE_CONTRIB_SMOOTHED,
    *cols.ATTRIBUTION_COLUMNS_SIMPLE,
    *cols.ATTRIBUTION_COLUMNS_SMOOTHED,
)
_PERIOD_DETAIL_NAMES = {
    "identifier": cols.CLASSIFICATION_IDENTIFIER,
    "portfolio_weight": cols.PORTFOLIO_WEIGHT,
    "portfolio_return": cols.PORTFOLIO_RETURN,
    "portfolio_contribution": cols.PORTFOLIO_CONTRIB_SIMPLE,
    "linked_portfolio_contribution": cols.PORTFOLIO_CONTRIB_SMOOTHED,
    "benchmark_weight": cols.BENCHMARK_WEIGHT,
    "benchmark_return": cols.BENCHMARK_RETURN,
    "benchmark_contribution": cols.BENCHMARK_CONTRIB_SIMPLE,
    "linked_benchmark_contribution": cols.BENCHMARK_CONTRIB_SMOOTHED,
    "active_weight": cols.ACTIVE_WEIGHT,
    "active_return": cols.ACTIVE_RETURN,
    "active_contribution": cols.ACTIVE_CONTRIB_SIMPLE,
    "linked_active_contribution": cols.ACTIVE_CONTRIB_SMOOTHED,
    "allocation_effect": cols.ALLOCATION_EFFECT_SIMPLE,
    "selection_effect": cols.SELECTION_EFFECT_SIMPLE,
    "total_effect": cols.TOTAL_EFFECT_SIMPLE,
    "linked_allocation_effect": cols.ALLOCATION_EFFECT_SMOOTHED,
    "linked_selection_effect": cols.SELECTION_EFFECT_SMOOTHED,
    "linked_total_effect": cols.TOTAL_EFFECT_SMOOTHED,
}

_OVERALL_DETAIL_COLUMNS = (
    cols.FROM_DATE,
    cols.THRU_DATE,
    cols.CLASSIFICATION_IDENTIFIER,
    cols.PORTFOLIO_RETURN,
    cols.PORTFOLIO_WEIGHT,
    cols.BENCHMARK_RETURN,
    cols.BENCHMARK_WEIGHT,
    cols.PORTFOLIO_CONTRIB_SMOOTHED,
    cols.BENCHMARK_CONTRIB_SMOOTHED,
    cols.ALLOCATION_EFFECT_SMOOTHED,
    cols.SELECTION_EFFECT_SMOOTHED,
    cols.ACTIVE_RETURN,
    cols.ACTIVE_WEIGHT,
    cols.ACTIVE_CONTRIB_SMOOTHED,
    cols.TOTAL_EFFECT_SMOOTHED,
)
_OVERALL_DETAIL_NAMES = {
    "identifier": cols.CLASSIFICATION_IDENTIFIER,
    "portfolio_weight": cols.PORTFOLIO_WEIGHT,
    "portfolio_return": cols.PORTFOLIO_RETURN,
    "linked_portfolio_contribution": cols.PORTFOLIO_CONTRIB_SMOOTHED,
    "benchmark_weight": cols.BENCHMARK_WEIGHT,
    "benchmark_return": cols.BENCHMARK_RETURN,
    "linked_benchmark_contribution": cols.BENCHMARK_CONTRIB_SMOOTHED,
    "active_weight": cols.ACTIVE_WEIGHT,
    "active_return": cols.ACTIVE_RETURN,
    "linked_active_contribution": cols.ACTIVE_CONTRIB_SMOOTHED,
    "linked_allocation_effect": cols.ALLOCATION_EFFECT_SMOOTHED,
    "linked_selection_effect": cols.SELECTION_EFFECT_SMOOTHED,
    "linked_total_effect": cols.TOTAL_EFFECT_SMOOTHED,
}


def _to_portable_input(performance: Performance) -> pd.DataFrame:
    """Convert one prepared Polars performance frame to the portable input schema."""
    rows = performance.narrow_df.select(_INPUT_COLUMNS).rename(
        {cols.QUANTITY_OF_DAYS: "quantity_of_days"}
    )
    return pd.DataFrame(
        # Keep the one-time boundary conversion columnar instead of first
        # materializing every column as a Python list.
        {column: rows[column].to_numpy() for column in rows.columns}
    )


def _polars_to_pandas(frame: pl.DataFrame) -> pd.DataFrame:
    """Translate a Polars frame columnarly without requiring PyArrow."""
    return pd.DataFrame(
        {column: frame[column].to_numpy() for column in frame.columns}
    )


def _prepared_to_polars(frame: pd.DataFrame) -> pl.DataFrame:
    """Translate prepared rows and restore ppar's repeated total-return column."""
    renamed = frame.rename(columns={"quantity_of_days": cols.QUANTITY_OF_DAYS})
    translated = pl.DataFrame(
        {column: renamed[column].to_numpy(copy=False) for column in renamed.columns}
    ).with_columns(
        pl.col(cols.DATE_COLUMNS).cast(pl.Date),
        pl.col(cols.QUANTITY_OF_DAYS).cast(pl.Int64),
    )
    totals = translated.group_by(cols.DATE_COLUMNS).agg(
        pl.col(cols.CONTRIBUTION).sum().alias(cols.TOTAL_RETURN)
    )
    return (
        translated.join(totals, on=cols.DATE_COLUMNS, validate="m:1")
        .select(_PPAR_PERFORMANCE_COLUMNS)
        .sort([cols.THRU_DATE, cols.IDENTIFIER])
    )


def _portable_frequency(frequency: object) -> PortableFrequency:
    """Translate ppar's compatibility enum value to the portable enum."""
    value = getattr(frequency, "value", frequency)
    try:
        return PortableFrequency(value)
    except ValueError as error:
        raise PparError(f"Unsupported reporting frequency: {value!r}.") from error


def _translate_preparation_error(error: Exception) -> PparError:
    """Preserve ppar's public error type at the portable boundary."""
    return PparError(f"perfattr preparation failed: {error}")


def _translate_identity_error(
    error: Exception,
    source: str,
    source_kind: str = "performance",
) -> PparError:
    """Preserve established ppar identity and conflict diagnostics."""
    message = str(error)
    if "multiple classifications" in message or "multiple names" in message:
        return PparError(
            f"{source} has conflicting values for the same identifier: {message}"
        )
    if "empty string" in message or "non-null strings" in message:
        if source_kind == "mapping":
            field = "to" if "classification_identifier" in message else "from"
        elif source_kind == "classification":
            field = (
                cols.CLASSIFICATION_NAME
                if "classification_name" in message
                else cols.CLASSIFICATION_IDENTIFIER
            )
        else:
            field = cols.IDENTIFIER
        return PparError(
            f"{source} identity field {field!r} must be non-null and nonblank "
            f"after surrounding whitespace is removed. {message}",
            context={"boundary": source, "field": field},
        )
    return _translate_preparation_error(error)


def _load_performance_input(
    data_source: str | Path | pl.DataFrame,
) -> tuple[pd.DataFrame, pl.DataFrame]:
    """Load one source-neutral input and retain optional display names.

    Args:
        data_source: Canonical performance CSV path or narrow Polars frame.

    Returns:
        A pandas input for portable preparation and separate host display metadata.

    Raises:
        PparError: If the host source type or canonical columns are invalid.
        PreparationError: If the portable CSV reader rejects a canonical file.

    Notes:
        This helper translates container types only. Financial normalization,
        validation, alignment, and consolidation occur in the subsequent public
        ``perfattr`` call.
    """
    if isinstance(data_source, str | Path):
        source = read_performance_csv(
            data_source,
            reconciliation_tolerance=_PPAR_RECONCILIATION_TOLERANCE,
        )
    elif isinstance(data_source, pl.DataFrame):
        source_frame = data_source.clone()
        required = (*cols.DATE_COLUMNS, cols.IDENTIFIER, cols.RETURN, cols.WEIGHT)
        missing = [column for column in required if column not in source_frame.columns]
        if missing:
            raise PparError(f"Missing required performance columns {missing}.")
        selected = [*required]
        selected.extend(
            column
            for column in (cols.CONTRIBUTION, cols.NAME)
            if column in source_frame.columns
        )
        try:
            source_frame = source_frame.select(selected).with_columns(
                pl.col(cols.DATE_COLUMNS).cast(pl.Date),
                pl.col((cols.WEIGHT, cols.RETURN)).cast(pl.Float64),
                pl.col(cols.IDENTIFIER).cast(pl.String),
            )
            if cols.CONTRIBUTION in source_frame.columns:
                source_frame = source_frame.with_columns(
                    pl.col(cols.CONTRIBUTION).cast(pl.Float64)
                )
            if cols.NAME in source_frame.columns:
                source_frame = source_frame.with_columns(
                    pl.col(cols.NAME).cast(pl.String).str.strip_chars()
                )
        except pl.exceptions.PolarsError as error:
            raise PparError(f"Cannot normalize performance columns: {error}") from error
        source = _polars_to_pandas(source_frame)
    else:
        raise PparError(
            "Performance data source must be a CSV path or Polars DataFrame."
        )

    names = pl.DataFrame()
    if "name" in source.columns:
        named = source.loc[:, ["thru_date", "identifier", "name"]].copy(deep=True)
        named["identifier"] = named["identifier"].astype("string").str.strip()
        named["name"] = named["name"].astype("string").str.strip()
        named = named.sort_values(
            ["thru_date", "identifier"], kind="stable"
        ).drop_duplicates("identifier", keep="last")
        names = pl.DataFrame(
            {
                cols.CLASSIFICATION_IDENTIFIER: named["identifier"].to_numpy(),
                cols.CLASSIFICATION_NAME: named["name"].to_numpy(),
            }
        )
    return source, names


def load_performance_source(
    data_source: str | Path | pl.DataFrame,
    *,
    from_date: dt.date | None,
    thru_date: dt.date | None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Load and prepare one canonical ppar performance source through perfattr.

    The second return value contains optional identifier/name metadata retained by
    the host presentation layer. Numerical normalization and validation belong to
    ``perfattr``.
    """
    try:
        source, names = _load_performance_input(data_source)
        prepared = prepare_attribution(
            source,
            source,
            from_date=from_date,
            thru_date=thru_date,
            reconciliation_tolerance=_PPAR_RECONCILIATION_TOLERANCE,
        )
        return _prepared_to_polars(prepared.portfolio), names
    except (PreparationError, TypeError, ValueError) as error:
        raise _translate_identity_error(error, "Performance") from error


def prepare_performance_sources(
    data_sources: Sequence[str | Path | pl.DataFrame],
    *,
    names: Sequence[str | None],
    classification_names: Sequence[str | None],
    from_date: dt.date,
    thru_date: dt.date,
    frequency: object,
    holidays: Collection[dt.date],
) -> tuple[Performance, Performance]:
    """Load and prepare an Analytics pair with one portable pipeline call.

    Args:
        data_sources: Portfolio and benchmark canonical data sources.
        names: Optional host display names in portfolio/benchmark order.
        classification_names: Optional source classifications in the same order.
        from_date: Earliest requested source-period endpoint.
        thru_date: Latest requested source-period endpoint.
        frequency: Host reporting frequency translated at the boundary.
        holidays: Nonbusiness dates used for fixed-frequency endpoints.

    Returns:
        Prepared host containers in portfolio/benchmark order.

    Raises:
        PparError: If pair metadata is malformed or portable preparation fails.

    Notes:
        This avoids independently preparing each raw side before the pair is aligned.
        Direct ``Performance`` construction continues to use the single-source
        boundary.
    """
    sources = tuple(data_sources)
    source_names = tuple(names)
    source_classifications = tuple(classification_names)
    metadata = (sources, source_names, source_classifications)
    if not all(len(values) == 2 for values in metadata):
        raise PparError("Analytics performance source metadata must contain two items.")

    try:
        loaded = tuple(_load_performance_input(source) for source in sources)
        prepared = prepare_attribution(
            loaded[0][0],
            loaded[1][0],
            frequency=_portable_frequency(frequency),
            holidays=holidays,
            from_date=None if from_date == dt.date.min else from_date,
            thru_date=None if thru_date == dt.date.max else thru_date,
            reconciliation_tolerance=_PPAR_RECONCILIATION_TOLERANCE,
        )
    except (PreparationError, TypeError, ValueError) as error:
        raise _translate_identity_error(error, "Performance") from error

    from ppar.performance import Performance  # pylint: disable=import-outside-toplevel

    results = tuple(
        Performance._from_prepared_rows(  # pylint: disable=protected-access
            _prepared_to_polars(frame),
            data_source=source,
            name=name,
            classification_name=classification_name,
            classification_items=metadata[1],
        )
        for source, name, classification_name, metadata, frame in zip(
            sources,
            source_names,
            source_classifications,
            loaded,
            (prepared.portfolio, prepared.benchmark),
            strict=True,
        )
    )
    return results[0], results[1]


def normalize_mapping_source(
    data_source: str | Path | pl.DataFrame,
    *,
    source_description: str = "Mapping data",
) -> pd.DataFrame:
    """Normalize a host mapping through the public portable boundary."""
    try:
        if isinstance(data_source, str | Path):
            return read_mapping_csv(data_source)
        if not isinstance(data_source, pl.DataFrame):
            raise PparError("Mapping data must be a CSV path or Polars DataFrame.")
        if len(data_source.columns) != 2:
            raise PparError("Mapping data must contain exactly two columns.")
        frame = _polars_to_pandas(data_source)
        frame.columns = ["identifier", "classification_identifier"]
        for column in frame.columns:
            frame[column] = frame[column].astype("string").astype(object)
        return normalize_mapping(frame)
    except (PreparationError, TypeError, ValueError) as error:
        raise _translate_identity_error(error, source_description, "mapping") from error


def normalize_classification_source(
    data_source: str | Path | pl.DataFrame,
    *,
    source_description: str = "Classification data",
) -> pd.DataFrame:
    """Normalize host display metadata through the public portable boundary."""
    try:
        if isinstance(data_source, str | Path):
            return read_classification_csv(data_source)
        if not isinstance(data_source, pl.DataFrame):
            raise PparError(
                "Classification data must be a CSV path or Polars DataFrame."
            )
        if len(data_source.columns) != 2:
            raise PparError("Classification data must contain exactly two columns.")
        frame = _polars_to_pandas(data_source)
        frame.columns = ["classification_identifier", "classification_name"]
        for column in frame.columns:
            frame[column] = frame[column].astype("string").astype(object)
        return normalize_classification(frame)
    except (PreparationError, TypeError, ValueError) as error:
        raise _translate_identity_error(
            error, source_description, "classification"
        ) from error


def prepare_performances(
    performances: Sequence[Performance],
    *,
    frequency: object,
    holidays: Collection[dt.date],
    mapping_data_sources: Sequence[str | Path | pl.DataFrame | None] = (None, None),
    classification_name: str | None = None,
) -> tuple[Performance, Performance]:
    """Prepare, align, map, and consolidate a ppar pair solely through perfattr."""
    portfolio, benchmark = performances
    mapping_sources = tuple(mapping_data_sources)
    if len(mapping_sources) != 2:
        raise PparError("mapping_data_sources must contain exactly two items.")
    mappings = tuple(
        None if source is None else normalize_mapping_source(source)
        for source in mapping_sources
    )
    try:
        prepared = prepare_attribution(
            _to_portable_input(portfolio),
            _to_portable_input(benchmark),
            frequency=_portable_frequency(frequency),
            holidays=holidays,
            portfolio_mapping=mappings[0],
            benchmark_mapping=mappings[1],
            reconciliation_tolerance=_PPAR_RECONCILIATION_TOLERANCE,
        )
    except (PreparationError, TypeError, ValueError) as error:
        raise _translate_preparation_error(error) from error

    results: list[Performance] = []
    for source, frame in zip(
        performances,
        (prepared.portfolio, prepared.benchmark),
        strict=True,
    ):
        result = source.copy()
        translated = _prepared_to_polars(frame)
        result._replace_calculated_rows(  # pylint: disable=protected-access
            translated,
            sort_rows=False,
        )
        if classification_name is not None:
            result.classification_name = classification_name
        results.append(result)
    return results[0], results[1]


def overall_performance(performance: Performance) -> pl.DataFrame:
    """Return ppar-compatible overall rows calculated by the portable core."""
    try:
        result = calculate_attribution(
            _to_portable_input(performance),
            _to_portable_input(performance),
            reconciliation_tolerance=_PPAR_RECONCILIATION_TOLERANCE,
        )
    except AttributionError as error:
        raise PparError(f"perfattr calculation failed: {error}") from error

    detail = result.overall_detail.rename(
        columns={
            "portfolio_weight": "weight",
            "portfolio_return": "return",
            "linked_portfolio_contribution": "contribution",
        }
    ).loc[
        :,
        [
            "from_date",
            "thru_date",
            "identifier",
            "weight",
            "return",
            "contribution",
        ],
    ]
    detail["quantity_of_days"] = int(
        performance.period_totals()[cols.QUANTITY_OF_DAYS].sum()
    )
    return _prepared_to_polars(detail)


def _to_polars(
    frame: pd.DataFrame,
    names: Mapping[str, str],
    columns: Sequence[str],
) -> pl.DataFrame:
    """Translate one portable result frame without requiring PyArrow."""
    renamed = frame.rename(columns=names)
    translated = pl.DataFrame(
        # NumPy arrays avoid Python-list materialization while retaining the
        # no-PyArrow boundary.
        {column: renamed[column].to_numpy(copy=False) for column in columns}
    ).with_columns(pl.col(cols.DATE_COLUMNS).cast(pl.Date))
    nullable_returns = [
        column for column in cols.RETURN_COLUMNS if column in translated.columns
    ]
    if nullable_returns:
        translated = translated.with_columns(pl.col(nullable_returns).fill_nan(None))
    return translated


def _period_summary(result: AttributionResult) -> pl.DataFrame:
    """Translate portable period and cumulative totals to the ppar summary schema."""
    summary = result.period_summary
    cumulative = result.cumulative
    values = {
        cols.FROM_DATE: summary["from_date"].tolist(),
        cols.THRU_DATE: summary["thru_date"].tolist(),
        cols.PORTFOLIO_CONTRIB_SIMPLE: summary["portfolio_contribution"].tolist(),
        cols.BENCHMARK_CONTRIB_SIMPLE: summary["benchmark_contribution"].tolist(),
        cols.PORTFOLIO_CONTRIB_SMOOTHED: summary[
            "linked_portfolio_contribution"
        ].tolist(),
        cols.BENCHMARK_CONTRIB_SMOOTHED: summary[
            "linked_benchmark_contribution"
        ].tolist(),
        cols.ALLOCATION_EFFECT_SIMPLE: summary["allocation_effect"].tolist(),
        cols.SELECTION_EFFECT_SIMPLE: summary["selection_effect"].tolist(),
        cols.ALLOCATION_EFFECT_SMOOTHED: summary[
            "linked_allocation_effect"
        ].tolist(),
        cols.SELECTION_EFFECT_SMOOTHED: summary[
            "linked_selection_effect"
        ].tolist(),
        cols.PORTFOLIO_RETURN: summary["portfolio_return"].tolist(),
        cols.BENCHMARK_RETURN: summary["benchmark_return"].tolist(),
        cols.ACTIVE_RETURN: summary["active_return"].tolist(),
        cols.ACTIVE_CONTRIB_SIMPLE: summary["active_contribution"].tolist(),
        cols.ACTIVE_CONTRIB_SMOOTHED: summary[
            "linked_active_contribution"
        ].tolist(),
        cols.TOTAL_EFFECT_SIMPLE: summary["total_effect"].tolist(),
        cols.TOTAL_EFFECT_SMOOTHED: summary["linked_total_effect"].tolist(),
        cols.CUMULATIVE_PORTFOLIO_RETURN: cumulative[
            "cumulative_portfolio_return"
        ].tolist(),
        cols.CUMULATIVE_BENCHMARK_RETURN: cumulative[
            "cumulative_benchmark_return"
        ].tolist(),
        cols.CUMULATIVE_PORTFOLIO_CONTRIB: cumulative[
            "cumulative_portfolio_contribution"
        ].tolist(),
        cols.CUMULATIVE_BENCHMARK_CONTRIB: cumulative[
            "cumulative_benchmark_contribution"
        ].tolist(),
        cols.CUMULATIVE_ALLOCATION_EFFECT: cumulative[
            "cumulative_allocation_effect"
        ].tolist(),
        cols.CUMULATIVE_SELECTION_EFFECT: cumulative[
            "cumulative_selection_effect"
        ].tolist(),
        cols.CUMULATIVE_TOTAL_EFFECT: cumulative[
            "cumulative_total_effect"
        ].tolist(),
        cols.CUMULATIVE_ACTIVE_RETURN: cumulative[
            "cumulative_active_return"
        ].tolist(),
        cols.CUMULATIVE_ACTIVE_CONTRIB: cumulative[
            "cumulative_active_contribution"
        ].tolist(),
    }
    return pl.DataFrame(values).with_columns(pl.col(cols.DATE_COLUMNS).cast(pl.Date))


def calculate_with_perfattr(
    performances: Sequence[Performance],
) -> AttributionCalculationResult:
    """Calculate prepared ppar performance rows with the portable core.

    Args:
        performances: Portfolio and benchmark performance streams after all ppar
            loading, alignment, consolidation, and classification mapping.

    Returns:
        The portable result translated to ppar's established Polars boundary.

    Raises:
        PparError: If the portable calculator rejects the prepared financial input or
            cannot satisfy one of its reconciliation invariants.
    """
    portfolio, benchmark = performances
    try:
        portable_result = calculate_attribution(
            _to_portable_input(portfolio),
            _to_portable_input(benchmark),
            reconciliation_tolerance=_PPAR_RECONCILIATION_TOLERANCE,
        )
    except AttributionError as error:
        raise PparError(f"perfattr calculation failed: {error}") from error

    period_summary = _period_summary(portable_result)
    return AttributionCalculationResult(
        period_summary=period_summary,
        period_detail=_to_polars(
            portable_result.period_detail,
            _PERIOD_DETAIL_NAMES,
            _PERIOD_DETAIL_COLUMNS,
        ),
        overall_summary=overall_summary_from_periods(period_summary),
        overall_detail=_to_polars(
            portable_result.overall_detail,
            _OVERALL_DETAIL_NAMES,
            _OVERALL_DETAIL_COLUMNS,
        ),
    )
