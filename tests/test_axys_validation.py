"""Focused tests for AxysData source and specification validation failures."""

# Python Imports
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import datetime as dt
from pathlib import Path
import tempfile
from typing import cast
import unittest

# Third-Party Imports
import polars as pl

# Test Imports
from tests import helpers as test_util

# Project Imports
from ppar.axys_apx import AxysData
from ppar.axys_apx.reconciliation import derive_security_performance_for_all_periods
from ppar.axys_apx.security_identity import (
    SecurityIdConstruction,
    with_constructed_security_id,
)
import ppar.schema as cols
from ppar.errors import PparError


@dataclass(frozen=True)
class _AxysArguments:
    """Constructor inputs that a validation test needs to override."""

    base_directory: Path = field(
        default_factory=lambda: test_util.axys_data_path("portperf.csv").parent
    )
    values: Mapping[str, object] = field(default_factory=test_util.axys_source_values)
    portfolio_performance_path: Path | None = field(
        default_factory=lambda: test_util.axys_data_path("portperf.csv")
    )
    security_performance_path: Path | None = field(
        default_factory=lambda: test_util.axys_data_path("secperf.csv")
    )
    portfolio_code: str = "PORT_SMALL"
    classification_name: str | None = None


def _assert_axys_error(
    test: unittest.TestCase,
    arguments: _AxysArguments | None = None,
    message_contains: str | None = None,
) -> None:
    """Assert that constructing AxysData fails with an actionable PparError."""
    arguments = arguments or _AxysArguments()

    with test.assertRaises(PparError) as context:
        data = AxysData(
            arguments.base_directory,
            arguments.values,
            portfolio_performance_path=arguments.portfolio_performance_path,
            security_performance_path=arguments.security_performance_path,
        )
        portfolio = data.get_portfolio(arguments.portfolio_code)
        if arguments.classification_name is not None:
            data.get_classification_sources(arguments.classification_name, portfolio)

    test.assertTrue(str(context.exception).strip(), str(context.exception))
    if message_contains is not None:
        test.assertIn(message_contains, str(context.exception))


def _write_text_csv(directory: Path, file_name: str, contents: str) -> Path:
    """Write a CSV fixture whose raw header is material to validation."""
    path = directory / file_name
    path.write_text(contents, encoding="utf-8")
    return path


def _write_frame_csv(
    directory: Path,
    file_name: str,
    data: Mapping[str, Sequence[object]],
) -> Path:
    """Write compact valid-schema input rows for a validation failure."""
    path = directory / file_name
    pl.DataFrame(data).write_csv(path)
    return path


def _fixture_specification() -> dict[str, object]:
    """Return the committed valid Python source settings as mutable data."""
    return test_util.axys_source_values()


def _file_definition(
    specification: dict[str, object],
    file_name: str,
) -> dict[str, object]:
    """Return one mutable nested source-file definition from a test config."""
    files = specification["files"]
    assert isinstance(files, dict)
    definition = files[file_name]
    assert isinstance(definition, dict)
    return definition


def _mapping_definitions(specification: dict[str, object]) -> dict[str, object]:
    """Return mutable mapping definitions from a specification."""
    return cast(dict[str, object], specification.setdefault("mappings", {}))


def _minimal_source_values(
    portfolio_performance_path: Path,
    security_performance_path: Path,
    security_master_path: Path | None = None,
) -> dict[str, object]:
    """Return compact Python-value source mappings for boundary tests."""
    files: dict[str, object] = {
        "portfolio_performance": {
            "path": str(portfolio_performance_path),
            "columns": {
                "from_date": "FROM_DATE",
                "thru_date": "THRU_DATE",
                "portfolio_code": "PORTFOLIO_CODE",
                "portfolio_name": "PORTFOLIO_NAME",
                "portfolio_return": "PORT_RETURN",
            },
        },
        "security_performance": {
            "path": str(security_performance_path),
            "columns": {
                "from_date": "FROM_DATE",
                "thru_date": "THRU_DATE",
                "portfolio_code": "PORTFOLIO_CODE",
                "identifier": "SECURITY_ID",
                "weight": "BEGIN_WEIGHT",
                "security_return": "SEC_RETURN",
                "contribution": "CONTRIBUTION",
            },
        },
    }
    values: dict[str, object] = {"files": files}
    if security_master_path is not None:
        files["security_master"] = {
            "path": str(security_master_path),
            "columns": {
                "identifier_column": "SECURITY_ID",
                "security_name": "SECURITY_NAME",
            },
        }
        values["mappings"] = {
            "Sector": {
                "classification_column": "SECTOR_CODE",
                "display_name_column": "SECTOR_NAME",
            }
        }
    return values


