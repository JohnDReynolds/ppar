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
import yaml

# Test Imports
from tests import test_utilities as test_util

# Project Imports
from ppar.axys_apx import AxysData
import ppar.schema as cols
from ppar.errors import PparError


@dataclass(frozen=True)
class _AxysArguments:
    """Constructor inputs that a validation test needs to override."""

    specifications_path: Path = field(
        default_factory=lambda: test_util.axys_data_path("axys_column_mappings.yaml", ".yaml")
    )
    portfolio_performance_path: Path | None = field(
        default_factory=lambda: test_util.axys_data_path("portperf.csv")
    )
    security_performance_path: Path | None = field(
        default_factory=lambda: test_util.axys_data_path("secperf.csv")
    )
    source_path_overrides: Mapping[str, Path] | None = None
    portfolio_code: str = "PORT_SMALL"
    classification_name: str | None = None


def _assert_axys_error(
    test: unittest.TestCase,
    _error_code: int,
    arguments: _AxysArguments | None = None,
    message_contains: str | None = None,
) -> None:
    """Assert that constructing AxysData fails with an actionable PparError."""
    arguments = arguments or _AxysArguments()

    with test.assertRaises(PparError) as context:
        data = AxysData(
            arguments.specifications_path,
            arguments.portfolio_performance_path,
            arguments.security_performance_path,
            arguments.source_path_overrides,
        )
        portfolio = data.get_portfolio(arguments.portfolio_code)
        if arguments.classification_name is not None:
            data.get_classification_sources(arguments.classification_name, portfolio)

    test.assertTrue(str(context.exception).strip(), str(context.exception))
    if message_contains is not None:
        test.assertIn(message_contains, str(context.exception))


def _write_yaml(directory: Path, contents: object) -> Path:
    """Write temporary YAML contents and return its path."""
    path = directory / "ppar.yaml"
    path.write_text(yaml.safe_dump(contents), encoding="utf-8")
    return path


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
    """Load the committed valid specification as mutable data."""
    path = test_util.axys_data_path("axys_column_mappings.yaml", ".yaml")
    specification: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(specification, dict)
    mutable_specification = cast(dict[str, object], specification)
    _file_definition(mutable_specification, "portfolio_performance")["path"] = str(
        test_util.axys_data_path("portperf.csv")
    )
    _file_definition(mutable_specification, "security_performance")["path"] = str(
        test_util.axys_data_path("secperf.csv")
    )
    _file_definition(mutable_specification, "security_master")["path"] = str(
        test_util.axys_data_path("secmast.csv")
    )
    classifications = _classification_definitions(mutable_specification)
    for classification in classifications.values():
        if isinstance(classification, dict):
            classification_source = cast(dict[str, object], classification)
            file_path = classification_source.get("file_path")
            if isinstance(file_path, str):
                classification_source["file_path"] = str(test_util.axys_data_path(file_path))
    return mutable_specification


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


def _classification_definitions(specification: dict[str, object]) -> dict[str, object]:
    """Return mutable classification definitions from a specification."""
    return cast(dict[str, object], specification.setdefault("classifications", {}))


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


