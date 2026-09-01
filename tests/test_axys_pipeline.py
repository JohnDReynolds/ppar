"""Focused tests for the AxysData-to-Analytics pipeline using temporary inputs."""

# Python Imports
import datetime as dt
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

# Third-Party Imports
import polars as pl
import yaml

# Project Imports
from ppar import Analytics
from ppar.attribution import View
from ppar.axys_apx import AxysData
import ppar.schema as cols
from ppar.errors import PparError
from ppar.frequency import Frequency


def _write_axys_inputs(directory: Path) -> Path:
    """Write minimal Axys-like sources into a temporary test directory."""
    pl.DataFrame(
        {
            "FROM_DATE": ["2024-01-01", "2024-02-01", "2024-01-01"],
            "THRU_DATE": ["2024-01-31", "2024-02-29", "2024-01-31"],
            "PORTFOLIO_CODE": ["P1", "P1", "P2"],
            "PORTFOLIO_NAME": ["Growth", "Growth", "Income"],
            "PORT_RETURN": [0.04, 0.03, 0.02],
        }
    ).write_csv(directory / "portperf.csv")
    pl.DataFrame(
        {
            "FROM_DATE": [
                "2024-01-01",
                "2024-01-01",
                "2024-02-01",
                "2024-02-01",
                "2024-01-01",
            ],
            "THRU_DATE": [
                "2024-01-31",
                "2024-01-31",
                "2024-02-29",
                "2024-02-29",
                "2024-01-31",
            ],
            "PORTFOLIO_CODE": ["P1", "P1", "P1", "P1", "P2"],
            "SECURITY_ID": ["A", "B", "A", "B", "C"],
            "SEC_RETURN": [0.10, -0.05, 0.04, 0.015, 0.02],
            "BEGIN_WEIGHT": [0.50, 0.50, 0.50, 0.50, 1.00],
            "CONTRIBUTION": [0.06, -0.02, 0.024, 0.006, 0.02],
        }
    ).write_csv(directory / "secperf.csv")
    pl.DataFrame(
        {
            "SECURITY_ID": ["A", "B", "C", "UNUSED"],
            "SECURITY_NAME": ["Alpha", "Beta", "Cash", "Unused"],
            "SECTOR_CODE": ["TECH", "DEF", "CASH", "OTHER"],
            "SECTOR_DESC": ["Technology", "Defensive", "Cash", "Other"],
            "COUNTRY_CODE": ["US", "GB", "US", "CA"],
            "COUNTRY_DESC": ["United States", "United Kingdom", "United States", "Canada"],
        }
    ).write_csv(directory / "security_master.csv")
    pl.DataFrame(
        {
            "CODE": ["TECH", "DEF", "CASH", "OTHER"],
            "DESCRIPTION": ["Technology", "Defensive", "Cash", "Other"],
            "TYPE": ["SECTOR", "SECTOR", "SECTOR", "SECTOR"],
        }
    ).write_csv(directory / "classifications.csv")
    specification: dict[str, object] = {
        "files": {
            "portfolio_performance": {
                "path": "portperf.csv",
                "columns": {
                    cols.FROM_DATE: "FROM_DATE",
                    cols.THRU_DATE: "THRU_DATE",
                    cols.PORTFOLIO_CODE: "PORTFOLIO_CODE",
                    cols.PORTFOLIO_NAME: "PORTFOLIO_NAME",
                    "portfolio_return": "PORT_RETURN",
                },
            },
            "security_performance": {
                "path": "secperf.csv",
                "columns": {
                    cols.FROM_DATE: "FROM_DATE",
                    cols.THRU_DATE: "THRU_DATE",
                    cols.IDENTIFIER: "SECURITY_ID",
                    cols.PORTFOLIO_CODE: "PORTFOLIO_CODE",
                    "security_return": "SEC_RETURN",
                    cols.WEIGHT: "BEGIN_WEIGHT",
                    cols.CONTRIBUTION: "CONTRIBUTION",
                },
            },
            "security_master": {
                "path": "security_master.csv",
                "columns": {
                    "identifier_column": "SECURITY_ID",
                    "security_name": "SECURITY_NAME",
                },
            },
        },
        "classifications": {
            "SectorLookup": {
                "file_path": "classifications.csv",
                "display_name": "Sector",
                "identifier_column": "CODE",
                "name_column": "DESCRIPTION",
                "filter_column": "TYPE",
                "filter_value": "SECTOR",
                "mapping": "Sector",
            },
        },
        "mappings": {
            "Country": {
                "classification_column": "COUNTRY_CODE",
                "display_name_column": "COUNTRY_DESC",
            },
            "Sector": {
                "classification_column": "SECTOR_CODE",
                "display_name_column": "SECTOR_DESC",
            }
        },
    }
    specification_path = directory / "ppar.yaml"
    specification_path.write_text(yaml.safe_dump(specification), encoding="utf-8")
    return specification_path


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


