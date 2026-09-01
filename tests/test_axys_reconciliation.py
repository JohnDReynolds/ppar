"""Focused in-memory tests for Axys security performance reconciliation."""

# Python Imports
from collections.abc import Sequence
import datetime as dt
import math
import random
import unittest

# Third-Party Imports
import polars as pl

# Project Imports
from ppar.axys_apx.reconciliation import (
    derive_reconciled_weights,
    derive_security_performance_for_all_periods,
    exceeds_fatal_tolerance,
    filter_to_common_periods,
    unreconciled_difference,
)
import ppar.schema as cols
from ppar.errors import PparError


_FROM_DATE = dt.date(2023, 12, 31)
_THRU_DATE = dt.date(2024, 1, 31)


def _error_message(message: str) -> str:
    """Return calculation-only error details unchanged."""
    return message


def _single_period_security_performance(
    contributions: Sequence[float | None],
    returns: Sequence[float | None],
    weights: Sequence[float | None],
    identifiers: Sequence[str] | None = None,
) -> pl.DataFrame:
    """Return row-grain security performance data for a single portfolio period."""
    if identifiers is None:
        identifiers = [f"S{index}" for index in range(len(returns))]
    return pl.DataFrame(
        {
            cols.PORTFOLIO_CODE: ["PORT"] * len(returns),
            cols.FROM_DATE: [_FROM_DATE] * len(returns),
            cols.THRU_DATE: [_THRU_DATE] * len(returns),
            cols.IDENTIFIER: identifiers,
            cols.CONTRIBUTION: pl.Series(contributions, dtype=pl.Float64),
            cols.RETURN: pl.Series(returns, dtype=pl.Float64),
            cols.WEIGHT: pl.Series(weights, dtype=pl.Float64),
        }
    )


def _single_period_portfolio_performance(portfolio_return: float) -> pl.DataFrame:
    """Return portfolio-level data corresponding to one security period."""
    return pl.DataFrame(
        {
            cols.PORTFOLIO_CODE: ["PORT"],
            cols.FROM_DATE: [_FROM_DATE],
            cols.THRU_DATE: [_THRU_DATE],
            cols.PORTFOLIO_RETURN: [portfolio_return],
        }
    )