class TestAxysValidation(unittest.TestCase):
    """Verify Axys input validation and numbered error behavior."""

    def test_nonfinite_portfolio_returns_raise_contextual_error(self) -> None:
        """Account returns must be finite before reconciliation begins."""
        for invalid_value in (float("nan"), float("inf"), float("-inf"), "bad"):
            with self.subTest(invalid_value=invalid_value), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                portfolio_path = _write_frame_csv(
                    directory,
                    "portperf.csv",
                    _valid_portfolio_rows(portfolio_returns=[invalid_value]),
                )
                security_path = _write_frame_csv(
                    directory,
                    "secperf.csv",
                    _valid_security_rows(),
                )
                data = AxysData.from_values(
                    directory,
                    _minimal_source_values(portfolio_path, security_path),
                )

                with self.assertRaises(PparError) as context:
                    data.get_portfolio("PORT")

                message = str(context.exception)
                self.assertIn(cols.PORTFOLIO_RETURN, message)
                self.assertIn("2024-01-31", message)

    def test_invalid_security_financial_values_raise_contextual_error(self) -> None:
        """Security returns and non-null weight evidence must be finite."""
        cases: tuple[tuple[str, dict[str, Sequence[object]]], ...] = (
            (cols.RETURN, {"security_returns": [float("nan")]}),
            (cols.RETURN, {"security_returns": [None]}),
            (cols.WEIGHT, {"weights": [float("inf")]}),
            (cols.CONTRIBUTION, {"contributions": [float("-inf")]}),
            (cols.CONTRIBUTION, {"contributions": ["bad"]}),
        )
        for column_name, overrides in cases:
            with self.subTest(column_name=column_name), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                portfolio_path = _write_frame_csv(
                    directory,
                    "portperf.csv",
                    _valid_portfolio_rows(),
                )
                security_path = _write_frame_csv(
                    directory,
                    "secperf.csv",
                    _valid_security_rows(**overrides),
                )
                data = AxysData.from_values(
                    directory,
                    _minimal_source_values(portfolio_path, security_path),
                )

                with self.assertRaises(PparError) as context:
                    data.get_portfolio("PORT")

                message = str(context.exception)
                self.assertIn(column_name, message)
                self.assertIn("2024-01-31", message)

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
            data = AxysData.from_values(
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
            data = AxysData.from_values(
                directory,
                _minimal_source_values(
                    portfolio_path,
                    security_path,
                    security_master_path,
                ),
            )

            portfolio = data.get_portfolio("PORT", classification_name="Sector")
            sources = portfolio.required_classification_sources
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

    def test_blank_or_padded_security_identifiers_are_rejected(self) -> None:
        """Direct security identifiers must be complete, exact text values."""
        for invalid_identifier in (None, "", " S1 "):
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
                data = AxysData.from_values(
                    directory,
                    _minimal_source_values(portfolio_path, security_path),
                )

                with self.assertRaises(PparError) as context:
                    data.get_portfolio("PORT")

                message = str(context.exception)
                self.assertIn(cols.IDENTIFIER, message)
                self.assertIn("secperf.csv", message)
                self.assertIn("2024-01-31", message)

    def test_blank_classification_codes_are_rejected(self) -> None:
        """Classification codes cannot become null identities during CSV parsing."""
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
                    "SECURITY_ID": ["S1"],
                    "SECURITY_NAME": ["Security One"],
                    "SECTOR_CODE": [None],
                    "SECTOR_NAME": ["Unknown"],
                },
            )
            data = AxysData.from_values(
                directory,
                _minimal_source_values(
                    portfolio_path,
                    security_path,
                    security_master_path,
                ),
            )

            with self.assertRaises(PparError) as context:
                data.get_portfolio("PORT", classification_name="Sector")

            message = str(context.exception)
            self.assertIn("SECTOR_CODE", message)
            self.assertIn("secmast.csv", message)

    def test_missing_portfolio_performance_columns_raise_error_502(self) -> None:
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
                502,
                _AxysArguments(portfolio_performance_path=portfolio_performance_path),
            )

    def test_missing_security_performance_columns_raise_error_502(self) -> None:
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
                502,
                _AxysArguments(security_performance_path=security_performance_path),
            )

    def test_unconfigured_legacy_performance_columns_raise_error_502(self) -> None:
        """Legacy headings are not guessed when a mapping is omitted."""
        specification = _fixture_specification()
        _file_definition(specification, "portfolio_performance")["columns"] = {
            "from_date": "FROM_DATE",
            "thru_date": "THRU_DATE",
            "portfolio_code": "PORTFOLIO_CODE",
            "portfolio_name": "PORTFOLIO_NAME",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specifications_path = _write_yaml(directory, specification)
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
                502,
                _AxysArguments(
                    specifications_path=specifications_path,
                    portfolio_performance_path=portfolio_performance_path,
                ),
                "portfolio_return",
            )

    def test_material_reconciliation_difference_raises_error_503(self) -> None:
        """An unreconciled return difference outside tolerance is rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            portfolio_performance_path = _write_frame_csv(
                Path(temp_dir),
                "portperf.csv",
                {
                    "PORTFOLIO_CODE": ["PORT_FAIL_HIGH"],
                    "PORTFOLIO_NAME": ["Failure Demo High Target"],
                    "FROM_DATE": ["2024-03-01"],
                    "THRU_DATE": ["2024-03-31"],
                    "PORT_RETURN": [0.50],
                },
            )
            _assert_axys_error(
                self,
                503,
                _AxysArguments(
                    portfolio_performance_path=portfolio_performance_path,
                    security_performance_path=test_util.axys_data_path(
                        "unreachable_target_secperf.csv"
                    ),
                    portfolio_code="PORT_FAIL_HIGH",
                ),
            )

    def test_equal_return_reconciliation_failure_raises_error_503(self) -> None:
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
                503,
                _AxysArguments(
                    portfolio_performance_path=portfolio_performance_path,
                    security_performance_path=security_performance_path,
                    portfolio_code="PORT_FAIL_EQUAL",
                ),
            )

    def test_invalid_yaml_raises_error_504(self) -> None:
        """A syntactically invalid YAML specification is rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ppar.yaml"
            path.write_text("classifications: [", encoding="utf-8")
            _assert_axys_error(self, 504, _AxysArguments(specifications_path=path))

    def test_non_mapping_yaml_root_raises_error_504(self) -> None:
        """A YAML list cannot be used as the specification object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), ["not", "a", "mapping"])
            _assert_axys_error(self, 504, _AxysArguments(specifications_path=path))

    def test_omitted_performance_paths_use_conventional_filenames(self) -> None:
        """Omitted Analytics performance paths resolve beside the YAML."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            path = _write_yaml(directory, {})
            data = AxysData(
                path,
                portfolio_performance_path=None,
                security_performance_path=None,
            )

            self.assertEqual(
                data.portfolio_performance_path,
                directory / "portperf.csv",
            )
            self.assertEqual(
                data.security_performance_path,
                directory / "secperf.csv",
            )

    def test_unknown_classification_raises_error_504(self) -> None:
        """Requested classification names must be defined in the specification."""
        _assert_axys_error(self, 504, _AxysArguments(classification_name="unknown"))

    def test_invalid_configured_date_is_rejected(self) -> None:
        """Configured date filters must be ISO dates."""
        specification = _fixture_specification()
        specification["from_date"] = "01/01/2024"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(specifications_path=path),
                "from_date must be an ISO date",
            )

    def test_invalid_configured_classification_is_rejected(self) -> None:
        """Configured classification must be a string."""
        specification = _fixture_specification()
        specification["classification"] = ["Country"]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(specifications_path=path),
                "classification must be a string",
            )

    def test_unknown_defaults_section_raises_error_504(self) -> None:
        """The unsupported split defaults section fails strict validation."""
        specification = _fixture_specification()
        specification["defaults"] = {"classification": "Country"}

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(specifications_path=path),
                "unsupported top-level keys: defaults",
            )

    def test_invalid_root_classification_shape_is_rejected(self) -> None:
        """The root classification selection must be a string."""
        specification = _fixture_specification()
        specification["classification"] = {"Security": {}}

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(specifications_path=path),
                "classification must be a string",
            )

    def test_unknown_source_settings_raise_error_504(self) -> None:
        """Unsupported top-level source settings fail strict validation."""
        specification = _fixture_specification()
        specification["portfolio_performance_path"] = "legacy.csv"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(specifications_path=path),
                "unsupported top-level keys: portfolio_performance_path",
            )

    def test_missing_portfolio_error_includes_requested_dates(self) -> None:
        """Portfolio-loading errors report the requested date window."""
        data = AxysData(
            test_util.axys_data_path("axys_column_mappings.yaml", ".yaml"),
            test_util.axys_data_path("portperf.csv"),
            test_util.axys_data_path("secperf.csv"),
        )

        with self.assertRaises(PparError) as context:
            data.get_portfolio(
                "UNKNOWN_PORTFOLIO",
                from_date=dt.date(2024, 1, 1),
                thru_date=dt.date(2024, 12, 31),
            )

        self.assertIn("from_date=2024-01-01", str(context.exception))
        self.assertIn("thru_date=2024-12-31", str(context.exception))

    def test_missing_required_source_field_raises_error_504(self) -> None:
        """Explicit classification source definitions require a path."""
        specification = _fixture_specification()
        classifications = _classification_definitions(specification)
        classifications["BadMissingFilePath"] = {
            "identifier_column": "CODE",
            "name_column": "DESCRIPTION",
            "mapping": "Sector",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(
                    specifications_path=path,
                    classification_name="BadMissingFilePath",
                ),
            )

    def test_unknown_source_path_override_raises_error_504(self) -> None:
        """Source path overrides must reference configured source names."""
        _assert_axys_error(
            self,
            504,
            _AxysArguments(
                source_path_overrides={"UnknownSource": Path("x.csv")},
            ),
            "Unknown source path override names",
        )

    def test_mapping_only_source_path_override_raises_error_504(self) -> None:
        """Source path overrides apply to classifications, not mapping-only names."""
        _assert_axys_error(
            self,
            504,
            _AxysArguments(
                source_path_overrides={"Sector": Path("x.csv")},
            ),
            "Unknown source path override names",
        )

    def test_nonexistent_source_column_raises_error_504(self) -> None:
        """Specified source columns must exist in their CSV source."""
        specification = _fixture_specification()
        classifications = _classification_definitions(specification)
        classifications["BadFilterColumnName"] = {
            "file_path": str(test_util.axys_data_path("classification_lookup.csv")),
            "identifier_column": "CODE",
            "name_column": "DESCRIPTION",
            "filter_column": "CLASSIFICATION_TYPE_XXX",
            "filter_value": "SECTOR",
            "mapping": "Sector",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(
                    specifications_path=path,
                    classification_name="BadFilterColumnName",
                ),
            )

    def test_unconfigured_legacy_security_master_columns_raise_error_504(self) -> None:
        """Legacy security-master headings are not guessed without mappings."""
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
            specifications_path = _write_yaml(directory, specification)

            _assert_axys_error(
                self,
                504,
                _AxysArguments(
                    specifications_path=specifications_path,
                    classification_name="Security",
                ),
                "security_name",
            )

    def test_retired_security_master_name_column_is_rejected(self) -> None:
        """The security-master name mapping uses the normalized key."""
        specification = _fixture_specification()
        _file_definition(specification, "security_master")["columns"] = {
            "identifier_column": "SECURITY_ID",
            "name_column": "SECURITY_NAME",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            specifications_path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(
                    specifications_path=specifications_path,
                    classification_name="Security",
                ),
                "files.security_master.columns has unsupported keys: name_column",
            )

    def test_mapping_without_display_name_column_cannot_be_classification(self) -> None:
        """Mapping-backed classifications require display_name_column."""
        specification = _fixture_specification()
        mappings = _mapping_definitions(specification)
        mappings["SectorCodeOnly"] = {"classification_column": "SECTOR_CODE"}

        with tempfile.TemporaryDirectory() as temp_dir:
            specifications_path = _write_yaml(Path(temp_dir), specification)

            _assert_axys_error(
                self,
                504,
                _AxysArguments(
                    specifications_path=specifications_path,
                    classification_name="SectorCodeOnly",
                ),
                "cannot be used as a classification without display_name_column",
            )

    def test_unknown_source_field_raises_error_504(self) -> None:
        """Unrecognized source-definition fields are rejected."""
        specification = _fixture_specification()
        classifications = _classification_definitions(specification)
        sector = cast(dict[str, object], classifications["SectorLookup"])
        sector["file_path"] = str(test_util.axys_data_path("classification_lookup.csv"))
        sector["mapping"] = "BadUnknownField"
        mappings = _mapping_definitions(specification)
        mappings["BadUnknownField"] = {"unknown_field_xxx": "security_master.csv"}

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(specifications_path=path, classification_name="SectorLookup"),
            )

    def test_non_security_master_classification_requires_mapping(self) -> None:
        """Classifications below security grain must identify their mapping."""
        specification = _fixture_specification()
        classifications = _classification_definitions(specification)
        sector = cast(dict[str, object], classifications["SectorLookup"])
        del sector["mapping"]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(specifications_path=path, classification_name="SectorLookup"),
                "Missing mapping for classification 'SectorLookup'",
            )

    def test_classification_mapping_must_be_configured(self) -> None:
        """Classification mapping references must point to configured mappings."""
        specification = _fixture_specification()
        classifications = _classification_definitions(specification)
        sector = cast(dict[str, object], classifications["SectorLookup"])
        sector["mapping"] = "UnknownMapping"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(specifications_path=path, classification_name="SectorLookup"),
                "Unknown mapping 'UnknownMapping' for classification 'SectorLookup'",
            )

    def test_mapping_definition_rejects_classification_mapping_field(self) -> None:
        """The mapping field belongs to classifications, not mapping sources."""
        specification = _fixture_specification()
        classifications = _classification_definitions(specification)
        mappings = _mapping_definitions(specification)
        sector = cast(dict[str, object], classifications["SectorLookup"])
        sector_mapping = cast(dict[str, object], mappings["Sector"])
        sector["file_path"] = str(test_util.axys_data_path("classification_lookup.csv"))
        sector_mapping["mapping"] = "Sector"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(
                    specifications_path=path,
                    classification_name="SectorLookup",
                ),
                "Unknown fields for mapping 'Sector'",
            )

    def test_non_boolean_is_security_master_setting_raises_error_504(self) -> None:
        """The optional is_security_master setting accepts booleans only."""
        specification = _fixture_specification()
        classifications = _classification_definitions(specification)
        sector = cast(dict[str, object], classifications["SectorLookup"])
        sector["is_security_master"] = "true"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = _write_yaml(Path(temp_dir), specification)
            _assert_axys_error(
                self,
                504,
                _AxysArguments(specifications_path=path, classification_name="SectorLookup"),
            )

    def test_no_common_periods_raise_error_505(self) -> None:
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
                505,
                _AxysArguments(
                    portfolio_performance_path=portfolio_performance_path,
                    security_performance_path=security_performance_path,
                ),
            )


if __name__ == "__main__":
    unittest.main()
