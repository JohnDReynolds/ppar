"""Focused in-memory tests for Axys security performance reconciliation."""

# Python Imports
import datetime as dt
import math
import unittest

# Third-Party Imports
import polars as pl

# Project Imports
from ppar.axys_apx.reconciliation import (
    derive_reconciled_weights,
    derive_security_performance_for_all_periods,
    filter_to_common_periods,
)
import ppar.schema as cols
from ppar.errors import PparError


_FROM_DATE = dt.date(2023, 12, 31)
_THRU_DATE = dt.date(2024, 1, 31)


def _error_message(message: str) -> str:
    """Return calculation-only error details unchanged."""
    return message


def _single_period_security_performance(
    contributions: list[float | None],
    returns: list[float | None],
    weights: list[float | None],
    identifiers: list[str] | None = None,
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

    def test_invalid_anchors_fall_back_to_equal_weights(self) -> None:
        """Null and negative unusable inputs still produce valid normalized weights."""
        security_performance = _single_period_security_performance(
            contributions=[None, None],
            returns=[0.0, 0.0],
            weights=[None, -0.50],
        )

        weights, achieved_return = derive_reconciled_weights(
            security_performance,
            portfolio_return=0.0,
        )

        self.assertEqual(weights, [0.50, 0.50])
        self.assertTrue(math.isclose(achieved_return, 0.0, abs_tol=1e-12))

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

    def test_filter_to_common_periods_removes_unmatched_periods(self) -> None:
        """Only periods represented in both files proceed to reconciliation."""
        february_end = dt.date(2024, 2, 29)
        march_end = dt.date(2024, 3, 31)
        portfolio_performance = pl.DataFrame(
            {
                cols.PORTFOLIO_CODE: ["PORT", "PORT"],
                cols.FROM_DATE: [_FROM_DATE, _THRU_DATE],
                cols.THRU_DATE: [_THRU_DATE, february_end],
                cols.PORTFOLIO_RETURN: [0.04, 0.03],
            }
        )
        security_performance = pl.DataFrame(
            {
                cols.PORTFOLIO_CODE: ["PORT", "PORT"],
                cols.FROM_DATE: [_THRU_DATE, february_end],
                cols.THRU_DATE: [february_end, march_end],
                cols.IDENTIFIER: ["A", "A"],
            }
        )

        portfolio_performance, security_performance = filter_to_common_periods(
            portfolio_performance,
            security_performance,
            _error_message,
        )

        self.assertEqual(portfolio_performance[cols.THRU_DATE].to_list(), [february_end])
        self.assertEqual(security_performance[cols.THRU_DATE].to_list(), [february_end])

    def test_all_period_reconciliation_preserves_duplicate_identifier_rows(self) -> None:
        """Row-grain inputs remain separate even when identifiers repeat."""
        portfolio_performance = _single_period_portfolio_performance(0.04)
        security_performance = _single_period_security_performance(
            contributions=[0.06, -0.02],
            returns=[0.10, -0.05],
            weights=[0.50, 0.50],
            identifiers=["A", "A"],
        )

        reconciled, unreconciled = derive_security_performance_for_all_periods(
            portfolio_performance, security_performance, _error_message
        )

        self.assertEqual(unreconciled, set())
        self.assertEqual(reconciled.height, 2)
        self.assertEqual(reconciled[cols.IDENTIFIER].to_list(), ["A", "A"])
        weights = reconciled[cols.WEIGHT].to_list()
        self.assertTrue(math.isclose(weights[0], 0.60, abs_tol=1e-12))
        self.assertTrue(math.isclose(weights[1], 0.40, abs_tol=1e-12))

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


if __name__ == "__main__":
    unittest.main()