class TestAxysReconciliation(unittest.TestCase):
    """Verify reconciliation calculations without source-file fixtures."""

    def test_nonfinite_values_are_rejected_before_weight_solving(self) -> None:
        """Direct reconciliation cannot bypass source-boundary finiteness checks."""
        cases = (
            (
                _single_period_portfolio_performance(float("nan")),
                _single_period_security_performance([0.0], [0.0], [1.0]),
            ),
            (
                _single_period_portfolio_performance(0.0),
                _single_period_security_performance([0.0], [float("nan")], [1.0]),
            ),
            (
                _single_period_portfolio_performance(0.0),
                _single_period_security_performance([0.0], [0.0], [float("inf")]),
            ),
            (
                _single_period_portfolio_performance(0.0),
                _single_period_security_performance([float("-inf")], [0.0], [1.0]),
            ),
        )

        for portfolio_performance, security_performance in cases:
            with self.subTest(
                portfolio=portfolio_performance.to_dicts(),
                security=security_performance.to_dicts(),
            ):
                with self.assertRaises(PparError):
                    derive_security_performance_for_all_periods(
                        portfolio_performance,
                        security_performance,
                        _error_message,
                    )

    def test_usable_contributions_are_preferred_over_reported_weights(self) -> None:
        """Contribution-divided-by-return provides the preferred anchor weights."""
        security_performance = _single_period_security_performance(
            contributions=[0.06, -0.02],
            returns=[0.10, -0.05],
            weights=[0.50, 0.50],
        )

        weights, achieved_return = derive_reconciled_weights(
            security_performance,
            portfolio_return=0.04,
        )

        self.assertTrue(math.isclose(weights[0], 0.60, abs_tol=1e-12))
        self.assertTrue(math.isclose(weights[1], 0.40, abs_tol=1e-12))
        self.assertTrue(math.isclose(achieved_return, 0.04, abs_tol=1e-12))

    def test_all_missing_anchors_are_rejected_as_underdetermined(self) -> None:
        """Missing evidence cannot be replaced with arbitrary equal participation."""
        security_performance = _single_period_security_performance(
            contributions=[None, None, None],
            returns=[0.0, 0.1, 0.2],
            weights=[None, None, None],
        )

        with self.assertRaisesRegex(ValueError, "underdetermined"):
            derive_reconciled_weights(
                security_performance,
                portfolio_return=0.12,
            )

    def test_signed_source_weights_and_contributions_are_preserved(self) -> None:
        """Exact long/short evidence remains signed and unchanged."""
        expected_weights = [1.20, -0.20, 0.0]
        security_returns = [0.10, 0.05, -0.03]
        contributions = [
            weight * security_return
            for weight, security_return in zip(expected_weights, security_returns)
        ]
        security_performance = _single_period_security_performance(
            contributions=contributions,
            returns=security_returns,
            weights=[1.0, 0.0, 0.0],
        )

        weights, achieved_return = derive_reconciled_weights(
            security_performance,
            portfolio_return=sum(contributions),
        )

        for actual, expected in zip(weights, expected_weights):
            self.assertTrue(math.isclose(actual, expected, abs_tol=1e-12))
        self.assertTrue(math.isclose(sum(weights), 1.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(achieved_return, sum(contributions), abs_tol=1e-12))

    def test_signed_reported_weights_are_used_when_contributions_are_missing(self) -> None:
        """Reported long/short weights remain valid fallback evidence."""
        expected_weights = [1.20, -0.20]
        returns = [0.10, 0.05]
        security_performance = _single_period_security_performance(
            contributions=[None, None],
            returns=returns,
            weights=expected_weights,
        )

        weights, achieved_return = derive_reconciled_weights(
            security_performance,
            portfolio_return=0.11,
        )

        self.assertEqual(weights, expected_weights)
        self.assertTrue(math.isclose(achieved_return, 0.11, abs_tol=1e-12))

    def test_zero_return_with_nonzero_contribution_is_rejected(self) -> None:
        """A contribution unsupported by a zero security return is contradictory."""
        security_performance = _single_period_security_performance(
            contributions=[0.01, 0.0],
            returns=[0.0, 0.0],
            weights=[0.50, 0.50],
        )

        with self.assertRaisesRegex(ValueError, "contradictory"):
            derive_reconciled_weights(security_performance, portfolio_return=0.0)

    def test_two_missing_weights_are_inferred_when_equations_are_unique(self) -> None:
        """Two missing anchors are supported when sum and return fix both weights."""
        security_performance = _single_period_security_performance(
            contributions=[0.05, None, None],
            returns=[0.10, 0.0, -0.10],
            weights=[0.50, None, None],
        )

        weights, achieved_return = derive_reconciled_weights(
            security_performance,
            portfolio_return=0.025,
        )

        for actual, expected in zip(weights, [0.50, 0.25, 0.25]):
            self.assertTrue(math.isclose(actual, expected, abs_tol=1e-12))
        self.assertTrue(math.isclose(achieved_return, 0.025, abs_tol=1e-12))

    def test_one_missing_weight_is_inferred_when_both_equations_agree(self) -> None:
        """One absent anchor is determined by sum and confirmed by portfolio return."""
        security_performance = _single_period_security_performance(
            contributions=[0.06, None],
            returns=[0.10, -0.05],
            weights=[0.60, None],
        )

        weights, achieved_return = derive_reconciled_weights(
            security_performance,
            portfolio_return=0.04,
        )

        self.assertEqual(weights, [0.60, 0.40])
        self.assertTrue(math.isclose(achieved_return, 0.04, abs_tol=1e-12))

    def test_one_anchor_and_three_missing_weights_are_underdetermined(self) -> None:
        """Two equations cannot uniquely determine three missing row weights."""
        security_performance = _single_period_security_performance(
            contributions=[0.05, None, None, None],
            returns=[0.10, 0.0, -0.10, 0.20],
            weights=[0.50, None, None, None],
        )

        with self.assertRaisesRegex(ValueError, "underdetermined"):
            derive_reconciled_weights(security_performance, portfolio_return=0.025)

    def test_equal_returns_cannot_determine_two_missing_weights(self) -> None:
        """Redundant sum and return equations leave missing weights ambiguous."""
        security_performance = _single_period_security_performance(
            contributions=[0.05, None, None],
            returns=[0.10, 0.0, 0.0],
            weights=[0.50, None, None],
        )

        with self.assertRaisesRegex(ValueError, "underdetermined"):
            derive_reconciled_weights(security_performance, portfolio_return=0.05)

    def test_adjusted_weights_do_not_depend_on_input_order(self) -> None:
        """The minimum-departure adjustment has an order-independent result."""
        identifiers = ["A", "B", "C"]
        security_performance = _single_period_security_performance(
            contributions=[None, None, None],
            returns=[0.10, 0.03, -0.02],
            weights=[0.50, 0.30, 0.20],
            identifiers=identifiers,
        )
        reversed_performance = security_performance.reverse()

        weights, _ = derive_reconciled_weights(security_performance, portfolio_return=0.06)
        reversed_weights, _ = derive_reconciled_weights(
            reversed_performance,
            portfolio_return=0.06,
        )

        weights_by_identifier = dict(zip(identifiers, weights))
        reversed_by_identifier = dict(
            zip(reversed_performance[cols.IDENTIFIER].to_list(), reversed_weights)
        )
        for identifier in identifiers:
            self.assertTrue(
                math.isclose(
                    weights_by_identifier[identifier],
                    reversed_by_identifier[identifier],
                    abs_tol=1e-12,
                )
            )

    def test_random_exact_signed_evidence_preserves_conservation(self) -> None:
        """Random valid source portfolios conserve weights, returns, and contributions."""
        generator = random.Random(1731)
        for case_number in range(100):
            with self.subTest(case_number=case_number):
                weights = [generator.uniform(-0.50, 0.75) for _ in range(4)]
                weights.append(1.0 - sum(weights))
                returns = [generator.uniform(-0.25, 0.35) for _ in weights]
                contributions = [
                    weight * security_return
                    for weight, security_return in zip(weights, returns)
                ]
                target_return = sum(contributions)
                security_performance = _single_period_security_performance(
                    contributions=contributions,
                    returns=returns,
                    weights=[None] * len(weights),
                )

                actual_weights, achieved_return = derive_reconciled_weights(
                    security_performance,
                    portfolio_return=target_return,
                )

                self.assertTrue(math.isclose(sum(actual_weights), 1.0, abs_tol=1e-12))
                self.assertTrue(
                    math.isclose(achieved_return, target_return, abs_tol=1e-12)
                )
                for actual, expected in zip(actual_weights, weights):
                    self.assertTrue(math.isclose(actual, expected, abs_tol=1e-12))
                actual_contributions = [
                    weight * security_return
                    for weight, security_return in zip(actual_weights, returns)
                ]
                for actual, expected in zip(actual_contributions, contributions):
                    self.assertTrue(math.isclose(actual, expected, abs_tol=1e-12))

    def test_random_signed_adjustments_preserve_constraints_and_signs(self) -> None:
        """Random feasible adjustments conserve returns without inventing signs."""
        generator = random.Random(4819)
        for case_number in range(100):
            with self.subTest(case_number=case_number):
                positive_anchors = [generator.uniform(0.05, 1.0) for _ in range(3)]
                negative_anchors = [generator.uniform(0.05, 1.0) for _ in range(2)]
                anchor_short_total = generator.uniform(0.05, 0.60)
                anchor_weights = [
                    value * (1.0 + anchor_short_total) / sum(positive_anchors)
                    for value in positive_anchors
                ] + [
                    -value * anchor_short_total / sum(negative_anchors)
                    for value in negative_anchors
                ]

                positive_targets = [generator.uniform(0.05, 1.0) for _ in range(3)]
                negative_targets = [generator.uniform(0.05, 1.0) for _ in range(2)]
                target_short_total = generator.uniform(0.05, 0.60)
                target_weights = [
                    value * (1.0 + target_short_total) / sum(positive_targets)
                    for value in positive_targets
                ] + [
                    -value * target_short_total / sum(negative_targets)
                    for value in negative_targets
                ]
                returns = [generator.uniform(-0.25, 0.35) for _ in anchor_weights]
                contributions = [
                    weight * security_return
                    for weight, security_return in zip(anchor_weights, returns)
                ]
                target_return = sum(
                    weight * security_return
                    for weight, security_return in zip(target_weights, returns)
                )
                security_performance = _single_period_security_performance(
                    contributions=contributions,
                    returns=returns,
                    weights=[None] * len(anchor_weights),
                )

                actual_weights, achieved_return = derive_reconciled_weights(
                    security_performance,
                    portfolio_return=target_return,
                )

                self.assertTrue(math.isclose(sum(actual_weights), 1.0, abs_tol=1e-12))
                self.assertTrue(
                    math.isclose(achieved_return, target_return, abs_tol=1e-12)
                )
                for actual, anchor in zip(actual_weights, anchor_weights):
                    self.assertGreaterEqual(actual * math.copysign(1.0, anchor), -1e-12)

    def test_weights_are_adjusted_to_reconcile_to_portfolio_return(self) -> None:
        """A feasible target return shifts weights while preserving invariants."""
        security_performance = _single_period_security_performance(
            contributions=[0.05, 0.0],
            returns=[0.10, 0.0],
            weights=[0.50, 0.50],
        )

        weights, achieved_return = derive_reconciled_weights(
            security_performance,
            portfolio_return=0.08,
        )

        self.assertTrue(all(weight >= 0.0 for weight in weights))
        self.assertTrue(math.isclose(sum(weights), 1.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(achieved_return, 0.08, abs_tol=1e-12))

    def test_all_period_reconciliation_retains_exact_period_for_linking(self) -> None:
        """Aggregate evidence includes exact periods as part of each linked path."""
        portfolio_performance = _single_period_portfolio_performance(0.04)
        security_performance = _single_period_security_performance(
            contributions=[0.04],
            returns=[0.04],
            weights=[1.0],
        )

        _, reconciliation_periods = derive_security_performance_for_all_periods(
            portfolio_performance,
            security_performance,
            _error_message,
        )

        self.assertEqual(
            reconciliation_periods,
            {(("PORT", _FROM_DATE, _THRU_DATE), 0.04, 0.04)},
        )

    def test_filter_to_common_periods_rejects_any_period_mismatch(self) -> None:
        """No beginning, interior, or ending source period may be discarded."""
        periods = (
            (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
            (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
        )
        portfolio_performance = pl.DataFrame(
            {
                cols.PORTFOLIO_CODE: ["PORT"] * 3,
                cols.FROM_DATE: [period[0] for period in periods],
                cols.THRU_DATE: [period[1] for period in periods],
                cols.PORTFOLIO_RETURN: [0.01, 0.02, 0.03],
            }
        )
        security_performance = pl.DataFrame(
            {
                cols.PORTFOLIO_CODE: ["PORT"] * 3,
                cols.FROM_DATE: [period[0] for period in periods],
                cols.THRU_DATE: [period[1] for period in periods],
                cols.IDENTIFIER: ["A"] * 3,
            }
        )

        for missing_index in range(3):
            for missing_source in ("portfolio", "security"):
                with self.subTest(
                    missing_index=missing_index,
                    missing_source=missing_source,
                ):
                    portfolio = portfolio_performance
                    security = security_performance
                    if missing_source == "portfolio":
                        portfolio = portfolio_performance.with_row_index().filter(
                            pl.col("index") != missing_index
                        ).drop("index")
                    else:
                        security = security_performance.with_row_index().filter(
                            pl.col("index") != missing_index
                        ).drop("index")

                    with self.assertRaises(PparError) as context:
                        filter_to_common_periods(
                            portfolio,
                            security,
                            _error_message,
                        )

                    self.assertIn(periods[missing_index][0].isoformat(), str(context.exception))
                    self.assertIn(periods[missing_index][1].isoformat(), str(context.exception))

    def test_all_period_reconciliation_rejects_duplicate_identifier_rows(self) -> None:
        """Ambiguous duplicate security rows fail at the adapter boundary."""
        portfolio_performance = _single_period_portfolio_performance(0.04)
        security_performance = _single_period_security_performance(
            contributions=[0.06, -0.02],
            returns=[0.10, -0.05],
            weights=[0.50, 0.50],
            identifiers=["A", "A"],
        )

        with self.assertRaises(PparError) as context:
            derive_security_performance_for_all_periods(
                portfolio_performance, security_performance, _error_message
            )

        message = str(context.exception)
        self.assertIn("Duplicate security performance rows", message)
        self.assertIn("PORT", message)
        self.assertIn("2023-12-31", message)
        self.assertIn("2024-01-31", message)
        self.assertIn("A", message)

    def test_unreachable_period_return_raises_reconciliation_error(self) -> None:
        """A target outside the available return range cannot be reconciled."""
        portfolio_performance = _single_period_portfolio_performance(0.10)
        security_performance = _single_period_security_performance(
            contributions=[0.005, 0.01],
            returns=[0.01, 0.02],
            weights=[0.50, 0.50],
        )

        with self.assertRaises(PparError):
            derive_security_performance_for_all_periods(
                portfolio_performance,
                security_performance,
                _error_message,
            )

    def test_linked_reconciliation_difference_cannot_cancel_period_residuals(self) -> None:
        """Opposing simple residuals remain visible after geometric linking."""
        periods = {
            (("PORT", dt.date(2024, 1, 1), dt.date(2024, 1, 31)), 0.75, 0.75009),
            (("PORT", dt.date(2024, 2, 1), dt.date(2024, 2, 29)), -0.75, -0.75009),
        }

        difference = unreconciled_difference(periods)

        self.assertTrue(
            math.isclose(
                sum(target - achieved for _, target, achieved in periods),
                0.0,
            )
        )
        self.assertGreater(difference, 0.0001)
        self.assertTrue(exceeds_fatal_tolerance(difference))

    def test_linked_reconciliation_difference_handles_same_sign_residuals(self) -> None:
        """Same-sign residuals compare complete linked target and achieved paths."""
        periods = {
            (("PORT", dt.date(2024, 1, 1), dt.date(2024, 1, 31)), 0.10, 0.10004),
            (("PORT", dt.date(2024, 2, 1), dt.date(2024, 2, 29)), 0.20, 0.20004),
        }
        expected = abs((1.10 * 1.20) - (1.10004 * 1.20004))

        self.assertTrue(
            math.isclose(
                unreconciled_difference(periods),
                expected,
                abs_tol=1e-15,
            )
        )

    def test_linked_reconciliation_difference_tolerates_floating_noise(self) -> None:
        """Benign floating noise remains beneath the unchanged fatal tolerance."""
        periods = {
            (("PORT", dt.date(2024, 1, 1), dt.date(2024, 1, 31)), 0.01, 0.01000000001),
            (("PORT", dt.date(2024, 2, 1), dt.date(2024, 2, 29)), -0.02, -0.02000000001),
        }

        self.assertFalse(exceeds_fatal_tolerance(unreconciled_difference(periods)))


if __name__ == "__main__":
    unittest.main()
