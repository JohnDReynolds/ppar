"""Focused in-memory tests for core performance and attribution calculations."""

# Python Imports
import datetime as dt
import math
import unittest

# Third-Party Imports
import polars as pl

# Project Imports
from ppar import Analytics
from ppar.attribution import View
import ppar.schema as cols
from ppar.errors import PparError
from ppar.frequency import Frequency
from ppar.performance import Performance
from tests import helpers as test_util


class TestCalculationInvariants(unittest.TestCase):
    """Test small financial identities without external data files."""

    def test_single_asset_total_return_equals_asset_return(self) -> None:
        """A fully invested single asset contributes its entire return."""
        performance = Performance(
            test_util.make_performance_df(
                [(dt.date(2024, 1, 1), dt.date(2024, 1, 31))],
                {"A": ([0.0375], [1.0])},
            )
        )

        self.assertTrue(
            math.isclose(
                performance.period_totals()[cols.TOTAL_RETURN].item(), 0.0375, abs_tol=1e-12
            )
        )
        self.assertTrue(
            math.isclose(performance.narrow_df[cols.CONTRIBUTION].item(), 0.0375, abs_tol=1e-12)
        )

    def test_two_asset_total_return_equals_sum_of_contributions(self) -> None:
        """A period total return is the weighted sum of asset returns."""
        performance = Performance(
            test_util.make_performance_df(
                [(dt.date(2024, 1, 1), dt.date(2024, 1, 31))],
                {
                    "A": ([0.10], [0.60]),
                    "B": ([-0.05], [0.40]),
                },
            )
        )

        contributions = performance.narrow_df[cols.CONTRIBUTION].sum()
        self.assertTrue(math.isclose(contributions, 0.04, abs_tol=1e-12))
        self.assertTrue(
            math.isclose(
                performance.period_totals()[cols.TOTAL_RETURN].item(),
                contributions,
                abs_tol=1e-12,
            )
        )

    def test_long_short_fully_invested_portfolio_reconciles(self) -> None:
        """Gross exposures above one reconcile when net weights equal one."""
        performance = Performance(
            test_util.make_performance_df(
                [(dt.date(2024, 1, 1), dt.date(2024, 1, 31))],
                {
                    "Long": ([0.10], [1.20]),
                    "Short": ([0.05], [-0.20]),
                },
            )
        )

        contributions = dict(
            zip(
                performance.narrow_df[cols.IDENTIFIER],
                performance.narrow_df[cols.CONTRIBUTION],
            )
        )
        self.assertTrue(math.isclose(contributions["Long"], 0.12, abs_tol=1e-12))
        self.assertTrue(math.isclose(contributions["Short"], -0.01, abs_tol=1e-12))
        self.assertTrue(
            math.isclose(
                performance.period_totals()[cols.TOTAL_RETURN].item(), 0.11, abs_tol=1e-12
            )
        )
        performance.audit()

    def test_identical_portfolio_and_benchmark_have_zero_active_effects(self) -> None:
        """Identical inputs have no active return or attribution effects."""
        periods = [
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
        ]
        df = test_util.make_performance_df(
            periods,
            {
                "A": ([0.08, -0.01], [0.60, 0.55]),
                "B": ([-0.02, 0.04], [0.40, 0.45]),
            },
        )
        attribution = Analytics(df, df).attribution()

        subperiods = attribution.to_polars(View.SUBPERIOD_SUMMARY)
        for column in (
            cols.ACTIVE_RETURN,
            cols.ALLOCATION_EFFECT_SIMPLE,
            cols.SELECTION_EFFECT_SIMPLE,
        ):
            self.assertTrue(
                all(math.isclose(value, 0.0, abs_tol=1e-12) for value in subperiods[column])
            )

    def test_reported_selection_combines_three_effect_selection_and_interaction(
        self,
    ) -> None:
        """Portfolio-weighted selection equals conventional selection plus interaction."""
        periods = [(dt.date(2024, 1, 1), dt.date(2024, 1, 31))]
        portfolio = test_util.make_performance_df(
            periods,
            {
                "A": ([0.10], [0.70]),
                "B": ([0.02], [0.30]),
            },
        )
        benchmark = test_util.make_performance_df(
            periods,
            {
                "A": ([0.06], [0.40]),
                "B": ([0.02], [0.60]),
            },
        )

        detail = (
            Analytics(portfolio, benchmark)
            .attribution()
            .to_polars(View.SUBPERIOD_ATTRIBUTION)
            .filter(pl.col(cols.CLASSIFICATION_IDENTIFIER) == "A")
        )
        portfolio_weight = 0.70
        benchmark_weight = 0.40
        active_group_return = 0.10 - 0.06
        conventional_selection = benchmark_weight * active_group_return
        conventional_interaction = (
            portfolio_weight - benchmark_weight
        ) * active_group_return

        self.assertAlmostEqual(
            detail[cols.SELECTION_EFFECT_SIMPLE].item(),
            conventional_selection + conventional_interaction,
        )
        self.assertAlmostEqual(
            detail[cols.SELECTION_EFFECT_SIMPLE].item(),
            portfolio_weight * active_group_return,
        )
        self.assertNotIn("Interaction_Effect_Simple", detail.columns)

    def test_overall_smoothed_effects_reconcile_to_active_return(self) -> None:
        """Linked attribution effects reconcile to linked active return."""
        periods = [
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
            (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
        ]
        portfolio = test_util.make_performance_df(
            periods,
            {
                "A": ([0.08, -0.01, 0.03], [0.70, 0.55, 0.60]),
                "B": ([-0.02, 0.05, 0.01], [0.30, 0.45, 0.40]),
            },
        )
        benchmark = test_util.make_performance_df(
            periods,
            {
                "A": ([0.06, 0.01, 0.02], [0.50, 0.50, 0.50]),
                "B": ([0.00, 0.03, -0.01], [0.50, 0.50, 0.50]),
            },
        )

        overall = Analytics(portfolio, benchmark).attribution().to_polars(
            View.OVERALL_ATTRIBUTION
        )
        total_row = overall[-1]

        self.assertTrue(
            math.isclose(
                total_row[cols.TOTAL_EFFECT_SMOOTHED].item(),
                total_row[cols.ACTIVE_RETURN].item(),
                abs_tol=1e-12,
            )
        )

    def test_gapped_overall_attribution_weights_foot_for_both_streams(self) -> None:
        """Overall portfolio and benchmark weights use observed coverage."""
        periods = [
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
        ]
        portfolio = test_util.make_performance_df(
            periods,
            {
                "A": ([0.02, 0.01], [0.60, 0.40]),
                "B": ([0.00, 0.03], [0.40, 0.60]),
            },
        )
        benchmark = test_util.make_performance_df(
            periods,
            {
                "A": ([0.01, 0.02], [0.30, 0.70]),
                "B": ([0.02, 0.00], [0.70, 0.30]),
            },
        )

        overall = Analytics(portfolio, benchmark).attribution().to_polars(
            View.OVERALL_ATTRIBUTION
        )
        detail = overall.filter(pl.col(cols.CLASSIFICATION_NAME) != "Total")

        self.assertTrue(
            math.isclose(detail[cols.PORTFOLIO_WEIGHT].sum(), 1.0, abs_tol=1e-12)
        )
        self.assertTrue(
            math.isclose(detail[cols.BENCHMARK_WEIGHT].sum(), 1.0, abs_tol=1e-12)
        )

    def test_daily_periods_consolidate_to_monthly_return(self) -> None:
        """Sub-monthly total returns compound into monthly report periods."""
        periods = [
            (dt.date(2024, 1, 1), dt.date(2024, 1, 15)),
            (dt.date(2024, 1, 16), dt.date(2024, 1, 31)),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 15)),
            (dt.date(2024, 2, 16), dt.date(2024, 2, 29)),
        ]
        df = test_util.make_performance_df(
            periods,
            {"A": ([0.01, 0.02, -0.03, 0.04], [1.0, 1.0, 1.0, 1.0])},
        )

        summary = Analytics(df, df, frequency=Frequency.MONTHLY).attribution().to_polars(
            View.SUBPERIOD_SUMMARY
        )

        self.assertEqual(summary.height, 2)
        self.assertTrue(
            math.isclose(
                summary[cols.PORTFOLIO_RETURN].item(0),
                (1.01 * 1.02) - 1.0,
                abs_tol=1e-12,
            )
        )
        self.assertTrue(
            math.isclose(
                summary[cols.PORTFOLIO_RETURN].item(1),
                (0.97 * 1.04) - 1.0,
                abs_tol=1e-12,
            )
        )

    def test_date_alignment_keeps_only_common_periods(self) -> None:
        """Analytics restricts portfolio and benchmark to their common periods."""
        portfolio = test_util.make_performance_df(
            [
                (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
                (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
                (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
            ],
            {"A": ([0.01, 0.02, 0.03], [1.0, 1.0, 1.0])},
        )
        benchmark = test_util.make_performance_df(
            [
                (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
                (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
                (dt.date(2024, 4, 1), dt.date(2024, 4, 30)),
            ],
            {"A": ([0.02, 0.01, 0.04], [1.0, 1.0, 1.0])},
        )

        summary = Analytics(portfolio, benchmark).attribution().to_polars(
            View.SUBPERIOD_SUMMARY
        )

        self.assertEqual(summary.height, 2)
        self.assertEqual(summary[cols.FROM_DATE].item(0), dt.date(2024, 2, 1))
        self.assertEqual(summary[cols.THRU_DATE].item(-1), dt.date(2024, 3, 31))

    def test_native_frequency_rejects_an_interior_period_on_only_one_side(self) -> None:
        """An unmatched interior period cannot be folded into an earlier return."""
        january = (dt.date(2024, 1, 1), dt.date(2024, 1, 31))
        february = (dt.date(2024, 2, 1), dt.date(2024, 2, 29))
        march = (dt.date(2024, 3, 1), dt.date(2024, 3, 31))
        complete = test_util.make_performance_df(
            (january, february, march),
            {"A": ([0.01, 0.02, 0.03], [1.0, 1.0, 1.0])},
        )
        missing_february = test_util.make_performance_df(
            (january, march),
            {"A": ([0.01, 0.03], [1.0, 1.0])},
        )

        for portfolio, benchmark in (
            (complete, missing_february),
            (missing_february, complete),
        ):
            with self.subTest(extra_side="portfolio" if portfolio.height == 3 else "benchmark"):
                with self.assertRaises(PparError) as context:
                    Analytics(portfolio, benchmark)

                self.assertIn("2024-02-01", str(context.exception))
                self.assertIn("2024-02-29", str(context.exception))

    def test_native_frequency_rejects_interior_partial_overlap(self) -> None:
        """Different source intervals cannot share a synthesized period label."""
        portfolio = test_util.make_performance_df(
            (
                (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
                (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
                (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
            ),
            {"A": ([0.01, 0.02, 0.03], [1.0, 1.0, 1.0])},
        )
        benchmark = test_util.make_performance_df(
            (
                (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
                (dt.date(2024, 2, 1), dt.date(2024, 2, 15)),
                (dt.date(2024, 2, 16), dt.date(2024, 2, 29)),
                (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
            ),
            {"A": ([0.01, 0.01, 0.01, 0.03], [1.0, 1.0, 1.0, 1.0])},
        )

        with self.assertRaises(PparError) as context:
            Analytics(portfolio, benchmark)

        self.assertIn("2024-02", str(context.exception))

    def test_native_frequency_accepts_a_shared_irregular_gap(self) -> None:
        """A gap is valid when both streams contain the same native intervals."""
        periods = (
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
        )
        portfolio = test_util.make_performance_df(
            periods,
            {"A": ([0.01, 0.03], [1.0, 1.0])},
        )
        benchmark = test_util.make_performance_df(
            periods,
            {"A": ([0.02, 0.04], [1.0, 1.0])},
        )

        summary = Analytics(portfolio, benchmark).attribution().to_polars(
            View.SUBPERIOD_SUMMARY
        )

        self.assertEqual(summary.select(cols.DATE_COLUMNS).height, 2)

    def test_no_common_periods_raises_expected_error(self) -> None:
        """Analytics fails when portfolio and benchmark do not overlap."""
        portfolio = test_util.make_performance_df(
            [(dt.date(2024, 1, 1), dt.date(2024, 1, 31))],
            {"A": ([0.01], [1.0])},
        )
        benchmark = test_util.make_performance_df(
            [(dt.date(2024, 2, 1), dt.date(2024, 2, 29))],
            {"A": ([0.02], [1.0])},
        )

        with self.assertRaises(PparError):
            Analytics(portfolio, benchmark)


if __name__ == "__main__":
    unittest.main()
