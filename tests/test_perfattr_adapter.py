"""Verify ppar's permanent perfattr numerical-result boundary."""

from collections.abc import Sequence
from dataclasses import dataclass
import datetime as dt
from pathlib import Path
from typing import cast
import unittest
from unittest import mock

import polars as pl
from polars.testing import assert_frame_equal

from ppar import Analytics
import ppar._perfattr_adapter as adapter_module
import ppar.attribution as attribution_module
from ppar.attribution import Attribution, View
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


def _calculate_all_views(
    test_case: unittest.TestCase,
    analytics: Analytics,
    classification_name: str | None = None,
    classification_data_source: str | Path | pl.DataFrame | None = None,
    mapping_data_sources: Sequence[str | Path | pl.DataFrame | None] | None = None,
) -> Attribution:
    """Calculate one attribution and exercise every public tabular view."""
    result = analytics.attribution(
        classification_name,
        classification_data_source,
        mapping_data_sources,
    )
    for view in View:
        with test_case.subTest(view=view):
            test_case.assertFalse(result.to_polars(view).is_empty())
            test_case.assertIn("<table", result.to_html(view))
    return result


def _assert_financial_invariants(
    test_case: unittest.TestCase,
    attribution: Attribution,
) -> None:
    """Check additive and linked identities exposed at the public boundary."""
    summary = attribution.to_polars(View.SUBPERIOD_SUMMARY)
    simple_identities = (
        pl.col(cols.ACTIVE_CONTRIB_SIMPLE)
        - pl.col(cols.PORTFOLIO_CONTRIB_SIMPLE)
        + pl.col(cols.BENCHMARK_CONTRIB_SIMPLE),
        pl.col(cols.TOTAL_EFFECT_SIMPLE)
        - pl.col(cols.ALLOCATION_EFFECT_SIMPLE)
        - pl.col(cols.SELECTION_EFFECT_SIMPLE),
        pl.col(cols.TOTAL_EFFECT_SIMPLE) - pl.col(cols.ACTIVE_RETURN),
    )
    cumulative = attribution.to_polars(View.CUMULATIVE_ATTRIBUTION)
    linked_identities = (
        pl.col(cols.ACTIVE_CONTRIB_SMOOTHED)
        - pl.col(cols.PORTFOLIO_CONTRIB_SMOOTHED)
        + pl.col(cols.BENCHMARK_CONTRIB_SMOOTHED),
        pl.col(cols.TOTAL_EFFECT_SMOOTHED)
        - pl.col(cols.ALLOCATION_EFFECT_SMOOTHED)
        - pl.col(cols.SELECTION_EFFECT_SMOOTHED),
    )
    for frame, identities in (
        (summary, simple_identities),
        (cumulative, linked_identities),
    ):
        for identity in identities:
            maximum_error = cast(float, frame.select(identity.abs().max()).item())
            test_case.assertLessEqual(maximum_error, _TOLERANCE)
    final_cumulative_error = abs(
        cast(float, cumulative[-1, cols.CUMULATIVE_TOTAL_EFFECT])
        - cast(float, cumulative[-1, cols.CUMULATIVE_ACTIVE_RETURN])
    )
    test_case.assertLessEqual(final_cumulative_error, _TOLERANCE)


