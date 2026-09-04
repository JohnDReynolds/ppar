"""Retained ppar-facing attribution invariants at the portable boundary."""

import datetime as dt
import math
import unittest

import polars as pl

from ppar import Analytics
from ppar.attribution import View
from ppar.errors import PparError
import ppar.schema as cols
from tests import helpers as test_util


class TestCalculationInvariants(unittest.TestCase):
    """Verify ppar-specific schema, aggregation, and error behavior."""

    def test_reported_selection_combines_three_effect_selection_and_interaction(
        self,
    ) -> None:
        """The ppar schema exposes portable selection without an interaction column."""
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
        self.assertNotIn("Interaction_Effect_Simple", detail.columns)

    def test_gapped_overall_attribution_weights_foot_for_both_streams(self) -> None:
        """The host's overall-view aggregation uses only observed coverage."""
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

    def test_no_common_periods_uses_ppar_error_contract(self) -> None:
        """One real disjoint-history failure must cross the adapter as PparError."""
        portfolio = test_util.make_performance_df(
            [(dt.date(2024, 1, 1), dt.date(2024, 1, 31))],
            {"A": ([0.01], [1.0])},
        )
        benchmark = test_util.make_performance_df(
            [(dt.date(2024, 2, 1), dt.date(2024, 2, 29))],
            {"A": ([0.02], [1.0])},
        )

        with self.assertRaisesRegex(PparError, "no common performance periods"):
            Analytics(portfolio, benchmark)


if __name__ == "__main__":
    unittest.main()
