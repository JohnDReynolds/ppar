"""Focused in-memory tests for ex-post risk-statistics calculations."""

# Python Imports
import datetime as dt
import math
import unittest

# Third-Party Imports
import numpy as np
import polars as pl

# Project Imports
from ppar import Analytics
import ppar.schema as cols
from ppar.frequency import Frequency
from ppar.risk import RiskStatistics
import ppar.utilities as util


def _monthly_risk_statistics(
    portfolio_returns: list[float],
    benchmark_returns: list[float],
    annual_minimum_acceptable_return: float = util.DEFAULT_ANNUAL_MINIMUM_ACCEPTABLE_RETURN,
    annual_risk_free_rate: float = util.DEFAULT_ANNUAL_RISK_FREE_RATE,
    confidence_level: float = util.DEFAULT_CONFIDENCE_LEVEL,
    portfolio_value: tuple[float, str] = (
        util.DEFAULT_PORTFOLIO_VALUE,
        util.DEFAULT_CURRENCY_SYMBOL,
    ),
) -> RiskStatistics:
    """Construct monthly risk statistics from simple return lists.

    Args:
        portfolio_returns: Periodic portfolio returns.
        benchmark_returns: Periodic benchmark returns.
        annual_minimum_acceptable_return: Annual return hurdle for downside
            calculations.
        annual_risk_free_rate: Annual cash return for adjusted ratios.
        confidence_level: Probability level used in value at risk.
        portfolio_value: Portfolio value and currency display symbol.

    Returns:
        Monthly risk statistics for the supplied arrays.
    """
    return RiskStatistics(
        (np.array(portfolio_returns), np.array(benchmark_returns)),
        Frequency.MONTHLY,
        annual_minimum_acceptable_return,
        annual_risk_free_rate,
        confidence_level,
        portfolio_value,
    )


def _portfolio_value(risk_statistics: RiskStatistics, statistic_name: str) -> float:
    """Return the portfolio result for a labeled statistic row.

    Args:
        risk_statistics: Calculated risk statistics object.
        statistic_name: Exact output label in the ``column`` field.

    Returns:
        Portfolio result from the requested output row.
    """
    result = risk_statistics.to_polars().filter(pl.col("column") == statistic_name)
    return float(result["Portfolio"].item())