def _valid_portfolio_rows(
    portfolio_codes: Sequence[object] | None = None,
    portfolio_returns: Sequence[object] | None = None,
) -> dict[str, list[object]]:
    """Return compact portfolio-performance rows for boundary tests."""
    codes: list[object] = list(portfolio_codes) if portfolio_codes else ["PORT"]
    returns: list[object] = (
        list(portfolio_returns) if portfolio_returns else [0.04]
    )
    return {
        "PORTFOLIO_CODE": codes,
        "PORTFOLIO_NAME": [f"Portfolio {code}" for code in codes],
        "FROM_DATE": ["2024-01-01"] * len(codes),
        "THRU_DATE": ["2024-01-31"] * len(codes),
        "PORT_RETURN": returns,
    }


def _valid_security_rows(
    portfolio_codes: Sequence[object] | None = None,
    security_ids: Sequence[object] | None = None,
    weights: Sequence[object] | None = None,
    security_returns: Sequence[object] | None = None,
    contributions: Sequence[object] | None = None,
) -> dict[str, list[object]]:
    """Return compact security-performance rows for boundary tests."""
    identifiers: list[object] = list(security_ids) if security_ids else ["S1"]
    row_count = len(identifiers)
    codes: list[object] = (
        list(portfolio_codes) if portfolio_codes else ["PORT"] * row_count
    )
    return {
        "PORTFOLIO_CODE": codes,
        "FROM_DATE": ["2024-01-01"] * row_count,
        "THRU_DATE": ["2024-01-31"] * row_count,
        "SECURITY_ID": identifiers,
        "BEGIN_WEIGHT": list(weights) if weights else [1.0] * row_count,
        "SEC_RETURN": (
            list(security_returns) if security_returns else [0.04] * row_count
        ),
        "CONTRIBUTION": (
            list(contributions) if contributions else [0.04] * row_count
        ),
    }


