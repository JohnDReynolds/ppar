"""Focused tests for the AxysData-to-Analytics pipeline using temporary inputs."""

# Python Imports
import datetime as dt
import inspect
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

# Third-Party Imports
import polars as pl

# Project Imports
from ppar.attribution import View
from ppar.axys_apx import AxysClassificationSources, AxysData, AxysPortfolio
from ppar.axys_apx.supporting_sources import combine_classification_sources
import ppar.schema as cols
from ppar.errors import PparError
from ppar.frequency import Frequency


def _write_axys_inputs(directory: Path) -> dict[str, object]:
    """Write minimal Axys-like sources and return their Python settings."""
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
    return specification


def _axys_data(
    directory: Path,
    values: dict[str, object] | None = None,
) -> AxysData:
    """Return an Axys loader for temporary test inputs."""
    source_values = _write_axys_inputs(directory) if values is None else values
    return AxysData(directory, source_values)


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

    def test_axys_data_constructor_has_focused_source_options(self) -> None:
        """AxysData exposes performance overrides but no lookup-file override map."""
        self.assertEqual(
            tuple(inspect.signature(AxysData).parameters),
            (
                "base_directory",
                "values",
                "portfolio_performance_path",
                "security_performance_path",
            ),
        )

    def test_load_reconciles_weights_and_filters_security_sources(self) -> None:
        """Selected security sources and performance are ready for Analytics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))

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
                specification = _write_axys_inputs(directory)
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
                    portfolio = _axys_data(directory, specification).get_portfolio("P1")
                    portfolio.to_analytics(frequency=Frequency.QUARTERLY)

                message = str(context.exception)
                self.assertIn("P1", message)
                self.assertIn("2024-02-01", message)
                self.assertIn("2024-02-29", message)

    def test_constructor_does_not_load_portfolios(self) -> None:
        """Constructing AxysData leaves portfolio loading to get_portfolio."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))

            self.assertFalse(hasattr(data, "portfolios"))
            self.assertFalse(hasattr(data, "classification_data_sources"))
            self.assertFalse(hasattr(data, "mapping_data_sources"))

    def test_get_portfolio_loads_requested_portfolio(self) -> None:
        """Portfolio loading returns reconciled output for a requested code."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
            portfolio = data.get_portfolio("P2")

            self.assertEqual(portfolio.portfolio_code, "P2")
            self.assertEqual(portfolio.portfolio_name, "P2 - Income")

    def test_get_portfolios_scans_each_performance_source_once(self) -> None:
        """A portfolio and benchmark share one scan of each performance CSV."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
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
            data = _axys_data(Path(temp_dir))
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
            data = _axys_data(Path(temp_dir))
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
            specification = _write_axys_inputs(directory)
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
            del _file_definition(specification, "portfolio_performance")["columns"]
            del _file_definition(specification, "security_performance")["columns"]

            data = _axys_data(directory, specification)
            portfolio = data.get_portfolio("P1")

            self.assertEqual(portfolio.portfolio_name, "P1 - Growth")
            self.assertEqual(portfolio.security_performance.height, 4)

    def test_composite_security_id_joins_performance_and_security_master(self) -> None:
        """Analytics shares type-first composite identity across its sources."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
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

            data = _axys_data(directory, specification)
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
        """Configured performance columns ignore unrelated headings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
            portperf_path = directory / "portperf.csv"
            (
                pl.read_csv(portperf_path)
                .with_columns(
                    pl.lit(0.99).alias("RET"),
                    pl.lit(0.88).alias("RETURN"),
                )
                .write_csv(portperf_path)
            )

            data = _axys_data(directory, specification)
            portfolio = data.get_portfolio("P1")

            self.assertEqual(portfolio.portfolio_name, "P1 - Growth")
            self.assertEqual(portfolio.security_performance.height, 4)

    def test_security_master_columns_default_to_exact_normalized_names(self) -> None:
        """Security-master mappings may be omitted for normalized headers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
            pl.read_csv(directory / "security_master.csv").rename(
                {
                    "SECURITY_ID": "security_id",
                    "SECURITY_NAME": "security_name",
                }
            ).write_csv(directory / "security_master.csv")
            del _file_definition(specification, "security_master")["columns"]

            data = _axys_data(directory, specification)
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
            specification = _write_axys_inputs(directory)
            (directory / "security_master.csv").rename(directory / "secmast.csv")
            del _file_definition(specification, "security_master")["path"]

            data = _axys_data(directory, specification)
            portfolio = data.get_portfolio("P1")
            sources = data.get_classification_sources("Security", portfolio)

            self.assertEqual(sources.classification_data_source.height, 2)

    def test_explicit_security_master_mapping_ignores_other_columns(self) -> None:
        """Configured security-master columns ignore unrelated headings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
            security_master_path = directory / "security_master.csv"
            (
                pl.read_csv(security_master_path)
                .with_columns(pl.lit("Wrong Alias").alias("NAME"))
                .write_csv(security_master_path)
            )

            data = _axys_data(directory, specification)
            portfolio = data.get_portfolio("P1")
            sources = data.get_classification_sources("Security", portfolio)

            self.assertEqual(
                sources.classification_data_source[cols.NAME].sort().to_list(),
                ["Alpha", "Beta"],
            )

    def test_date_filters_apply_before_returning_portfolio_performance(self) -> None:
        """Axys lower bounds before, at, and inside a period use its thru date."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
            for from_date in (
                dt.date(2023, 12, 31),
                dt.date(2024, 1, 31),
                dt.date(2024, 1, 15),
            ):
                with self.subTest(from_date=from_date):
                    portfolio = data.get_portfolio("P1", from_date=from_date)
                    self.assertEqual(
                        portfolio.security_performance[cols.THRU_DATE]
                        .unique()
                        .sort()
                        .to_list(),
                        [dt.date(2024, 1, 31), dt.date(2024, 2, 29)],
                    )

    def test_get_portfolio_loads_one_requested_portfolio(self) -> None:
        """Lazy portfolio loading returns one reconciled portfolio by code."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))

            portfolio = data.get_portfolio("P1")

            self.assertEqual(portfolio.portfolio_code, "P1")
            self.assertEqual(portfolio.portfolio_name, "P1 - Growth")
            self.assertEqual(portfolio.security_performance.height, 4)

    def test_get_portfolio_applies_date_filters(self) -> None:
        """Lazy portfolio loading accepts its own date window."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))

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

    def test_latest_portfolio_name_is_independent_of_source_row_order(self) -> None:
        """A chronological rename determines portfolio and report display names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
            portfolio_path = directory / "portperf.csv"
            source = pl.read_csv(portfolio_path).with_columns(
                pl.when(
                    (pl.col("PORTFOLIO_CODE") == "P1")
                    & (pl.col("THRU_DATE") == "2024-01-31")
                )
                .then(pl.lit("Growth Legacy"))
                .when(
                    (pl.col("PORTFOLIO_CODE") == "P1")
                    & (pl.col("THRU_DATE") == "2024-02-29")
                )
                .then(pl.lit("Growth Current"))
                .otherwise(pl.col("PORTFOLIO_NAME"))
                .alias("PORTFOLIO_NAME")
            )
            loaded_outputs: list[pl.DataFrame] = []

            for reversed_rows, source_rows in (
                (False, source),
                (True, source.reverse()),
            ):
                with self.subTest(reversed=reversed_rows):
                    source_rows.write_csv(portfolio_path)
                    data = _axys_data(directory, specification)
                    portfolio = data.get_portfolio("P1")
                    attribution = portfolio.to_analytics().attribution_for(
                        data.get_classification_sources("Sector", portfolio)
                    )
                    output = attribution.to_polars(View.OVERALL_ATTRIBUTION)
                    html = attribution.to_html(View.OVERALL_ATTRIBUTION)

                    self.assertEqual(portfolio.portfolio_name, "P1 - Growth Current")
                    self.assertIn("P1 - Growth Current", html)
                    loaded_outputs.append(output)

            self.assertTrue(loaded_outputs[0].equals(loaded_outputs[1]))

    def test_portfolio_name_uses_latest_retained_period_for_each_code(self) -> None:
        """Date filtering and account selection independently determine names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
            portfolio_path = directory / "portperf.csv"
            source = pl.read_csv(portfolio_path).with_columns(
                pl.when(
                    (pl.col("PORTFOLIO_CODE") == "P1")
                    & (pl.col("THRU_DATE") == "2024-01-31")
                )
                .then(pl.lit("Growth Legacy"))
                .when(
                    (pl.col("PORTFOLIO_CODE") == "P1")
                    & (pl.col("THRU_DATE") == "2024-02-29")
                )
                .then(pl.lit("Growth Current"))
                .otherwise(pl.col("PORTFOLIO_NAME"))
                .alias("PORTFOLIO_NAME")
            )
            source.reverse().write_csv(portfolio_path)
            data = _axys_data(directory, specification)

            full_portfolios = data.get_portfolios(("P1", "P2"))
            january_portfolio = data.get_portfolio(
                "P1",
                thru_date=dt.date(2024, 1, 31),
            )

            self.assertEqual(full_portfolios["P1"].portfolio_name, "P1 - Growth Current")
            self.assertEqual(full_portfolios["P2"].portfolio_name, "P2 - Income")
            self.assertEqual(january_portfolio.portfolio_name, "P1 - Growth Legacy")

    def test_portfolio_dates_and_classification_sources_are_selected_explicitly(
        self,
    ) -> None:
        """Date filtering and classification loading remain separate choices."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
            data = _axys_data(directory, specification)

            portfolio = data.get_portfolio(
                "P1",
                from_date=dt.date(2024, 1, 1),
                thru_date=dt.date(2024, 1, 31),
            )

            sources = data.get_classification_sources("Sector", portfolio)
            self.assertEqual(portfolio.security_performance.height, 2)
            self.assertEqual(
                portfolio.security_performance[cols.THRU_DATE].unique().to_list(),
                [dt.date(2024, 1, 31)],
            )
            self.assertEqual(sources.classification_name, "Sector")

    def test_axys_sources_roll_up_through_analytics_to_sector_attribution(self) -> None:
        """Generated classification and mapping sources drive public attribution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
            portfolio = data.get_portfolio("P1")

            analytics = portfolio.to_analytics()
            attribution = analytics.attribution_for(
                data.get_classification_sources("Sector", portfolio)
            )
            detail = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

            self.assertEqual(
                set(detail[cols.CLASSIFICATION_NAME].to_list()),
                {"Defensive", "Technology"},
            )
            self.assertTrue((detail[cols.ACTIVE_RETURN] == 0.0).all())
            self.assertTrue((detail[cols.TOTAL_EFFECT_SIMPLE] == 0.0).all())

    def test_get_classification_sources_loads_requested_classification(self) -> None:
        """Classification loading is explicit and separate from portfolio loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))

            portfolio = data.get_portfolio("P1")

            sources = data.get_classification_sources("Sector", portfolio)
            self.assertEqual(sources.classification_name, "Sector")
            self.assertIsNotNone(sources.mapping_data_sources)
            self.assertEqual(
                sources.classification_data_source[cols.NAME].sort().to_list(),
                ["Cash", "Defensive", "Other", "Technology"],
            )

    def test_portfolio_only_attribution_names_its_sources_explicitly(self) -> None:
        """Portfolio-only Axys attribution identifies its classification source."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
            portfolio = data.get_portfolio("P1")

            analytics = portfolio.to_analytics()
            attribution = analytics.attribution_for(
                data.get_classification_sources("Sector", portfolio)
            )
            detail = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

            self.assertEqual(
                set(detail[cols.CLASSIFICATION_NAME].to_list()),
                {"Defensive", "Technology"},
            )

    def test_portfolio_and_benchmark_attribution_names_paired_sources(self) -> None:
        """Axys benchmark attribution identifies its paired sources explicitly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
            portfolio = data.get_portfolio("P1")
            benchmark = data.get_portfolio("P2")

            analytics = portfolio.to_analytics(benchmark)
            attribution = analytics.attribution_for(
                data.get_classification_sources_for_pair(
                    "Country",
                    portfolio,
                    benchmark,
                )
            )
            detail = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

            self.assertEqual(
                set(detail[cols.CLASSIFICATION_NAME].to_list()),
                {"United Kingdom", "United States"},
            )

    def test_one_portfolio_pair_can_produce_multiple_explicit_classifications(
        self,
    ) -> None:
        """One loaded pair supports independently selected attribution sources."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
            portfolio = data.get_portfolio("P1")
            benchmark = data.get_portfolio("P2")
            analytics = portfolio.to_analytics(benchmark)

            country = analytics.attribution_for(
                data.get_classification_sources_for_pair(
                    "Country", portfolio, benchmark
                )
            )
            sector = analytics.attribution_for(
                data.get_classification_sources_for_pair(
                    "Sector", portfolio, benchmark
                )
            )

            country_names = set(
                country.to_polars(View.SUBPERIOD_ATTRIBUTION)[
                    cols.CLASSIFICATION_NAME
                ].to_list()
            )
            sector_names = set(
                sector.to_polars(View.SUBPERIOD_ATTRIBUTION)[
                    cols.CLASSIFICATION_NAME
                ].to_list()
            )
            self.assertEqual(country_names, {"United Kingdom", "United States"})
            self.assertEqual(sector_names, {"Cash", "Defensive", "Technology"})

    def test_portfolio_convenience_method_requires_overlapping_periods(self) -> None:
        """Analytics raises its normal error when Axys portfolios do not overlap."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
            portfolio = data.get_portfolio(
                "P1",
                from_date=dt.date(2024, 2, 1),
                thru_date=dt.date(2024, 2, 29),
            )
            benchmark = data.get_portfolio(
                "P2",
                from_date=dt.date(2024, 1, 1),
                thru_date=dt.date(2024, 1, 31),
            )

            with self.assertRaises(PparError):
                portfolio.to_analytics(benchmark)

    def test_portfolio_analytics_options_are_keyword_only(self) -> None:
        """Only the optional benchmark remains positional in the convenience API."""
        parameters = inspect.signature(AxysPortfolio.to_analytics).parameters

        self.assertEqual(
            parameters["benchmark_data_source"].kind,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        for name in tuple(parameters)[2:]:
            with self.subTest(name=name):
                self.assertEqual(
                    parameters[name].kind,
                    inspect.Parameter.KEYWORD_ONLY,
                )

    def test_portfolio_does_not_carry_hidden_classification_sources(self) -> None:
        """Reconciled portfolios contain performance rather than report choices."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
            portfolio = data.get_portfolio("P1")

            self.assertFalse(hasattr(portfolio, "classification_sources"))

    def test_security_classification_sources_do_not_include_mapping(self) -> None:
        """Security-grain Axys classifications do not need mapping sources."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data = _axys_data(Path(temp_dir))
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
            data = _axys_data(Path(temp_dir))
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

    def test_axys_sources_accept_exact_duplicate_pairs(self) -> None:
        """Repeated identical security-master rows do not make sources ambiguous."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
            security_master_path = directory / "security_master.csv"
            security_master = pl.read_csv(security_master_path)
            duplicated = pl.concat((security_master, security_master.head(1)))
            for source_rows in (duplicated, duplicated.reverse()):
                with self.subTest(reversed=source_rows["SECURITY_ID"].item(0) != "A"):
                    source_rows.write_csv(security_master_path)
                    data = _axys_data(directory, specification)
                    portfolio = data.get_portfolio("P1")
                    sources = data.get_classification_sources("Security", portfolio)

                    self.assertEqual(
                        sources.classification_data_source[cols.IDENTIFIER]
                        .sort()
                        .to_list(),
                        ["A", "B"],
                    )

    def test_axys_classification_rejects_conflicting_display_names(self) -> None:
        """One grouping code cannot have two security-master display names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
            security_master_path = directory / "security_master.csv"
            security_master = pl.read_csv(security_master_path)
            conflicting = security_master.head(1).with_columns(
                pl.lit("D").alias("SECURITY_ID"),
                pl.lit("Technology Alternate").alias("SECTOR_DESC"),
            )
            conflict_rows = pl.concat((security_master, conflicting))
            for source_rows in (conflict_rows, conflict_rows.reverse()):
                with self.subTest(first_id=source_rows["SECURITY_ID"].item(0)):
                    source_rows.write_csv(security_master_path)
                    data = _axys_data(directory, specification)
                    portfolio = data.get_portfolio("P1")

                    with self.assertRaisesRegex(PparError, "conflicting values.*TECH"):
                        data.get_classification_sources("Sector", portfolio)

    def test_axys_mapping_rejects_conflicting_destinations(self) -> None:
        """One security cannot map to two grouping codes in the same source."""
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            specification = _write_axys_inputs(directory)
            security_master_path = directory / "security_master.csv"
            security_master = pl.read_csv(security_master_path)
            conflicting = security_master.head(1).with_columns(
                pl.lit("DEF").alias("SECTOR_CODE"),
                pl.lit("Defensive").alias("SECTOR_DESC"),
            )
            conflict_rows = pl.concat((security_master, conflicting))
            for source_rows in (conflict_rows, conflict_rows.reverse()):
                with self.subTest(first_id=source_rows["SECURITY_ID"].item(0)):
                    source_rows.write_csv(security_master_path)
                    data = _axys_data(directory, specification)
                    portfolio = data.get_portfolio("P1")

                    with self.assertRaisesRegex(PparError, "conflicting values.*A"):
                        data.get_classification_sources("Sector", portfolio)

    def test_combined_axys_sources_reject_conflicting_names_regardless_of_order(
        self,
    ) -> None:
        """Portfolio/benchmark source order cannot select a grouping display name."""
        first = AxysClassificationSources(
            "Sector",
            pl.DataFrame({cols.IDENTIFIER: ["TECH"], cols.NAME: ["Technology"]}),
            None,
        )
        second = AxysClassificationSources(
            "Sector",
            pl.DataFrame(
                {cols.IDENTIFIER: ["TECH"], cols.NAME: ["Technology Alternate"]}
            ),
            None,
        )

        exact_duplicates = combine_classification_sources(first, first)
        self.assertEqual(exact_duplicates.classification_data_source.height, 1)

        for portfolio_sources, benchmark_sources in ((first, second), (second, first)):
            with self.subTest(portfolio_name=portfolio_sources.classification_name):
                with self.assertRaisesRegex(PparError, "conflicting values.*TECH"):
                    combine_classification_sources(
                        portfolio_sources,
                        benchmark_sources,
                    )

if __name__ == "__main__":
    unittest.main()