class TestPerfattrAdapter(unittest.TestCase):
    """Exercise portable calculation translation and financial invariants."""

    def test_all_views_support_asymmetric_multi_period_holdings(self) -> None:
        """The adapter preserves asymmetric rows across every public view."""
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

        result = _calculate_all_views(self, Analytics(portfolio, benchmark))
        _assert_financial_invariants(self, result)

    def test_project_fixture_runs_for_security_and_sector(self) -> None:
        """Real rounded weights cross the boundary after classification mapping."""
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
                _calculate_all_views(
                    self,
                    analytics,
                    classification_name,
                    test_util.classification_data_path(classification_name),
                    test_util.mapping_data_paths(analytics, classification_name),
                )

    def test_signed_weights_and_near_minus_one_returns_preserve_invariants(self) -> None:
        """Linking remains reconciled near its lower limit with short exposure."""
        periods = (
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
        )
        portfolio = test_util.make_performance_df(
            periods,
            {
                "LONG": ([-0.80, 0.12], [1.20, 1.15]),
                "SHORT": ([0.10, -0.04], [-0.20, -0.15]),
            },
        )
        benchmark = test_util.make_performance_df(
            periods,
            {
                "LONG": ([-0.85, 0.08], [1.10, 1.05]),
                "OTHER_SHORT": ([0.10, -0.02], [-0.10, -0.05]),
            },
        )

        result = _calculate_all_views(self, Analytics(portfolio, benchmark))
        _assert_financial_invariants(self, result)

    def test_classification_split_does_not_change_group_results(self) -> None:
        """Splitting one group into equivalent holdings preserves mapped results."""
        periods = (
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
            (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
        )
        base_portfolio = test_util.make_performance_df(
            periods,
            {
                "X": ([0.10, -0.04, 0.06], [0.60, 0.50, 0.70]),
                "B": ([0.02, 0.03, -0.01], [0.40, 0.50, 0.30]),
            },
        )
        base_benchmark = test_util.make_performance_df(
            periods,
            {
                "X": ([0.08, -0.02, 0.04], [0.55, 0.65, 0.60]),
                "B": ([0.01, 0.02, 0.00], [0.45, 0.35, 0.40]),
            },
        )
        split_portfolio = test_util.make_performance_df(
            periods,
            {
                "X1": ([0.10, -0.04, 0.06], [0.36, 0.30, 0.42]),
                "X2": ([0.10, -0.04, 0.06], [0.24, 0.20, 0.28]),
                "B": ([0.02, 0.03, -0.01], [0.40, 0.50, 0.30]),
            },
        )
        split_benchmark = test_util.make_performance_df(
            periods,
            {
                "X1": ([0.08, -0.02, 0.04], [0.33, 0.39, 0.36]),
                "X2": ([0.08, -0.02, 0.04], [0.22, 0.26, 0.24]),
                "B": ([0.01, 0.02, 0.00], [0.45, 0.35, 0.40]),
            },
        )
        classification = pl.DataFrame(
            {cols.IDENTIFIER: ["B", "X"], cols.NAME: ["Base", "Combined"]}
        )
        mapping = pl.DataFrame(
            {"from": ["B", "X1", "X2"], "to": ["B", "X", "X"]}
        )
        base_analytics = Analytics(
            base_portfolio,
            base_benchmark,
            portfolio_classification_name="Group",
            benchmark_classification_name="Group",
        )
        split_analytics = Analytics(
            split_portfolio,
            split_benchmark,
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )

        base = base_analytics.attribution("Group", classification)
        split = split_analytics.attribution(
            "Group",
            classification,
            (mapping, mapping),
        )
        for view in View:
            assert_frame_equal(
                base.to_polars(view),
                split.to_polars(view),
                rel_tol=_TOLERANCE,
                abs_tol=_TOLERANCE,
            )

    def test_attribution_uses_perfattr_boundary(self) -> None:
        """Every attribution calculation invokes the permanent portable boundary."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            {"A": ([0.01], [1.0])},
        )
        with mock.patch.object(
            attribution_module,
            "calculate_with_perfattr",
            wraps=attribution_module.calculate_with_perfattr,
        ) as adapter:
            Analytics(performance).attribution()

        adapter.assert_called_once()

    def test_analytics_preparation_uses_portable_boundary(self) -> None:
        """Source loading and pair preparation invoke only portable composition."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            {"A": ([0.01], [1.0])},
        )
        with mock.patch.object(
            adapter_module,
            "prepare_attribution",
            wraps=adapter_module.prepare_attribution,
        ) as portable:
            Analytics(performance)

        # Analytics prepares the portfolio/benchmark pair once. Preparing each side
        # against itself first would repeat validation and consolidation without
        # adding a financial check.
        self.assertEqual(portable.call_count, 1)

    def test_preparation_error_uses_ppar_terminology(self) -> None:
        """Portable preparation detail remains useful without branding the boundary."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            {"A": ([0.01], [1.0])},
        )
        with (
            mock.patch.object(
                adapter_module,
                "prepare_attribution",
                side_effect=adapter_module.PreparationError("periods do not align"),
            ),
            self.assertRaises(PparError) as context,
        ):
            Analytics(performance)

        self.assertEqual(
            str(context.exception),
            "Cannot prepare performance: periods do not align",
        )
        self.assertEqual(context.exception.context, {"boundary": "Performance"})
        self.assertNotIn("perfattr", str(context.exception))

    def test_calculation_error_uses_ppar_terminology(self) -> None:
        """Portable calculation detail remains useful without branding the boundary."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            {"A": ([0.01], [1.0])},
        )
        analytics = Analytics(performance)
        with (
            mock.patch.object(
                adapter_module,
                "calculate_attribution",
                side_effect=adapter_module.AttributionError("effects do not reconcile"),
            ),
            self.assertRaises(PparError) as context,
        ):
            analytics.attribution()

        self.assertEqual(
            str(context.exception),
            "Cannot calculate attribution: effects do not reconcile",
        )
        self.assertEqual(
            context.exception.context,
            {"boundary": "Attribution calculation"},
        )
        self.assertNotIn("perfattr", str(context.exception))

    def test_attribution_for_uses_portable_calculation(self) -> None:
        """Bundled classification sources use the permanent calculation path."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            {"A": ([0.01], [1.0])},
        )
        sources = _Sources()

        result = Analytics(performance).attribution_for(sources)

        self.assertFalse(result.to_polars(View.SUBPERIOD_SUMMARY).is_empty())