def _reconciliation_frames(
    portfolio_rows: Mapping[str, Sequence[object]],
    security_rows: Mapping[str, Sequence[object]],
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return raw normalized frames for the defensive reconciliation boundary."""
    portfolio = (
        pl.DataFrame(portfolio_rows)
        .rename(
            {
                "PORTFOLIO_CODE": cols.PORTFOLIO_CODE,
                "FROM_DATE": cols.FROM_DATE,
                "THRU_DATE": cols.THRU_DATE,
                "PORT_RETURN": cols.PORTFOLIO_RETURN,
            }
        )
        .with_columns(
            pl.col(cols.FROM_DATE).str.to_date(),
            pl.col(cols.THRU_DATE).str.to_date(),
        )
    )
    security = (
        pl.DataFrame(security_rows)
        .rename(
            {
                "PORTFOLIO_CODE": cols.PORTFOLIO_CODE,
                "FROM_DATE": cols.FROM_DATE,
                "THRU_DATE": cols.THRU_DATE,
                "SECURITY_ID": cols.IDENTIFIER,
                "BEGIN_WEIGHT": cols.WEIGHT,
                "SEC_RETURN": cols.RETURN,
                "CONTRIBUTION": cols.CONTRIBUTION,
            }
        )
        .with_columns(
            pl.col(cols.FROM_DATE).str.to_date(),
            pl.col(cols.THRU_DATE).str.to_date(),
        )
    )
    return portfolio, security


class TestAxysValidation(unittest.TestCase):
    """Verify Axys input validation and numbered error behavior."""

    def test_financial_validation_matches_loader_and_reconciliation_boundaries(
        self,
    ) -> None:
        """Every invalid financial field produces equivalent boundary evidence."""
        fields = (
            (cols.PORTFOLIO_RETURN, "portfolio_performance", "portfolio_returns", True),
            (cols.RETURN, "security_performance", "security_returns", True),
            (cols.WEIGHT, "security_performance", "weights", False),
            (cols.CONTRIBUTION, "security_performance", "contributions", False),
        )
        invalid_values = (None, "bad", float("nan"), float("inf"), float("-inf"))
        for column_name, dataset_name, override_name, required in fields:
            for invalid_value in invalid_values:
                if invalid_value is None and not required:
                    continue
                with (
                    self.subTest(column_name=column_name, invalid_value=invalid_value),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    directory = Path(tmp)
                    portfolio_overrides: dict[str, Sequence[object]] = {}
                    security_overrides: dict[str, Sequence[object]] = {}
                    if dataset_name == "portfolio_performance":
                        portfolio_overrides[override_name] = [invalid_value]
                    else:
                        security_overrides[override_name] = [invalid_value]
                    portfolio_rows = _valid_portfolio_rows(**portfolio_overrides)
                    security_rows = _valid_security_rows(**security_overrides)
                    portfolio_path = _write_frame_csv(
                        directory,
                        "portperf.csv",
                        portfolio_rows,
                    )
                    security_path = _write_frame_csv(
                        directory,
                        "secperf.csv",
                        security_rows,
                    )
                    data = AxysData(
                        directory,
                        _minimal_source_values(portfolio_path, security_path),
                    )

                    with self.assertRaises(PparError) as loader_context:
                        data.get_portfolio("PORT")
                    direct_portfolio, direct_security = _reconciliation_frames(
                        portfolio_rows,
                        security_rows,
                    )
                    with self.assertRaises(PparError) as reconciliation_context:
                        derive_security_performance_for_all_periods(
                            direct_portfolio,
                            direct_security,
                            lambda message: message,
                        )

                    for message in (
                        str(loader_context.exception),
                        str(reconciliation_context.exception),
                    ):
                        self.assertIn(column_name, message)
                        self.assertIn(dataset_name, message)
                        self.assertIn("PORT", message)
                        self.assertIn("2024-01-31", message)
                    source_file = (
                        "portperf.csv"
                        if dataset_name == "portfolio_performance"
                        else "secperf.csv"
                    )
                    self.assertIn(source_file, str(loader_context.exception))

    def test_null_optional_financial_evidence_is_accepted_at_both_boundaries(
        self,
    ) -> None:
        """Only required fields reject null; optional evidence may be absent."""
        for override_name in ("weights", "contributions"):
            with (
                self.subTest(override_name=override_name),
                tempfile.TemporaryDirectory() as tmp,
            ):
                directory = Path(tmp)
                security_overrides: dict[str, Sequence[object]] = {
                    override_name: [None]
                }
                portfolio_rows = _valid_portfolio_rows()
                security_rows = _valid_security_rows(**security_overrides)
                portfolio_path = _write_frame_csv(
                    directory,
                    "portperf.csv",
                    portfolio_rows,
                )
                security_path = _write_frame_csv(
                    directory,
                    "secperf.csv",
                    security_rows,
                )
                data = AxysData(
                    directory,
                    _minimal_source_values(portfolio_path, security_path),
                )

                portfolio = data.get_portfolio("PORT")
                direct_portfolio, direct_security = _reconciliation_frames(
                    portfolio_rows,
                    security_rows,
                )
                reconciled, periods = derive_security_performance_for_all_periods(
                    direct_portfolio,
                    direct_security,
                    lambda message: message,
                )

                self.assertEqual(portfolio.security_performance.height, 1)
                self.assertEqual(reconciled.height, 1)
                self.assertEqual(len(periods), 1)

    def test_numeric_looking_portfolio_codes_remain_distinct_strings(self) -> None:
        """Portfolio selection preserves leading zeroes in account codes."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            portfolio_codes = ["001", "1", "99999999999999999999", "A01"]
            portfolio_path = _write_frame_csv(
                directory,
                "portperf.csv",
                _valid_portfolio_rows(
                    portfolio_codes=portfolio_codes,
                    portfolio_returns=[0.02, 0.03, 0.04, 0.05],
                ),
            )
            security_path = _write_frame_csv(
                directory,
                "secperf.csv",
                _valid_security_rows(
                    portfolio_codes=portfolio_codes,
                    security_ids=["S001", "S1", "S-LARGE", "S-A01"],
                    security_returns=[0.02, 0.03, 0.04, 0.05],
                    contributions=[0.02, 0.03, 0.04, 0.05],
                ),
            )
            data = AxysData(
                directory,
                _minimal_source_values(portfolio_path, security_path),
            )

            portfolios = data.get_portfolios(tuple(portfolio_codes))

            self.assertEqual(tuple(portfolios), tuple(portfolio_codes))
            self.assertEqual(portfolios["001"].portfolio_code, "001")
            self.assertEqual(portfolios["1"].portfolio_code, "1")
            self.assertEqual(
                portfolios["99999999999999999999"].portfolio_code,
                "99999999999999999999",
            )
            self.assertEqual(portfolios["A01"].portfolio_code, "A01")

    def test_numeric_looking_security_and_classification_codes_remain_distinct(self) -> None:
        """Security and classification identities survive CSV inference unchanged."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            identifiers = ["001", "1", "99999999999999999999", "A01"]
            portfolio_path = _write_frame_csv(
                directory,
                "portperf.csv",
                _valid_portfolio_rows(),
            )
            security_path = _write_frame_csv(
                directory,
                "secperf.csv",
                _valid_security_rows(
                    security_ids=identifiers,
                    weights=[0.25] * 4,
                    security_returns=[0.04] * 4,
                    contributions=[0.01] * 4,
                ),
            )
            security_master_path = _write_frame_csv(
                directory,
                "secmast.csv",
                {
                    "SECURITY_ID": identifiers,
                    "SECURITY_NAME": [f"Security {value}" for value in identifiers],
                    "SECTOR_CODE": identifiers,
                    "SECTOR_NAME": [f"Sector {value}" for value in identifiers],
                },
            )
            data = AxysData(
                directory,
                _minimal_source_values(
                    portfolio_path,
                    security_path,
                    security_master_path,
                ),
            )

            portfolio = data.get_portfolio("PORT")
            sources = data.get_classification_sources("Sector", portfolio)
            assert sources.mapping_data_sources is not None
            mapping = sources.mapping_data_sources[0]

            self.assertEqual(
                sorted(portfolio.security_performance[cols.IDENTIFIER].unique().to_list()),
                sorted(identifiers),
            )
            self.assertEqual(
                sorted(sources.classification_data_source[cols.IDENTIFIER].to_list()),
                sorted(identifiers),
            )
            self.assertEqual(
                sorted(mapping.iter_rows()),
                sorted((value, value) for value in identifiers),
            )

    def test_blank_security_identifiers_are_rejected(self) -> None:
        """Direct security identifiers must contain non-whitespace text."""
        for invalid_identifier in (None, "", " "):
            with (
                self.subTest(invalid_identifier=invalid_identifier),
                tempfile.TemporaryDirectory() as tmp,
            ):
                directory = Path(tmp)
                portfolio_path = _write_frame_csv(
                    directory,
                    "portperf.csv",
                    _valid_portfolio_rows(),
                )
                security_path = _write_frame_csv(
                    directory,
                    "secperf.csv",
                    _valid_security_rows(security_ids=[invalid_identifier]),
                )
                data = AxysData(
                    directory,
                    _minimal_source_values(portfolio_path, security_path),
                )

                with self.assertRaises(PparError) as context:
                    data.get_portfolio("PORT")

                message = str(context.exception)
                self.assertIn(cols.IDENTIFIER, message)
                self.assertIn("secperf.csv", message)
                self.assertIn("2024-01-31", message)

    def test_security_identifiers_are_trimmed(self) -> None:
        """Direct security identifiers lose only surrounding whitespace."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            portfolio_path = _write_frame_csv(
                directory,
                "portperf.csv",
                _valid_portfolio_rows(),
            )
            security_path = _write_frame_csv(
                directory,
                "secperf.csv",
                _valid_security_rows(security_ids=[" S1 "]),
            )
            data = AxysData(
                directory,
                _minimal_source_values(portfolio_path, security_path),
            )

            portfolio = data.get_portfolio("PORT")

            self.assertEqual(
                portfolio.security_performance[cols.IDENTIFIER].unique().to_list(),
                ["S1"],
            )

    def test_blank_portfolio_names_are_rejected(self) -> None:
        """Selected portfolio display names must contain non-whitespace text."""
        for invalid_name in (None, "", " "):
            with (
                self.subTest(invalid_name=invalid_name),
                tempfile.TemporaryDirectory() as tmp,
            ):
                directory = Path(tmp)
                portfolio_rows = _valid_portfolio_rows()
                portfolio_rows["PORTFOLIO_NAME"] = [invalid_name]
                portfolio_path = _write_frame_csv(
                    directory,
                    "portperf.csv",
                    portfolio_rows,
                )
                security_path = _write_frame_csv(
                    directory,
                    "secperf.csv",
                    _valid_security_rows(),
                )
                data = AxysData(
                    directory,
                    _minimal_source_values(portfolio_path, security_path),
                )

                with self.assertRaises(PparError) as context:
                    data.get_portfolio("PORT")

                message = str(context.exception)
                self.assertIn(cols.PORTFOLIO_NAME, message)
                self.assertIn("non-null and nonblank", message)
                self.assertIn("portperf.csv", message)
                self.assertIn("2024-01-31", message)

    def test_portfolio_codes_and_names_are_trimmed(self) -> None:
        """Axys account identities and display names are normalized before matching."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            portfolio_rows = _valid_portfolio_rows()
            portfolio_rows["PORTFOLIO_CODE"] = [" PORT "]
            portfolio_rows["PORTFOLIO_NAME"] = [" Portfolio "]
            security_rows = _valid_security_rows()
            security_rows["PORTFOLIO_CODE"] = [" PORT "]
            portfolio_path = _write_frame_csv(directory, "portperf.csv", portfolio_rows)
            security_path = _write_frame_csv(directory, "secperf.csv", security_rows)
            data = AxysData(
                directory,
                _minimal_source_values(portfolio_path, security_path),
            )

            portfolio = data.get_portfolio("PORT")

            self.assertEqual(portfolio.portfolio_code, "PORT")
            self.assertEqual(portfolio.portfolio_name, "PORT - Portfolio")

    def test_classification_identities_reject_null_or_blank_values(self) -> None:
        """Security-master classification codes must contain non-whitespace text."""
        for invalid_value in (None, "", " "):
            with (
                self.subTest(invalid_value=invalid_value),
                tempfile.TemporaryDirectory() as tmp,
            ):
                directory = Path(tmp)
                portfolio_path = _write_frame_csv(
                    directory,
                    "portperf.csv",
                    _valid_portfolio_rows(),
                )
                security_path = _write_frame_csv(
                    directory,
                    "secperf.csv",
                    _valid_security_rows(),
                )
                security_master_path = _write_frame_csv(
                    directory,
                    "secmast.csv",
                    {
                        "SECURITY_ID": ["S1"],
                        "SECURITY_NAME": ["Security One"],
                        "SECTOR_CODE": [invalid_value],
                        "SECTOR_NAME": ["Unknown"],
                    },
                )
                data = AxysData(
                    directory,
                    _minimal_source_values(
                        portfolio_path,
                        security_path,
                        security_master_path,
                    ),
                )

                portfolio = data.get_portfolio("PORT")
                with self.assertRaises(PparError) as context:
                    data.get_classification_sources("Sector", portfolio)

                message = str(context.exception)
                self.assertIn("SECTOR_CODE", message)
                self.assertIn("classification", message)
                self.assertIn("secmast.csv", message)

    def test_classification_identities_and_names_are_trimmed(self) -> None:
        """Classification codes and display names are normalized together."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            portfolio_path = _write_frame_csv(
                directory,
                "portperf.csv",
                _valid_portfolio_rows(),
            )
            security_path = _write_frame_csv(
                directory,
                "secperf.csv",
                _valid_security_rows(),
            )
            security_master_path = _write_frame_csv(
                directory,
                "secmast.csv",
                {
                    "SECURITY_ID": [" S1 "],
                    "SECURITY_NAME": [" Security One "],
                    "SECTOR_CODE": [" TECH "],
                    "SECTOR_NAME": [" Technology "],
                },
            )
            data = AxysData(
                directory,
                _minimal_source_values(
                    portfolio_path,
                    security_path,
                    security_master_path,
                ),
            )
            portfolio = data.get_portfolio("PORT")

            sources = data.get_classification_sources("Sector", portfolio)

            self.assertEqual(
                sources.classification_data_source.to_dict(as_series=False),
                {cols.IDENTIFIER: ["TECH"], cols.NAME: ["Technology"]},
            )
            assert sources.mapping_data_sources is not None
            self.assertEqual(
                sources.mapping_data_sources[0].rows(),
                [("S1", "TECH")],
            )

    def test_mapping_identities_reject_null_or_blank_values(self) -> None:
        """Security-to-classification destinations must contain text."""
        for invalid_value in (None, "", " "):
            with (
                self.subTest(invalid_value=invalid_value),
                tempfile.TemporaryDirectory() as tmp,
            ):
                directory = Path(tmp)
                security_master_path = _write_frame_csv(
                    directory,
                    "secmast.csv",
                    {
                        "SECURITY_ID": ["S001"],
                        "SECURITY_NAME": ["Synthetic Security S001"],
                        "SECTOR_CODE": [invalid_value],
                        "SECTOR_DESC": ["Technology"],
                    },
                )
                specification = _fixture_specification()
                security_master = _file_definition(specification, "security_master")
                security_master["path"] = str(security_master_path)
                data = AxysData(directory, specification)
                with self.assertRaises(PparError) as context:
                    data._classification_loader.load(  # pylint: disable=protected-access
                        "mapping",
                        "Sector",
                        ["S001"],
                    )

                message = str(context.exception)
                self.assertIn("SECTOR_CODE", message)
                self.assertIn("mapping", message)
                self.assertIn("secmast.csv", message)

    def test_mapping_identities_are_trimmed(self) -> None:
        """Security-to-classification identities are normalized before filtering."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            security_master_path = _write_frame_csv(
                directory,
                "secmast.csv",
                {
                    "SECURITY_ID": [" S001 "],
                    "SECURITY_NAME": [" Synthetic Security S001 "],
                    "SECTOR_CODE": [" TECH "],
                    "SECTOR_DESC": [" Technology "],
                },
            )
            specification = _fixture_specification()
            security_master = _file_definition(specification, "security_master")
            security_master["path"] = str(security_master_path)
            data = AxysData(directory, specification)

            mapping = data._classification_loader.load(  # pylint: disable=protected-access
                "mapping",
                "Sector",
                ["S001"],
            )

            self.assertEqual(mapping.rows(), [("S001", "TECH")])

    def test_security_master_components_reject_null_or_blank_values(self) -> None:
        """Composite security-master identity components require text."""
        construction = SecurityIdConstruction(
            components=("security_type", "security_symbol"),
            source_columns=("SECURITY_TYPE", "SECURITY_SYMBOL"),
            separator="_",
        )
        for invalid_value in (None, "", " "):
            with self.subTest(invalid_value=invalid_value):
                frame = pl.DataFrame(
                    {
                        "SECURITY_TYPE": [invalid_value],
                        "SECURITY_SYMBOL": ["S001"],
                    },
                    schema_overrides={"SECURITY_TYPE": pl.String},
                )

                with self.assertRaises(PparError) as context:
                    with_constructed_security_id(
                        frame,
                        construction,
                        output_column=cols.IDENTIFIER,
                        dataset_name="security_master",
                        source_path=Path("secmast.csv"),
                        error_message=lambda message: message,
                    )

                message = str(context.exception)
                self.assertIn("security_type", message)
                self.assertIn("security_master", message)
                self.assertIn("secmast.csv", message)

    def test_security_master_components_are_trimmed(self) -> None:
        """Composite security identifiers use normalized component values."""
        construction = SecurityIdConstruction(
            components=("security_type", "security_symbol"),
            source_columns=("SECURITY_TYPE", "SECURITY_SYMBOL"),
            separator="_",
        )
        frame = pl.DataFrame(
            {
                "SECURITY_TYPE": [" csus "],
                "SECURITY_SYMBOL": [" S001 "],
            }
        )

        normalized = with_constructed_security_id(
            frame,
            construction,
            output_column=cols.IDENTIFIER,
            dataset_name="security_master",
            source_path=Path("secmast.csv"),
            error_message=lambda message: message,
        )

        self.assertEqual(
            normalized.select(
                "SECURITY_TYPE",
                "SECURITY_SYMBOL",
                cols.IDENTIFIER,
            ).row(0),
            ("csus", "S001", "csus_S001"),
        )

    def test_missing_portfolio_performance_columns_are_rejected(self) -> None:
        """Required portfolio performance columns are validated before processing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            portfolio_performance_path = _write_text_csv(
                Path(temp_dir),
                "portperf.csv",
                (
                    "PORTFOLIO_CODEX,PORTFOLIO_NAME,FROM_DATE,THRU_DATE,PORT_RETURN\n"
                    "PORT_SMALL,Small Portfolio,2024-01-01,2024-01-31,0.01\n"
                ),
            )
            _assert_axys_error(
                self,
                _AxysArguments(portfolio_performance_path=portfolio_performance_path),
            )

    def test_missing_security_performance_columns_are_rejected(self) -> None:
        """Required security performance columns are validated before processing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            security_performance_path = _write_text_csv(
                Path(temp_dir),
                "secperf.csv",
                (
                    "PORTFOLIO_CODE,FROM_DATEX,THRU_DATE,SECURITY_ID,BEGIN_WEIGHT,"
                    "SEC_RETURN,CONTRIBUTION\n"
                    "PORT_SMALL,2024-01-01,2024-01-31,S001,1.0,0.01,0.01\n"
                ),
            )
            _assert_axys_error(
                self,
                _AxysArguments(security_performance_path=security_performance_path),
            )

    def test_unconfigured_performance_columns_are_rejected(self) -> None:
        """Unconfigured headings are not guessed when a mapping is omitted."""
        specification = _fixture_specification()
        _file_definition(specification, "portfolio_performance")["columns"] = {
            "from_date": "FROM_DATE",
            "thru_date": "THRU_DATE",
            "portfolio_code": "PORTFOLIO_CODE",
            "portfolio_name": "PORTFOLIO_NAME",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            portfolio_performance_path = _write_text_csv(
                directory,
                "portperf.csv",
                (
                    "PORTFOLIO_CODE,PORTFOLIO_NAME,FROM_DATE,THRU_DATE,RET,RETURN\n"
                    "PORT_SMALL,Small Portfolio,2024-01-01,2024-01-31,0.01,0.02\n"
                ),
            )

            _assert_axys_error(
                self,
                _AxysArguments(
                    base_directory=directory,
                    values=specification,
                    portfolio_performance_path=portfolio_performance_path,
                ),
                "portfolio_return",
            )

    def test_material_reconciliation_difference_is_rejected(self) -> None:
        """An unreconciled return difference outside tolerance is rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            portfolio_performance_path = _write_frame_csv(
                directory,
                "portperf.csv",
                {
                    "PORTFOLIO_CODE": ["PORT_FAIL_HIGH"],
                    "PORTFOLIO_NAME": ["Failure Demo High Target"],
                    "FROM_DATE": ["2024-03-01"],
                    "THRU_DATE": ["2024-03-31"],
                    "PORT_RETURN": [0.50],
                },
            )
            security_performance_path = _write_frame_csv(
                directory,
                "secperf.csv",
                {
                    # Positive weights confine the attainable return to the
                    # 1%-to-2% range, making the portfolio's 50% target infeasible.
                    "PORTFOLIO_CODE": ["PORT_FAIL_HIGH", "PORT_FAIL_HIGH"],
                    "FROM_DATE": ["2024-03-01", "2024-03-01"],
                    "THRU_DATE": ["2024-03-31", "2024-03-31"],
                    "SECURITY_ID": ["LOW_RETURN_1", "LOW_RETURN_2"],
                    "BEGIN_WEIGHT": [0.50, 0.50],
                    "SEC_RETURN": [0.01, 0.02],
                    "CONTRIBUTION": [0.005, 0.01],
                },
            )
            _assert_axys_error(
                self,
                _AxysArguments(
                    portfolio_performance_path=portfolio_performance_path,
                    security_performance_path=security_performance_path,
                    portfolio_code="PORT_FAIL_HIGH",
                ),
                "infeasible without reversing a source-supported sign",
            )

    def test_equal_return_reconciliation_failure_is_rejected(self) -> None:
        """Unachievable equal-security target returns are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            portfolio_performance_path = _write_frame_csv(
                directory,
                "portperf.csv",
                {
                    "PORTFOLIO_CODE": ["PORT_FAIL_EQUAL"],
                    "PORTFOLIO_NAME": ["Failure Demo Equal Weight"],
                    "FROM_DATE": ["2024-04-11"],
                    "THRU_DATE": ["2024-04-20"],
                    "PORT_RETURN": [0.20],
                },
            )
            security_performance_path = _write_frame_csv(
                directory,
                "secperf.csv",
                {
                    "PORTFOLIO_CODE": ["PORT_FAIL_EQUAL"],
                    "FROM_DATE": ["2024-04-11"],
                    "THRU_DATE": ["2024-04-20"],
                    "SECURITY_ID": ["S001"],
                    "BEGIN_WEIGHT": [1.0],
                    "SEC_RETURN": [0.0],
                    "CONTRIBUTION": [0.0],
                },
            )
            _assert_axys_error(
                self,
                _AxysArguments(
                    portfolio_performance_path=portfolio_performance_path,
                    security_performance_path=security_performance_path,
                    portfolio_code="PORT_FAIL_EQUAL",
                ),
            )

    def test_non_mapping_source_values_are_rejected(self) -> None:
        """A list cannot be used as the source-settings object."""
        values = cast(Mapping[str, object], ["not", "a", "mapping"])
        _assert_axys_error(self, _AxysArguments(values=values))

    def test_non_analytics_file_datasets_are_rejected(self) -> None:
        """Perfaud-oriented source datasets are not accepted by ppar."""
        for dataset_name in ("holdings", "transactions", "splits"):
            with self.subTest(dataset_name=dataset_name):
                specification = _fixture_specification()
                files = cast(dict[str, object], specification["files"])
                files[dataset_name] = {"path": f"{dataset_name}.csv"}

                _assert_axys_error(
                    self,
                    _AxysArguments(values=specification),
                    f"files has unsupported datasets: {dataset_name}",
                )

    def test_omitted_performance_paths_use_conventional_filenames(self) -> None:
        """Omitted Analytics performance paths resolve in the base directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            data = AxysData(
                directory,
                {},
                portfolio_performance_path=None,
                security_performance_path=None,
            )

            self.assertEqual(
                data.portfolio_performance_path,
                directory.resolve() / "portperf.csv",
            )
            self.assertEqual(
                data.security_performance_path,
                directory.resolve() / "secperf.csv",
            )

    def test_unknown_classification_is_rejected(self) -> None:
        """Requested classification names must be defined in the specification."""
        _assert_axys_error(self, _AxysArguments(classification_name="unknown"))

    def test_source_only_settings_remain_valid(self) -> None:
        """Documented files, columns, mappings, and security identity are accepted."""
        data = AxysData(
            test_util.axys_data_path("portperf.csv").parent,
            _fixture_specification(),
        )

        self.assertEqual(
            set(data.source_values),
            {"files", "mappings"},
        )

    def test_blank_source_paths_are_rejected(self) -> None:
        """A blank configured path or constructor override cannot mean omitted."""
        specification = _fixture_specification()
        portfolio_definition = _file_definition(
            specification,
            "portfolio_performance",
        )
        portfolio_definition["path"] = " "
        with self.assertRaisesRegex(PparError, "path must be a nonblank string"):
            AxysData(test_util.axys_data_path("portperf.csv").parent, specification)

        with self.assertRaisesRegex(PparError, "Source path must not be blank"):
            AxysData(
                test_util.axys_data_path("portperf.csv").parent,
                _fixture_specification(),
                portfolio_performance_path="",
            )

    def test_blank_performance_column_mapping_is_rejected(self) -> None:
        """Configured source-column names must contain non-whitespace text."""
        specification = _fixture_specification()
        portfolio_definition = _file_definition(
            specification,
            "portfolio_performance",
        )
        columns = portfolio_definition["columns"]
        assert isinstance(columns, dict)
        columns["from_date"] = " "
        data = AxysData(
            test_util.axys_data_path("portperf.csv").parent,
            specification,
        )

        with self.assertRaisesRegex(PparError, "values must be non-empty strings"):
            data.get_portfolio("PORT_SMALL")

    def test_blank_requested_classification_is_rejected(self) -> None:
        """Classification omission uses ``None`` rather than a blank name."""
        data = AxysData(
            test_util.axys_data_path("portperf.csv").parent,
            _fixture_specification(),
        )
        portfolio = data.get_portfolio("PORT_SMALL")

        with self.assertRaisesRegex(PparError, "classification_name must not be blank"):
            data.get_classification_sources(" ", portfolio)

    def test_unknown_source_settings_are_rejected(self) -> None:
        """Unsupported top-level source settings fail strict validation."""
        specification = _fixture_specification()
        specification["unsupported_option"] = True

        _assert_axys_error(
            self,
            _AxysArguments(values=specification),
            "unsupported top-level keys: unsupported_option",
        )

    def test_missing_portfolio_error_includes_requested_dates(self) -> None:
        """Portfolio-loading errors report the requested date window."""
        data = AxysData(
            test_util.axys_data_path("portperf.csv").parent,
            _fixture_specification(),
            portfolio_performance_path=test_util.axys_data_path("portperf.csv"),
            security_performance_path=test_util.axys_data_path("secperf.csv"),
        )

        with self.assertRaises(PparError) as context:
            data.get_portfolio(
                "UNKNOWN_PORTFOLIO",
                from_date=dt.date(2024, 1, 1),
                thru_date=dt.date(2024, 12, 31),
            )

        self.assertIn("from_date=2024-01-01", str(context.exception))
        self.assertIn("thru_date=2024-12-31", str(context.exception))

    def test_missing_required_mapping_field_is_rejected(self) -> None:
        """Security-master mappings require code and display-name columns."""
        specification = _fixture_specification()
        mappings = _mapping_definitions(specification)
        mappings["MissingDisplayName"] = {
            "classification_column": "SECTOR_CODE",
        }

        _assert_axys_error(
            self,
            _AxysArguments(values=specification),
            "missing required keys: display_name_column",
        )

    def test_nonexistent_source_column_is_rejected(self) -> None:
        """Configured mapping columns must exist in the security master."""
        specification = _fixture_specification()
        mappings = _mapping_definitions(specification)
        mapping = cast(dict[str, object], mappings["Sector"])
        mapping["classification_column"] = "SECTOR_CODE_XXX"

        _assert_axys_error(
            self,
            _AxysArguments(
                values=specification,
                classification_name="Sector",
            ),
            "Nonexistent column names",
        )

    def test_unconfigured_security_master_columns_are_rejected(self) -> None:
        """Security-master headings are not guessed without mappings."""
        specification = _fixture_specification()
        _file_definition(specification, "security_master").pop("columns", None)

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            security_master_path = _write_text_csv(
                directory,
                "security_master.csv",
                (
                    "SECURITY_ID,SECURITY_NAME,NAME\n"
                    "S001,Security Name,Alias Name\n"
                ),
            )
            _file_definition(specification, "security_master")["path"] = str(
                security_master_path
            )
            _assert_axys_error(
                self,
                _AxysArguments(
                    base_directory=directory,
                    values=specification,
                    classification_name="Security",
                ),
                "security_name",
            )

    def test_mapping_without_display_name_column_cannot_be_classification(self) -> None:
        """Mapping-backed classifications require display_name_column."""
        specification = _fixture_specification()
        mappings = _mapping_definitions(specification)
        mappings["SectorCodeOnly"] = {"classification_column": "SECTOR_CODE"}

        _assert_axys_error(
            self,
            _AxysArguments(values=specification),
            "missing required keys: display_name_column",
        )

    def test_unknown_source_field_is_rejected(self) -> None:
        """Unrecognized mapping-definition fields are rejected."""
        specification = _fixture_specification()
        mappings = _mapping_definitions(specification)
        mapping = cast(dict[str, object], mappings["Sector"])
        mapping["unknown_field_xxx"] = "security_master.csv"

        _assert_axys_error(
            self,
            _AxysArguments(values=specification),
            "mapping 'Sector' has unsupported keys: unknown_field_xxx",
        )

    def test_mapping_definition_rejects_classification_mapping_field(self) -> None:
        """Focused mapping definitions accept only security-master columns."""
        specification = _fixture_specification()
        mappings = _mapping_definitions(specification)
        sector_mapping = cast(dict[str, object], mappings["Sector"])
        sector_mapping["mapping"] = "Sector"

        _assert_axys_error(
            self,
            _AxysArguments(values=specification),
            "mapping 'Sector' has unsupported keys: mapping",
        )

    def test_no_common_periods_are_rejected(self) -> None:
        """Performance sources must retain at least one common period."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            portfolio_performance_path = _write_frame_csv(
                directory,
                "portperf.csv",
                {
                    "PORTFOLIO_CODE": ["PORT_SMALL"],
                    "PORTFOLIO_NAME": ["Small Demo Portfolio"],
                    "FROM_DATE": ["2024-01-01"],
                    "THRU_DATE": ["2024-01-30"],
                    "PORT_RETURN": [0.01],
                },
            )
            security_performance_path = _write_frame_csv(
                directory,
                "secperf.csv",
                {
                    "PORTFOLIO_CODE": ["PORT_SMALL"],
                    "FROM_DATE": ["2024-01-01"],
                    "THRU_DATE": ["2024-01-31"],
                    "SECURITY_ID": ["S001"],
                    "BEGIN_WEIGHT": [1.0],
                    "SEC_RETURN": [0.01],
                    "CONTRIBUTION": [0.01],
                },
            )
            _assert_axys_error(
                self,
                _AxysArguments(
                    portfolio_performance_path=portfolio_performance_path,
                    security_performance_path=security_performance_path,
                ),
            )


if __name__ == "__main__":
    unittest.main()
