"""Focused in-memory tests for Analytics orchestration and attribution views."""

# Python Imports
import datetime as dt
from collections.abc import Sequence
import unittest
from unittest import mock

# Third-Party Imports
import polars as pl

# Project Imports
from ppar import Analytics
from ppar.attribution import Attribution, View
from ppar.frequency import Frequency
from ppar.performance import Performance
from ppar.utilities import MappingDataSource
import ppar.schema as cols
from ppar.errors import PparError


_PERIODS = [
    (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
    (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
    (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
]


def _two_asset_performance() -> pl.DataFrame:
    """Return three periods of narrow-format performance data."""
    return pl.DataFrame(
        {
            cols.FROM_DATE: [period[0] for period in _PERIODS for _ in ("A", "B")],
            cols.THRU_DATE: [period[1] for period in _PERIODS for _ in ("A", "B")],
            cols.IDENTIFIER: ["A", "B"] * len(_PERIODS),
            cols.RETURN: [0.10, -0.05, 0.03, 0.02, -0.02, 0.04],
            cols.WEIGHT: [0.60, 0.40] * len(_PERIODS),
        }
    )


class TestAnalyticsContracts(unittest.TestCase):
    """Verify public orchestration behavior without external test data files."""

    def test_missing_benchmark_defaults_to_portfolio_classification_and_results(self) -> None:
        """A portfolio-only Analytics instance uses itself as its benchmark."""
        analytics = Analytics(
            _two_asset_performance(),
            portfolio_classification_name="Security",
        )

        attribution = analytics.attribution()
        summary = attribution.to_polars(View.SUBPERIOD_SUMMARY)

        self.assertEqual(analytics.classification_names(), ("Security", "Security"))
        self.assertTrue((summary[cols.ACTIVE_RETURN] == 0.0).all())
        self.assertTrue((summary[cols.TOTAL_EFFECT_SIMPLE] == 0.0).all())

    def test_date_window_keeps_only_periods_within_requested_bounds(self) -> None:
        """Date parameters constrain the aligned reportable periods."""
        analytics = Analytics(
            _two_asset_performance(),
            from_date="2024-02-01",
            thru_date=dt.date(2024, 3, 31),
        )

        summary = analytics.attribution().to_polars(View.SUBPERIOD_SUMMARY)

        self.assertEqual(
            summary[cols.FROM_DATE].to_list(),
            [dt.date(2024, 2, 1), dt.date(2024, 3, 1)],
        )
        self.assertEqual(
            summary[cols.THRU_DATE].to_list(),
            [dt.date(2024, 2, 29), dt.date(2024, 3, 31)],
        )

    def test_different_known_classifications_require_requested_target(self) -> None:
        """A caller must choose a target classification for unlike inputs."""
        analytics = Analytics(
            _two_asset_performance(),
            _two_asset_performance(),
            portfolio_classification_name="Security",
            benchmark_classification_name="Sector",
        )

        with self.assertRaises(PparError):
            analytics.attribution()

    def test_repeated_attribution_retrieval_reuses_cached_instance(self) -> None:
        """Repeated requests for a classification reuse calculated attribution."""
        analytics = Analytics(
            _two_asset_performance(),
            portfolio_classification_name="Security",
        )

        first = analytics.attribution()
        second = analytics.attribution()

        self.assertIs(first, second)

    def test_mapping_sources_require_exact_portfolio_benchmark_pair(self) -> None:
        """Mapping setup rejects missing and silently ignored extra sources."""
        analytics = Analytics(
            _two_asset_performance(),
            portfolio_classification_name="Security",
        )
        invalid_sources: tuple[Sequence[MappingDataSource | None], ...] = (
            (),
            (pl.DataFrame({"from": ["A"], "to": ["TECH"]}),),
            (None, None, None),
        )
        for mapping_sources in invalid_sources:
            with self.subTest(length=len(mapping_sources)):
                with self.assertRaises(PparError):
                    analytics.attribution(
                        "Sector",
                        mapping_data_sources=mapping_sources,
                    )

    def test_detail_view_zero_fills_identifier_missing_from_benchmark(self) -> None:
        """Attribution aligns asymmetric holdings on one classification grid."""
        portfolio = _two_asset_performance().head(2)
        benchmark = portfolio.filter(pl.col(cols.IDENTIFIER) == "A").with_columns(
            pl.lit(1.0).alias(cols.WEIGHT)
        )

        detail = Analytics(portfolio, benchmark).attribution().to_polars(
            View.SUBPERIOD_ATTRIBUTION
        )
        b_row = detail.filter(pl.col(cols.CLASSIFICATION_IDENTIFIER) == "B")

        self.assertEqual(b_row.height, 1)
        self.assertEqual(b_row[cols.BENCHMARK_WEIGHT].item(), 0.0)
        self.assertEqual(b_row[cols.BENCHMARK_RETURN].item(), 0.0)
        self.assertEqual(b_row[cols.BENCHMARK_CONTRIB_SIMPLE].item(), 0.0)

    def test_detail_view_zero_fills_identifiers_missing_in_individual_periods(self) -> None:
        """Alignment preserves contributions when identifier membership changes."""
        portfolio = pl.DataFrame(
            {
                cols.FROM_DATE: [
                    dt.date(2024, 1, 1),
                    dt.date(2024, 1, 1),
                    dt.date(2024, 2, 1),
                ],
                cols.THRU_DATE: [
                    dt.date(2024, 1, 31),
                    dt.date(2024, 1, 31),
                    dt.date(2024, 2, 29),
                ],
                cols.IDENTIFIER: ["A", "B", "A"],
                cols.RETURN: [0.02, 0.10, 0.03],
                cols.WEIGHT: [0.50, 0.50, 1.0],
            }
        )
        benchmark = pl.DataFrame(
            {
                cols.FROM_DATE: [
                    dt.date(2024, 1, 1),
                    dt.date(2024, 2, 1),
                    dt.date(2024, 2, 1),
                ],
                cols.THRU_DATE: [
                    dt.date(2024, 1, 31),
                    dt.date(2024, 2, 29),
                    dt.date(2024, 2, 29),
                ],
                cols.IDENTIFIER: ["A", "A", "B"],
                cols.RETURN: [0.01, 0.01, 0.04],
                cols.WEIGHT: [1.0, 0.50, 0.50],
            }
        )

        summary = Analytics(portfolio, benchmark).attribution().to_polars(
            View.SUBPERIOD_SUMMARY
        )

        self.assertEqual(
            summary[cols.PORTFOLIO_RETURN].round(12).to_list(),
            [0.06, 0.03],
        )
        self.assertEqual(
            summary[cols.BENCHMARK_RETURN].round(12).to_list(),
            [0.01, 0.025],
        )
        self.assertEqual(
            summary[cols.PORTFOLIO_CONTRIB_SIMPLE].round(12).to_list(),
            [0.06, 0.03],
        )
        self.assertEqual(
            summary[cols.BENCHMARK_CONTRIB_SIMPLE].round(12).to_list(),
            [0.01, 0.025],
        )

    def test_consolidated_detail_displays_return_used_for_contribution(self) -> None:
        """Displayed consolidated returns use the contribution calculation basis."""
        periods = (
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
            (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
        )
        performance = pl.DataFrame(
            {
                cols.FROM_DATE: [period[0] for period in periods for _ in range(2)],
                cols.THRU_DATE: [period[1] for period in periods for _ in range(2)],
                cols.IDENTIFIER: ["A", "B"] * len(periods),
                cols.RETURN: [0.10, -0.05] * len(periods),
                cols.WEIGHT: [0.50, 0.50] * len(periods),
            }
        )

        details = Analytics(
            performance,
            performance.clone(),
            frequency=Frequency.QUARTERLY,
        ).attribution().to_polars(View.SUBPERIOD_ATTRIBUTION)

        calculated_contributions = (
            details[cols.PORTFOLIO_WEIGHT] * details[cols.PORTFOLIO_RETURN]
        )
        self.assertTrue(
            details[cols.PORTFOLIO_CONTRIB_SIMPLE]
            .round(12)
            .equals(calculated_contributions.round(12))
        )

    def test_attribution_is_audited_when_created(self) -> None:
        """Normal attribution construction executes production invariants."""
        with mock.patch.object(Attribution, "audit", autospec=True) as audit:
            attribution = Analytics(_two_asset_performance()).attribution()

        audit.assert_called_once_with(attribution)

    def test_attribution_does_not_mutate_caller_performances(self) -> None:
        """Identifier alignment operates on attribution-owned calculation copies."""
        portfolio = Performance(_two_asset_performance().head(2))
        benchmark = Performance(
            _two_asset_performance()
            .head(2)
            .filter(pl.col(cols.IDENTIFIER) == "A")
            .with_columns(pl.lit(1.0).alias(cols.WEIGHT))
        )
        portfolio_before = portfolio.narrow_df.clone()
        benchmark_before = benchmark.narrow_df.clone()

        Attribution(
            (portfolio, benchmark),
            classification_name=None,
            classification_data_source=None,
            frequency=Frequency.AS_OFTEN_AS_POSSIBLE,
        )

        self.assertTrue(portfolio.narrow_df.equals(portfolio_before))
        self.assertTrue(benchmark.narrow_df.equals(benchmark_before))

    def test_total_rows_are_appended_only_to_aggregate_views(self) -> None:
        """Cumulative and overall views end in totals; detail views do not."""
        attribution = Analytics(_two_asset_performance()).attribution()

        cumulative = attribution.to_polars(View.CUMULATIVE_ATTRIBUTION)
        overall = attribution.to_polars(View.OVERALL_ATTRIBUTION)
        summary = attribution.to_polars(View.SUBPERIOD_SUMMARY)
        detail = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

        self.assertEqual(cumulative.schema[cols.THRU_DATE], pl.Date)
        self.assertIsNone(cumulative[cols.THRU_DATE].item(-1))
        self.assertIn(">Total<", attribution.to_html(View.CUMULATIVE_ATTRIBUTION))
        self.assertEqual(overall[cols.CLASSIFICATION_NAME].item(-1), "Total")
        self.assertEqual(summary.height, len(_PERIODS))
        self.assertEqual(detail.height, 2 * len(_PERIODS))

    def test_schema_column_groups_are_immutable(self) -> None:
        """Shared schema groupings cannot be changed by package consumers."""
        for grouping in (
            cols.DATE_COLUMNS,
            cols.CLASSIFICATION_COLUMNS,
            cols.VIEW_SUBPERIOD_ATTRIBUTION_COLUMNS,
        ):
            self.assertIsInstance(grouping, tuple)

    def test_overall_sorting_leaves_total_row_at_end(self) -> None:
        """Sorting orders holdings before the appended overall total row."""
        attribution = Analytics(_two_asset_performance()).attribution()

        overall = attribution.to_polars(
            View.OVERALL_ATTRIBUTION,
            columns_to_sort=cols.PORTFOLIO_CONTRIB_SMOOTHED,
            sort_descendings=True,
        )
        values = overall[cols.PORTFOLIO_CONTRIB_SMOOTHED][:-1].to_list()

        self.assertEqual(overall[cols.CLASSIFICATION_NAME].item(-1), "Total")
        self.assertEqual(values, sorted(values, reverse=True))


if __name__ == "__main__":
    unittest.main()
