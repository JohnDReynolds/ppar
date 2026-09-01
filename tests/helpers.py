"""Provide anchored fixture paths and reusable builders for ppar tests."""

from collections.abc import Mapping, Sequence
import datetime as dt
from pathlib import Path

import polars as pl

from ppar import Analytics
from ppar.attribution import Attribution
import ppar.schema as cols


Period = tuple[dt.date, dt.date]
AssetValues = tuple[Sequence[float], Sequence[float]]
DataSource = str | Path | pl.DataFrame

TESTS_DIRECTORY = Path(__file__).resolve().parent
DATA_DIRECTORY = TESTS_DIRECTORY / "data"
EXPECTED_RESULTS_DIRECTORY = TESTS_DIRECTORY / "expected_results"
HOLIDAYS_PATH = DATA_DIRECTORY / "holidays.csv"


def make_performance_df(
    periods: Sequence[Period],
    assets: Mapping[str, AssetValues],
) -> pl.DataFrame:
    """Create narrow performance rows from aligned return and weight values."""
    rows: list[dict[str, dt.date | str | float]] = []
    for period_index, (from_date, thru_date) in enumerate(periods):
        for identifier, (returns, weights) in assets.items():
            rows.append(
                {
                    cols.FROM_DATE: from_date,
                    cols.THRU_DATE: thru_date,
                    cols.IDENTIFIER: identifier,
                    cols.RETURN: returns[period_index],
                    cols.WEIGHT: weights[period_index],
                }
            )
    return pl.DataFrame(rows)


def axys_data_path(file_name: str) -> Path:
    """Return the anchored path to an Axys fixture file."""
    return _fixture_path(DATA_DIRECTORY / "axys", file_name, ".csv")


def axys_source_values() -> dict[str, object]:
    """Return fresh Python settings for the committed Axys fixtures."""
    return {
        "files": {
            "portfolio_performance": {
                "path": str(axys_data_path("portperf.csv")),
                "columns": {
                    "from_date": "FROM_DATE",
                    "thru_date": "THRU_DATE",
                    "portfolio_code": "PORTFOLIO_CODE",
                    "portfolio_name": "PORTFOLIO_NAME",
                    "portfolio_return": "PORT_RETURN",
                    "begin_market_value": "BEGIN_MV",
                    "end_market_value": "END_MV",
                    "flow": "FLOW",
                    "income": "INCOME",
                    "gain_loss": "GAIN_LOSS",
                    "period_id": "PERIOD_ID",
                },
            },
            "security_performance": {
                "path": str(axys_data_path("secperf.csv")),
                "columns": {
                    "from_date": "FROM_DATE",
                    "thru_date": "THRU_DATE",
                    "identifier": "SECURITY_ID",
                    "security_name": "SECURITY_NAME",
                    "portfolio_code": "PORTFOLIO_CODE",
                    "security_return": "SEC_RETURN",
                    "weight": "BEGIN_WEIGHT",
                    "contribution": "CONTRIBUTION",
                    "begin_market_value": "BEGIN_MV",
                    "end_market_value": "END_MV",
                    "income": "INCOME",
                    "gain_loss": "GAIN_LOSS",
                    "period_id": "PERIOD_ID",
                },
            },
            "security_master": {
                "path": str(axys_data_path("secmast.csv")),
                "columns": {
                    "identifier_column": "SECURITY_ID",
                    "security_name": "SECURITY_NAME",
                },
            },
        },
        "mappings": {
            "AssetClass": {
                "classification_column": "ASSET_CLASS_CODE",
                "display_name_column": "ASSET_CLASS_DESC",
            },
            "Country": {
                "classification_column": "COUNTRY_CODE",
                "display_name_column": "COUNTRY_DESC",
            },
            "Currency": {
                "classification_column": "CURRENCY_CODE",
                "display_name_column": "CURRENCY_DESC",
            },
            "Industry": {
                "classification_column": "INDUSTRY_CODE",
                "display_name_column": "INDUSTRY_DESC",
            },
            "Sector": {
                "classification_column": "SECTOR_CODE",
                "display_name_column": "SECTOR_DESC",
            },
        },
    }


def attribution(
    analytics: Analytics,
    classification_name: str | None = None,
    classification_data_source: DataSource | None = None,
    mapping_data_source: DataSource | None = None,
) -> Attribution:
    """Return attribution using anchored fixture sources where needed."""
    if classification_data_source is None:
        classification_data_source = classification_data_path(classification_name)
    if mapping_data_source is None:
        mapping_data_sources = mapping_data_paths(analytics, classification_name)
    else:
        mapping_data_sources = (mapping_data_source, mapping_data_source)
    return analytics.attribution(
        classification_name,
        classification_data_source,
        mapping_data_sources,
    )


def classification_data_path(classification_name: str | None) -> Path | None:
    """Return an anchored classification fixture path or ``None``."""
    if classification_name is None:
        return None
    return _fixture_path(
        DATA_DIRECTORY / "classifications",
        classification_name,
        ".csv",
    )


def mapping_data_paths(
    analytics: Analytics,
    to_classification_name: str | None,
) -> tuple[Path | None, Path | None]:
    """Return anchored mapping fixtures for portfolio and benchmark."""
    if to_classification_name is None:
        return (None, None)
    source_names = tuple(
        performance.classification_name
        for performance in analytics._performances  # pylint: disable=protected-access
    )
    paths = [
        (
            None
            if source_name == to_classification_name
            else _fixture_path(
                DATA_DIRECTORY / "mappings",
                f"{source_name}--to--{to_classification_name}.csv",
            )
        )
        for source_name in source_names
    ]
    return (paths[0], paths[1])


def performance_data_path(performance_name: str) -> Path:
    """Return the anchored path to a performance fixture."""
    return _fixture_path(DATA_DIRECTORY / "performance", performance_name, ".csv")


def expected_results_path(file_name: str) -> Path:
    """Return the anchored path to a stored result fixture."""
    return _fixture_path(EXPECTED_RESULTS_DIRECTORY, file_name)


def _fixture_path(directory: Path, file_name: str, suffix: str | None = None) -> Path:
    """Return one required fixture path relative to its anchored directory."""
    if suffix is not None and not file_name.endswith(suffix):
        file_name = f"{file_name}{suffix}"
    path = directory / file_name
    if not path.is_file():
        raise FileNotFoundError(f"Required test fixture does not exist: {path}")
    return path
