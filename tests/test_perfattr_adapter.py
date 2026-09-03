"""Verify the opt-in perfattr engine at ppar's numerical-result boundary."""

from collections.abc import Sequence
from dataclasses import dataclass
import datetime as dt
from pathlib import Path
import unittest
from unittest import mock

import polars as pl
from polars.testing import assert_frame_equal

from ppar import Analytics
from ppar.attribution import View
from ppar.errors import PparError
from ppar.frequency import Frequency
import ppar.schema as cols
from tests import helpers as test_util


_TOLERANCE = 1e-12


@dataclass
class _Sources:
    """Provide the structural source bundle consumed by ``attribution_for``."""

    classification_name: str | None = None
    classification_data_source: str | Path | pl.DataFrame | None = None
    mapping_data_sources: Sequence[str | Path | pl.DataFrame | None] | None = None


def _assert_engine_parity(
    test_case: unittest.TestCase,
    analytics: Analytics,
    classification_name: str | None = None,
    classification_data_source: str | Path | pl.DataFrame | None = None,
    mapping_data_sources: Sequence[str | Path | pl.DataFrame | None] | None = None,
) -> None:
    """Compare every public attribution view and its HTML presentation."""
    polars_result = analytics.attribution(
        classification_name,
        classification_data_source,
        mapping_data_sources,
    )
    pandas_result = analytics.attribution(
        classification_name,
        classification_data_source,
        mapping_data_sources,
        engine="pandas",
    )
    for view in View:
        with test_case.subTest(view=view):
            assert_frame_equal(
                polars_result.to_polars(view),
                pandas_result.to_polars(view),
                rel_tol=_TOLERANCE,
                abs_tol=_TOLERANCE,
            )
            test_case.assertEqual(
                polars_result.to_html(view),
                pandas_result.to_html(view),
            )


class TestPerfattrAdapter(unittest.TestCase):
    """Exercise engine selection, translation, and cross-engine parity."""

    def test_all_views_match_for_asymmetric_multi_period_holdings(self) -> None:
        """The adapter preserves rows, schemas, nulls, order, and numerical values."""
        periods = (
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
            (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
        )
        portfolio = test_util.make_performance_df(
            periods,
            {
                "A": ([0.10, -0.02, 0.04], [0.60, 0.55, 0.50]),
                "B": ([-0.05, 0.03, 0.01], [0.40, 0.45, 0.50]),
            },
        )
        benchmark = test_util.make_performance_df(
            periods,
            {
                "A": ([0.08, -0.01, 0.02], [0.70, 0.65, 0.60]),
                "C": ([0.01, 0.02, -0.01], [0.30, 0.35, 0.40]),
            },
        )

        _assert_engine_parity(self, Analytics(portfolio, benchmark))

    def test_consolidated_zero_net_group_preserves_authoritative_contribution(self) -> None:
        """Mapped null returns and nonzero contributions survive both boundaries."""
        periods = (
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
            (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
        )
        portfolio = test_util.make_performance_df(
            periods,
            {
                "LONG": ([0.20, 0.10, -0.05], [0.50] * 3),
                "SHORT": ([0.10, 0.05, -0.02], [-0.50] * 3),
                "CORE": ([0.02, 0.01, 0.03], [1.00] * 3),
            },
        )
        benchmark = test_util.make_performance_df(
            periods,
            {
                "LONG": ([0.10, 0.08, -0.03], [0.50] * 3),
                "SHORT": ([0.04, 0.02, -0.01], [-0.50] * 3),
                "CORE": ([0.01, 0.02, 0.02], [1.00] * 3),
            },
        )
        mapping = pl.DataFrame(
            {
                "from": ["LONG", "SHORT", "CORE"],
                "to": ["HEDGE", "HEDGE", "CORE"],
            }
        )
        classification = pl.DataFrame(
            {cols.IDENTIFIER: ["HEDGE", "CORE"], cols.NAME: ["Hedge", "Core"]}
        )
        analytics = Analytics(
            portfolio,
            benchmark,
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
            frequency=Frequency.QUARTERLY,
        )

        _assert_engine_parity(
            self,
            analytics,
            "Strategy",
            classification,
            (mapping, mapping),
        )
        pandas_detail = analytics.attribution(
            "Strategy",
            classification,
            (mapping, mapping),
            engine="pandas",
        ).to_polars(View.SUBPERIOD_ATTRIBUTION)
        hedge = pandas_detail.filter(
            pl.col(cols.CLASSIFICATION_IDENTIFIER) == "HEDGE"
        )
        self.assertIsNone(hedge[cols.PORTFOLIO_RETURN].item())
        self.assertNotEqual(hedge[cols.PORTFOLIO_CONTRIB_SIMPLE].item(), 0.0)

    def test_project_fixture_matches_for_security_and_sector(self) -> None:
        """Real rounded weights preserve parity through classification mapping."""
        analytics = Analytics(
            test_util.performance_data_path("Mega-Cap Portfolio"),
            test_util.performance_data_path("Large-Cap Portfolio"),
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
            from_date="2024-02-01",
            frequency=Frequency.MONTHLY,
            holidays=test_util.HOLIDAYS_PATH,
        )

        for classification_name in ("Security", "Economic Sector"):
            with self.subTest(classification_name=classification_name):
                _assert_engine_parity(
                    self,
                    analytics,
                    classification_name,
                    test_util.classification_data_path(classification_name),
                    test_util.mapping_data_paths(analytics, classification_name),
                )

    def test_default_engine_does_not_invoke_adapter(self) -> None:
        """Existing callers remain on the original Polars implementation."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            {"A": ([0.01], [1.0])},
        )
        with mock.patch("ppar.attribution.calculate_with_perfattr") as adapter:
            Analytics(performance).attribution()

        adapter.assert_not_called()

    def test_attribution_for_forwards_pandas_engine(self) -> None:
        """Bundled classification sources can select the portable calculation path."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            {"A": ([0.01], [1.0])},
        )
        sources = _Sources()

        result = Analytics(performance).attribution_for(sources, engine="pandas")

        self.assertFalse(result.to_polars(View.SUBPERIOD_SUMMARY).is_empty())

    def test_unknown_engine_is_rejected(self) -> None:
        """Misspelled engines fail explicitly rather than changing calculation paths."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            {"A": ([0.01], [1.0])},
        )

        with self.assertRaisesRegex(PparError, "engine must be"):
            Analytics(performance).attribution(engine="other")
