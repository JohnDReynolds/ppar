"""Focused tests for AxysData source and specification validation failures."""

# Python Imports
from collections.abc import Mapping
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


def _write_frame_csv(directory: Path, file_name: str, data: dict[str, list[object]]) -> Path:
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


class TestAxysValidation(unittest.TestCase):
    """Verify Axys input validation and numbered error behavior."""

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