def _file_columns(
    specification: dict[str, object],
    file_name: str,
) -> dict[str, object]:
    """Return mutable column mappings for one test source file."""
    columns = _file_definition(specification, file_name)["columns"]
    assert isinstance(columns, dict)
    return columns


class TestAxysPipeline(unittest.TestCase):
    """Verify successful Axys loading and downstream attribution behavior."""

    def test_load_reconciles_weights_and_filters_security_sources(self) -> None:
        """Selected security sources and performance are ready for Analytics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))

            portfolio = data.get_portfolio("P1")
            performance = portfolio.security_performance
            security_sources = data.get_classification_sources("Security", portfolio)
            sector_sources = data.get_classification_sources("Sector", portfolio)

            self.assertEqual(portfolio.portfolio_name, "P1 - Growth")
            self.assertEqual(
                security_sources.classification_data_source[cols.IDENTIFIER].sort().to_list(),
                ["A", "B"],
            )
            self.assertIsNotNone(sector_sources.mapping_data_sources)
            assert sector_sources.mapping_data_sources is not None
            self.assertEqual(
                sector_sources.mapping_data_sources[0][cols.IDENTIFIER].sort().to_list(),
                ["A", "B"],
            )
            first_period_weights = performance.filter(
                pl.col(cols.THRU_DATE) == dt.date(2024, 1, 31)
            )[cols.WEIGHT].to_list()
            self.assertTrue(math.isclose(first_period_weights[0], 0.60, abs_tol=1e-12))
            self.assertTrue(math.isclose(first_period_weights[1], 0.40, abs_tol=1e-12))

    def test_missing_axys_month_cannot_be_hidden_by_quarterly_consolidation(self) -> None:
        """Axys source periods must match before Analytics can label a quarter."""
        for missing_file in ("portperf.csv", "secperf.csv"):
            with self.subTest(missing_file=missing_file), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                specification_path = _write_axys_inputs(directory)
                portfolio_path = directory / "portperf.csv"
                security_path = directory / "secperf.csv"
                pl.concat(
                    (
                        pl.read_csv(portfolio_path),
                        pl.DataFrame(
                            {
                                "FROM_DATE": ["2024-03-01"],
                                "THRU_DATE": ["2024-03-31"],
                                "PORTFOLIO_CODE": ["P1"],
                                "PORTFOLIO_NAME": ["Growth"],
                                "PORT_RETURN": [0.02],
                            }
                        ),
                    ),
                    how="vertical",
                ).write_csv(portfolio_path)
                pl.concat(
                    (
                        pl.read_csv(security_path),
                        pl.DataFrame(
                            {
                                "FROM_DATE": ["2024-03-01", "2024-03-01"],
                                "THRU_DATE": ["2024-03-31", "2024-03-31"],
                                "PORTFOLIO_CODE": ["P1", "P1"],
                                "SECURITY_ID": ["A", "B"],
                                "SEC_RETURN": [0.03, 0.01],
                                "BEGIN_WEIGHT": [0.50, 0.50],
                                "CONTRIBUTION": [0.015, 0.005],
                            }
                        ),
                    ),
                    how="vertical",
                ).write_csv(security_path)
                missing_path = directory / missing_file
                pl.read_csv(missing_path).filter(
                    ~(
                        (pl.col("PORTFOLIO_CODE") == "P1")
                        & (pl.col("THRU_DATE") == "2024-02-29")
                    )
                ).write_csv(missing_path)

                with self.assertRaises(PparError) as context:
                    portfolio = AxysData(specification_path).get_portfolio("P1")
                    portfolio.to_analytics(frequency=Frequency.QUARTERLY)

                message = str(context.exception)
                self.assertIn("P1", message)
                self.assertIn("2024-02-01", message)
                self.assertIn("2024-02-29", message)

    def test_constructor_does_not_load_portfolios(self) -> None:
        """Constructing AxysData leaves portfolio loading to get_portfolio."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))

            self.assertFalse(hasattr(data, "portfolios"))
            self.assertFalse(hasattr(data, "classification_data_sources"))
            self.assertFalse(hasattr(data, "mapping_data_sources"))

    def test_get_portfolio_loads_requested_portfolio(self) -> None:
        """Portfolio loading returns reconciled output for a requested code."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio("P2")

            self.assertEqual(portfolio.portfolio_code, "P2")
            self.assertEqual(portfolio.portfolio_name, "P2 - Income")

    def test_get_portfolios_scans_each_performance_source_once(self) -> None:
        """A portfolio and benchmark share one scan of each performance CSV."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            with mock.patch(
                "ppar.axys_apx.performance_sources.pl.scan_csv",
                wraps=pl.scan_csv,
            ) as scan_csv:
                portfolios = data.get_portfolios(("P1", "P2"))

        self.assertEqual(list(portfolios), ["P1", "P2"])
        self.assertEqual(portfolios["P1"].portfolio_name, "P1 - Growth")
        self.assertEqual(portfolios["P2"].portfolio_name, "P2 - Income")
        self.assertEqual(scan_csv.call_count, 2)

    def test_classification_pair_combines_security_display_names(self) -> None:
        """Paired security sources cover holdings from both accounts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolios = data.get_portfolios(("P1", "P2"))
            portfolio = portfolios["P1"]
            benchmark = portfolios["P2"]

            sources = data.get_classification_sources_for_pair(
                "Security",
                portfolio,
                benchmark,
            )
            analytics = portfolio.to_analytics(benchmark)
            detail = analytics.attribution_for(sources).to_polars(
                View.SUBPERIOD_ATTRIBUTION
            )

            self.assertIsNone(sources.mapping_data_sources)
            self.assertEqual(
                sources.classification_data_source[cols.IDENTIFIER].to_list(),
                ["A", "B", "C"],
            )
            self.assertEqual(
                set(detail[cols.CLASSIFICATION_NAME].to_list()),
                {"Alpha", "Beta", "Cash"},
            )

    def test_classification_pair_preserves_mapping_side_order(self) -> None:
        """Paired mappings remain aligned to portfolio and benchmark inputs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolios = data.get_portfolios(("P1", "P2"))

            sources = data.get_classification_sources_for_pair(
                "Sector",
                portfolios["P1"],
                portfolios["P2"],
            )

            self.assertIsNotNone(sources.mapping_data_sources)
            assert sources.mapping_data_sources is not None
            portfolio_mapping, benchmark_mapping = sources.mapping_data_sources
            self.assertEqual(
                portfolio_mapping[cols.IDENTIFIER].sort().to_list(),
                ["A", "B"],
            )
            self.assertEqual(
                benchmark_mapping[cols.IDENTIFIER].sort().to_list(),
                ["C"],
            )

    def test_performance_columns_default_only_to_exact_normalized_names(self) -> None:
        """Performance mappings may be omitted for exact normalized headers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification_path = _write_axys_inputs(directory)
            pl.read_csv(directory / "portperf.csv").rename(
                {
                    "FROM_DATE": "from_date",
                    "THRU_DATE": "thru_date",
                    "PORTFOLIO_CODE": "portfolio_code",
                    "PORTFOLIO_NAME": "portfolio_name",
                    "PORT_RETURN": "portfolio_return",
                }
            ).write_csv(directory / "portperf.csv")
            pl.read_csv(directory / "secperf.csv").rename(
                {
                    "FROM_DATE": "from_date",
                    "THRU_DATE": "thru_date",
                    "PORTFOLIO_CODE": "portfolio_code",
                    "SECURITY_ID": "identifier",
                    "SEC_RETURN": "security_return",
                    "BEGIN_WEIGHT": "weight",
                    "CONTRIBUTION": "contribution",
                }
            ).write_csv(directory / "secperf.csv")
            specification = yaml.safe_load(specification_path.read_text(encoding="utf-8"))
            assert isinstance(specification, dict)
            del _file_definition(specification, "portfolio_performance")["columns"]
            del _file_definition(specification, "security_performance")["columns"]
            specification_path.write_text(
                yaml.safe_dump(specification),
                encoding="utf-8",
            )

            data = AxysData(specification_path)
            portfolio = data.get_portfolio("P1")

            self.assertEqual(portfolio.portfolio_name, "P1 - Growth")
            self.assertEqual(portfolio.security_performance.height, 4)

    def test_composite_security_id_joins_performance_and_security_master(self) -> None:
        """Analytics shares type-first composite identity across its sources."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification_path = _write_axys_inputs(directory)
            security_types = {"A": "csus", "B": "csus", "C": "caus", "UNUSED": "csus"}
            for file_name in ("secperf.csv", "security_master.csv"):
                path = directory / file_name
                frame = pl.read_csv(path).rename({"SECURITY_ID": "Security Symbol"})
                frame = frame.with_columns(
                    pl.col("Security Symbol")
                    .replace_strict(security_types)
                    .alias("Security Type")
                )
                frame.write_csv(path)

            specification = yaml.safe_load(
                specification_path.read_text(encoding="utf-8")
            )
            assert isinstance(specification, dict)
            specification["security_id"] = {
                "components": ["security_type", "security_symbol"],
                "separator": "_",
            }
            _file_columns(specification, "security_performance").update(
                {
                    "security_symbol": "Security Symbol",
                    "security_type": "Security Type",
                }
            )
            _file_columns(specification, "security_master").update(
                {
                    "security_symbol": "Security Symbol",
                    "security_type": "Security Type",
                }
            )
            del _file_columns(specification, "security_performance")[cols.IDENTIFIER]
            del _file_columns(specification, "security_master")["identifier_column"]
            specification_path.write_text(
                yaml.safe_dump(specification),
                encoding="utf-8",
            )

            data = AxysData(specification_path)
            portfolio = data.get_portfolio("P1")
            sources = data.get_classification_sources("Security", portfolio)

            self.assertEqual(
                portfolio.security_performance[cols.IDENTIFIER].unique().sort().to_list(),
                ["csus_A", "csus_B"],
            )
            self.assertEqual(
                sources.classification_data_source[cols.IDENTIFIER].sort().to_list(),
                ["csus_A", "csus_B"],
            )

    def test_explicit_performance_mapping_ignores_unconfigured_columns(self) -> None:
        """Configured performance columns ignore unrelated legacy headings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification_path = _write_axys_inputs(directory)
            portperf_path = directory / "portperf.csv"
            (
                pl.read_csv(portperf_path)
                .with_columns(
                    pl.lit(0.99).alias("RET"),
                    pl.lit(0.88).alias("RETURN"),
                )
                .write_csv(portperf_path)
            )

            data = AxysData(specification_path)
            portfolio = data.get_portfolio("P1")

            self.assertEqual(portfolio.portfolio_name, "P1 - Growth")
            self.assertEqual(portfolio.security_performance.height, 4)

    def test_security_master_columns_default_to_exact_normalized_names(self) -> None:
        """Security-master mappings may be omitted for normalized headers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification_path = _write_axys_inputs(directory)
            pl.read_csv(directory / "security_master.csv").rename(
                {
                    "SECURITY_ID": "security_id",
                    "SECURITY_NAME": "security_name",
                }
            ).write_csv(directory / "security_master.csv")
            specification = yaml.safe_load(specification_path.read_text(encoding="utf-8"))
            assert isinstance(specification, dict)
            del _file_definition(specification, "security_master")["columns"]
            specification_path.write_text(
                yaml.safe_dump(specification),
                encoding="utf-8",
            )

            data = AxysData(specification_path)
            portfolio = data.get_portfolio("P1")
            security_sources = data.get_classification_sources("Security", portfolio)
            sector_sources = data.get_classification_sources("Sector", portfolio)

            self.assertEqual(
                security_sources.classification_data_source[cols.IDENTIFIER]
                .sort()
                .to_list(),
                ["A", "B"],
            )
            self.assertEqual(sector_sources.classification_name, "Sector")

    def test_security_master_path_defaults_to_secmast_csv(self) -> None:
        """Analytics resolves an omitted security-master path conventionally."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification_path = _write_axys_inputs(directory)
            (directory / "security_master.csv").rename(directory / "secmast.csv")
            specification = yaml.safe_load(specification_path.read_text(encoding="utf-8"))
            assert isinstance(specification, dict)
            del _file_definition(specification, "security_master")["path"]
            specification_path.write_text(
                yaml.safe_dump(specification),
                encoding="utf-8",
            )

            data = AxysData(specification_path)
            portfolio = data.get_portfolio("P1")
            sources = data.get_classification_sources("Security", portfolio)

            self.assertEqual(sources.classification_data_source.height, 2)

    def test_explicit_security_master_mapping_ignores_other_columns(self) -> None:
        """Configured security-master columns ignore unrelated headings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification_path = _write_axys_inputs(directory)
            security_master_path = directory / "security_master.csv"
            (
                pl.read_csv(security_master_path)
                .with_columns(pl.lit("Wrong Alias").alias("NAME"))
                .write_csv(security_master_path)
            )

            data = AxysData(specification_path)
            portfolio = data.get_portfolio("P1")
            sources = data.get_classification_sources("Security", portfolio)

            self.assertEqual(
                sources.classification_data_source[cols.NAME].sort().to_list(),
                ["Alpha", "Beta"],
            )

    def test_date_filters_apply_before_returning_portfolio_performance(self) -> None:
        """Axys date arguments restrict the periods retained for a portfolio."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio(
                "P1",
                from_date=dt.date(2024, 2, 1),
                thru_date=dt.date(2024, 2, 29),
            )

            performance = portfolio.security_performance

            self.assertEqual(performance.height, 2)
            self.assertEqual(
                performance[cols.THRU_DATE].unique().to_list(),
                [dt.date(2024, 2, 29)],
            )

    def test_get_portfolio_loads_one_requested_portfolio(self) -> None:
        """Lazy portfolio loading returns one reconciled portfolio by code."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))

            portfolio = data.get_portfolio("P1")

            self.assertEqual(portfolio.portfolio_code, "P1")
            self.assertEqual(portfolio.portfolio_name, "P1 - Growth")
            self.assertEqual(portfolio.security_performance.height, 4)

    def test_get_portfolio_applies_date_filters(self) -> None:
        """Lazy portfolio loading accepts its own date window."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))

            portfolio = data.get_portfolio(
                "P1",
                from_date=dt.date(2024, 2, 1),
                thru_date=dt.date(2024, 2, 29),
            )

            self.assertEqual(portfolio.security_performance.height, 2)
            self.assertEqual(
                portfolio.security_performance[cols.THRU_DATE].unique().to_list(),
                [dt.date(2024, 2, 29)],
            )

    def test_get_portfolio_uses_configured_selection(self) -> None:
        """Root settings supply omitted date filters and classification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            specification_path = _write_axys_inputs(Path(temp_dir))
            specification = yaml.safe_load(specification_path.read_text(encoding="utf-8"))
            assert isinstance(specification, dict)
            specification.update(
                from_date=dt.date(2024, 2, 1),
                thru_date=dt.date(2024, 2, 29),
                classification="Country",
            )
            specification_path.write_text(
                yaml.safe_dump(specification),
                encoding="utf-8",
            )
            data = AxysData(specification_path)

            portfolio = data.get_portfolio("P1")

            sources = portfolio.required_classification_sources
            self.assertEqual(portfolio.security_performance.height, 2)
            self.assertEqual(sources.classification_name, "Country")
            self.assertEqual(
                sources.classification_data_source[cols.NAME].sort().to_list(),
                ["Canada", "United Kingdom", "United States"],
            )

    def test_get_portfolio_arguments_override_configured_selection(self) -> None:
        """Explicit arguments override the configured root selection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            specification_path = _write_axys_inputs(Path(temp_dir))
            specification = yaml.safe_load(specification_path.read_text(encoding="utf-8"))
            assert isinstance(specification, dict)
            specification.update(
                from_date="2024-02-01",
                thru_date="2024-02-29",
                classification="Country",
            )
            specification_path.write_text(
                yaml.safe_dump(specification),
                encoding="utf-8",
            )
            data = AxysData(specification_path)

            portfolio = data.get_portfolio(
                "P1",
                from_date=dt.date(2024, 1, 1),
                thru_date=dt.date(2024, 1, 31),
                classification_name="Sector",
            )

            sources = portfolio.required_classification_sources
            self.assertEqual(portfolio.security_performance.height, 2)
            self.assertEqual(
                portfolio.security_performance[cols.THRU_DATE].unique().to_list(),
                [dt.date(2024, 1, 31)],
            )
            self.assertEqual(sources.classification_name, "Sector")

    def test_axys_sources_roll_up_through_analytics_to_sector_attribution(self) -> None:
        """Generated classification and mapping sources drive public attribution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio("P1", classification_name="Sector")

            analytics = portfolio.to_analytics()
            attribution = analytics.attribution()
            detail = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

            self.assertEqual(
                set(detail[cols.CLASSIFICATION_NAME].to_list()),
                {"Defensive", "Technology"},
            )
            self.assertTrue((detail[cols.ACTIVE_RETURN] == 0.0).all())
            self.assertTrue((detail[cols.TOTAL_EFFECT_SIMPLE] == 0.0).all())

    def test_get_portfolio_can_include_requested_classification_sources(self) -> None:
        """Lazy portfolio loading can attach one requested classification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))

            portfolio = data.get_portfolio("P1", classification_name="Sector")

            sources = portfolio.required_classification_sources
            self.assertEqual(sources.classification_name, "Sector")
            self.assertIsNotNone(sources.mapping_data_sources)
            self.assertEqual(
                sources.classification_data_source[cols.NAME].sort().to_list(),
                ["Cash", "Defensive", "Other", "Technology"],
            )

    def test_portfolio_convenience_methods_build_attribution(self) -> None:
        """Axys portfolio bundles can initialize Analytics and attribution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio("P1", classification_name="Sector")

            analytics = portfolio.to_analytics()
            attribution = analytics.attribution()
            detail = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

            self.assertEqual(analytics.classification_names(), ("Security", "Security"))
            self.assertEqual(
                set(detail[cols.CLASSIFICATION_NAME].to_list()),
                {"Defensive", "Technology"},
            )

    def test_portfolio_convenience_method_accepts_axys_benchmark(self) -> None:
        """An Axys benchmark portfolio can supply benchmark data and mappings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio("P1", classification_name="Country")
            benchmark = data.get_portfolio("P2", classification_name="Country")

            analytics = portfolio.to_analytics(benchmark)
            attribution = analytics.attribution()
            detail = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

            self.assertEqual(analytics.classification_names(), ("Security", "Security"))
            self.assertEqual(
                set(detail[cols.CLASSIFICATION_NAME].to_list()),
                {"United Kingdom", "United States"},
            )

    def test_portfolio_convenience_method_rejects_different_classifications(self) -> None:
        """Default Axys attribution requires matching portfolio classifications."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio("P1", classification_name="Country")
            benchmark = data.get_portfolio("P2", classification_name="Sector")

            with self.assertRaises(PparError):
                portfolio.to_analytics(benchmark)

    def test_portfolio_convenience_method_requires_overlapping_periods(self) -> None:
        """Analytics raises its normal error when Axys portfolios do not overlap."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio(
                "P1",
                from_date=dt.date(2024, 2, 1),
                thru_date=dt.date(2024, 2, 29),
                classification_name="Country",
            )
            benchmark = data.get_portfolio(
                "P2",
                from_date=dt.date(2024, 1, 1),
                thru_date=dt.date(2024, 1, 31),
                classification_name="Country",
            )

            with self.assertRaises(PparError):
                portfolio.to_analytics(benchmark)

    def test_required_classification_sources_requires_attached_sources(self) -> None:
        """Required classification access fails when none were requested."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio("P1")

            with self.assertRaises(PparError) as context:
                _ = portfolio.required_classification_sources

            self.assertIn("classification", str(context.exception).lower())

    def test_source_path_overrides_replace_configured_defaults(self) -> None:
        """Constructor overrides can replace configured classification files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification_path = _write_axys_inputs(directory)
            pl.DataFrame(
                {
                    "CODE": ["TECH", "DEF", "CASH"],
                    "DESCRIPTION": ["Growth Sector", "Defensive Sector", "Cash"],
                    "TYPE": ["SECTOR", "SECTOR", "SECTOR"],
                }
            ).write_csv(directory / "alternate_classifications.csv")
            data = AxysData(
                specification_path,
                source_path_overrides={
                    "SectorLookup": directory / "alternate_classifications.csv"
                },
            )
            portfolio = data.get_portfolio("P1")

            sources = data.get_classification_sources("SectorLookup", portfolio)

            self.assertEqual(sources.classification_name, "Sector")
            self.assertEqual(
                sources.classification_data_source[cols.NAME].sort().to_list(),
                ["Cash", "Defensive Sector", "Growth Sector"],
            )

    def test_security_classification_sources_do_not_include_mapping(self) -> None:
        """Security-grain Axys classifications do not need mapping sources."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio("P1")

            sources = data.get_classification_sources("Security", portfolio)

            self.assertEqual(sources.classification_name, "Security")
            self.assertIsNone(sources.mapping_data_sources)
            self.assertEqual(
                sources.classification_data_source[cols.IDENTIFIER].sort().to_list(),
                ["A", "B"],
            )

    def test_security_master_backed_classification_uses_mapping_column(self) -> None:
        """Security-master classifications can inherit path and identifier fields."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio("P1")

            sources = data.get_classification_sources("Sector", portfolio)

            self.assertIsNotNone(sources.mapping_data_sources)
            self.assertEqual(
                sources.classification_data_source[cols.IDENTIFIER].sort().to_list(),
                ["CASH", "DEF", "OTHER", "TECH"],
            )
            self.assertEqual(
                sources.classification_data_source[cols.NAME].sort().to_list(),
                ["Cash", "Defensive", "Other", "Technology"],
            )

    def test_sector_and_sector_lookup_generate_same_attribution(self) -> None:
        """Security-master and lookup-table sector sources produce identical output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = AxysData(_write_axys_inputs(Path(temp_dir)))
            portfolio = data.get_portfolio("P1")
            analytics = Analytics(
                portfolio.security_performance,
                portfolio_name=portfolio.portfolio_name,
                portfolio_classification_name="Security",
            )

            sector_sources = data.get_classification_sources("Sector", portfolio)
            lookup_sources = data.get_classification_sources("SectorLookup", portfolio)
            sector_detail = analytics.attribution(
                sector_sources.classification_name,
                sector_sources.classification_data_source,
                sector_sources.mapping_data_sources,
            ).to_polars(View.SUBPERIOD_ATTRIBUTION)
            lookup_detail = analytics.attribution(
                lookup_sources.classification_name,
                lookup_sources.classification_data_source,
                lookup_sources.mapping_data_sources,
            ).to_polars(View.SUBPERIOD_ATTRIBUTION)

            self.assertEqual(sector_sources.classification_name, "Sector")
            self.assertEqual(lookup_sources.classification_name, "Sector")
            self.assertTrue(sector_detail.equals(lookup_detail))


if __name__ == "__main__":
    unittest.main()