class TestRiskStatisticsInvariants(unittest.TestCase):
    """Test financial identities and parameter effects without data files."""

    def test_identical_returns_have_zero_tracking_error(self) -> None:
        """Identical series have no benchmark-relative dispersion."""
        returns = [0.01, -0.02, 0.04, 0.03]
        risk_statistics = _monthly_risk_statistics(returns, returns)

        tracking_error = _portfolio_value(
            risk_statistics,
            "Monthly Tracking Error",
        )

        self.assertTrue(math.isclose(tracking_error, 0.0, abs_tol=1e-12))

    def test_identical_returns_have_unit_beta(self) -> None:
        """A nonconstant return series regressed against itself has beta one."""
        returns = [0.01, -0.02, 0.04, 0.03]
        risk_statistics = _monthly_risk_statistics(returns, returns)

        beta = _portfolio_value(risk_statistics, "Monthly Beta")

        self.assertTrue(math.isclose(beta, 1.0, abs_tol=1e-12))

    def test_identical_returns_have_zero_alpha_when_risk_free_rate_is_zero(self) -> None:
        """A series regressed against itself has no intercept at a zero cash rate."""
        returns = [0.01, -0.02, 0.04, 0.03]
        risk_statistics = _monthly_risk_statistics(
            returns,
            returns,
            annual_risk_free_rate=0.0,
        )

        alpha = _portfolio_value(risk_statistics, "Monthly Alpha")

        self.assertTrue(math.isclose(alpha, 0.0, abs_tol=1e-12))

    def test_downside_deviation_uses_only_returns_below_hurdle(self) -> None:
        """Above-hurdle observations contribute zero downside shortfall."""
        returns = [-0.02, 0.01, 0.03, -0.01]
        risk_statistics = _monthly_risk_statistics(
            returns,
            returns,
            annual_minimum_acceptable_return=0.0,
        )

        downside_deviation = _portfolio_value(
            risk_statistics,
            "Monthly Downside Deviation",
        )
        expected = math.sqrt(((0.02**2) + (0.01**2)) / len(returns))

        self.assertTrue(math.isclose(downside_deviation, expected, abs_tol=1e-12))

    def test_sortino_uses_mar_shortfalls_across_all_observations(self) -> None:
        """Sortino uses the MAR numerator and full-population downside deviation."""
        returns = [-0.02, 0.01, 0.03, -0.01]
        risk_statistics = _monthly_risk_statistics(
            returns,
            returns,
            annual_minimum_acceptable_return=0.0,
            annual_risk_free_rate=0.12,
        )

        sortino = _portfolio_value(risk_statistics, "Monthly Sortino Ratio")
        expected_downside_deviation = math.sqrt(((0.02**2) + (0.01**2)) / len(returns))
        expected = (sum(returns) / len(returns)) / expected_downside_deviation

        self.assertTrue(math.isclose(sortino, expected, abs_tol=1e-12))

    def test_zero_volatility_ratios_preserve_negative_numerator_sign(self) -> None:
        """Zero positive-risk denominators produce signed infinity."""
        risk_statistics = _monthly_risk_statistics(
            [-0.01, -0.01, -0.01, -0.01],
            [-0.02, -0.01, 0.01, 0.02],
            annual_minimum_acceptable_return=0.0,
            annual_risk_free_rate=0.0,
        )

        sharpe = _portfolio_value(risk_statistics, "Monthly Sharpe Ratio")

        self.assertTrue(math.isinf(sharpe))
        self.assertLess(sharpe, 0.0)

    def test_zero_tracking_error_information_ratio_preserves_sign(self) -> None:
        """Constant negative active return produces negative infinity."""
        benchmark = [0.01, 0.02, 0.03, 0.04]
        portfolio = [value - 0.01 for value in benchmark]
        risk_statistics = _monthly_risk_statistics(portfolio, benchmark)

        information_ratio = _portfolio_value(
            risk_statistics,
            "Monthly Information Ratio",
        )

        self.assertTrue(math.isinf(information_ratio))
        self.assertLess(information_ratio, 0.0)

    def test_zero_beta_treynor_ratio_preserves_sign(self) -> None:
        """Zero beta with negative excess return produces negative infinity."""
        risk_statistics = _monthly_risk_statistics(
            [0.01, -0.01, -0.01, 0.01],
            [-0.02, -0.01, 0.01, 0.02],
            annual_risk_free_rate=0.03,
        )

        treynor = _portfolio_value(risk_statistics, "Monthly Treynor Ratio")

        self.assertTrue(math.isinf(treynor))
        self.assertLess(treynor, 0.0)

    def test_value_at_risk_increases_with_confidence_level(self) -> None:
        """A more adverse lower-tail confidence level increases reported loss."""
        returns = [-0.04, -0.01, 0.02, 0.06]
        low_confidence = _monthly_risk_statistics(
            returns,
            returns,
            confidence_level=0.90,
        )
        high_confidence = _monthly_risk_statistics(
            returns,
            returns,
            confidence_level=0.99,
        )

        low_var = _portfolio_value(
            low_confidence,
            "Monthly Value At Risk for $100,000",
        )
        high_var = _portfolio_value(
            high_confidence,
            "Monthly Value At Risk for $100,000",
        )

        self.assertGreater(high_var, low_var)

    def test_value_at_risk_scales_with_portfolio_value(self) -> None:
        """Doubling portfolio value doubles reported value at risk."""
        returns = [-0.04, -0.01, 0.02, 0.06]
        lower_value = _monthly_risk_statistics(
            returns,
            returns,
            portfolio_value=(100_000.0, "$"),
        )
        higher_value = _monthly_risk_statistics(
            returns,
            returns,
            portfolio_value=(200_000.0, "$"),
        )

        lower_var = _portfolio_value(
            lower_value,
            "Monthly Value At Risk for $100,000",
        )
        higher_var = _portfolio_value(
            higher_value,
            "Monthly Value At Risk for $200,000",
        )

        self.assertTrue(math.isclose(higher_var, 2 * lower_var, abs_tol=1e-9))

    def test_regression_and_active_risk_statistics_obey_core_identities(self) -> None:
        """R-squared, tracking error, and information ratio reconcile independently."""
        portfolio = np.array([0.04, -0.01, 0.03, 0.00, 0.06, -0.02])
        benchmark = np.array([0.02, -0.02, 0.01, 0.01, 0.03, -0.01])
        risk_statistics = RiskStatistics((portfolio, benchmark), Frequency.MONTHLY)

        correlation = _portfolio_value(risk_statistics, "Monthly Correlation")
        r_squared = _portfolio_value(risk_statistics, "Monthly R-Squared")
        tracking_error = _portfolio_value(risk_statistics, "Monthly Tracking Error")
        information_ratio = _portfolio_value(risk_statistics, "Monthly Information Ratio")
        active_returns = portfolio - benchmark

        self.assertTrue(math.isclose(r_squared, correlation**2, abs_tol=1e-12))
        self.assertTrue(
            math.isclose(tracking_error, float(np.std(active_returns)), abs_tol=1e-12)
        )
        self.assertTrue(
            math.isclose(
                information_ratio,
                float(np.mean(active_returns) / np.std(active_returns)),
                abs_tol=1e-12,
            )
        )

    def test_equivalent_monthly_and_quarterly_means_annualize_equally(self) -> None:
        """Periodic means derived from one annual return annualize equally."""
        annual_return = 0.12
        monthly_mean = (1.0 + annual_return) ** (1 / 12) - 1.0
        quarterly_mean = (1.0 + annual_return) ** (1 / 4) - 1.0
        monthly_returns = [monthly_mean - 0.001, monthly_mean + 0.001] * 6
        quarterly_returns = [quarterly_mean - 0.001, quarterly_mean + 0.001] * 2
        monthly = _monthly_risk_statistics(monthly_returns, monthly_returns)
        quarterly = RiskStatistics(
            (np.array(quarterly_returns), np.array(quarterly_returns)),
            Frequency.QUARTERLY,
        )

        monthly_annual = _portfolio_value(monthly, "Annualized Mean Return")
        quarterly_annual = _portfolio_value(quarterly, "Annualized Mean Return")

        self.assertTrue(math.isclose(monthly_annual, annual_return, abs_tol=1e-12))
        self.assertTrue(math.isclose(quarterly_annual, annual_return, abs_tol=1e-12))

    def test_analytics_caches_risk_statistics_instance(self) -> None:
        """Repeated risk-statistics retrieval reuses the calculated result."""
        data_source = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1), dt.date(2024, 2, 1)],
                cols.THRU_DATE: [dt.date(2024, 1, 31), dt.date(2024, 2, 29)],
                cols.IDENTIFIER: ["A", "A"],
                cols.RETURN: [0.01, -0.02],
                cols.WEIGHT: [1.0, 1.0],
            }
        )
        analytics = Analytics(data_source, frequency=Frequency.MONTHLY)

        first = analytics.risk_statistics()
        second = analytics.risk_statistics()

        self.assertIs(first, second)

    def test_polars_result_cannot_mutate_cached_statistics(self) -> None:
        """Risk-statistics table retrieval returns a defensive DataFrame copy."""
        risk_statistics = _monthly_risk_statistics(
            [0.01, -0.02, 0.03, 0.04],
            [0.00, -0.01, 0.02, 0.03],
        )
        returned = risk_statistics.to_polars()
        returned[0, "Portfolio"] = 999.0

        self.assertNotEqual(risk_statistics.to_polars()["Portfolio"].item(0), 999.0)


if __name__ == "__main__":
    unittest.main()
