"""Focused validation tests for invalid and boundary risk-statistics inputs."""

# Python Imports
import datetime as dt
import math
import unittest

# Third-Party Imports
import numpy as np
import polars as pl

# Project Imports
import ppar.schema as cols
from ppar.errors import PparError
from ppar.frequency import Frequency
from ppar.performance import Performance
from ppar.risk import RiskStatistics


class TestRiskStatisticsValidation(unittest.TestCase):
    """Verify risk-statistics input rejection and calculation boundaries."""

    def test_unsupported_frequency_is_rejected(self) -> None:
        """Daily-frequency risk statistics are not supported."""
        with self.assertRaises(PparError):
            RiskStatistics(
                (np.array([np.nan, np.nan]), np.array([np.nan, np.nan])),
                Frequency.AS_OFTEN_AS_POSSIBLE,
            )

    def test_insufficient_returns_are_rejected(self) -> None:
        """At least two observations are required to calculate statistics."""
        with self.assertRaises(PparError):
            RiskStatistics(
                (np.array([np.nan]), np.array([np.nan])),
                Frequency.MONTHLY,
            )

    def test_mismatched_return_counts_are_rejected(self) -> None:
        """Portfolio and benchmark arrays must contain matching periods."""
        with self.assertRaises(PparError):
            RiskStatistics(
                (np.array([np.nan, np.nan]), np.array([np.nan, np.nan, np.nan])),
                Frequency.MONTHLY,
            )

    def test_nan_returns_are_rejected(self) -> None:
        """Missing observations are not valid calculated risk inputs."""
        with self.assertRaises(PparError):
            RiskStatistics(
                (np.array([1.0, 2.0]), np.array([1.0, np.nan])),
                Frequency.MONTHLY,
            )

    def test_infinite_returns_are_rejected(self) -> None:
        """Infinite observations cannot enter risk calculations."""
        with self.assertRaises(PparError):
            RiskStatistics(
                (np.array([1.0, 2.0]), np.array([1.0, np.inf])),
                Frequency.MONTHLY,
            )

    def test_returns_at_or_below_negative_one_are_rejected(self) -> None:
        """Periodic returns must remain inside the geometric-compounding domain."""
        invalid_returns = (-1.0, -1.0000001, -2.0)
        for invalid_return in invalid_returns:
            for source_index in (0, 1):
                with self.subTest(
                    invalid_return=invalid_return,
                    source_index=source_index,
                ):
                    return_pair = [
                        np.array([0.01, 0.02] * 6),
                        np.array([0.01, 0.02] * 6),
                    ]
                    return_pair[source_index][3] = invalid_return

                    with self.assertRaisesRegex(
                        PparError,
                        "exceed -100%",
                    ) as raised:
                        RiskStatistics(tuple(return_pair), Frequency.MONTHLY)
                    self.assertEqual(
                        raised.exception.context["return_source"],
                        ("portfolio", "benchmark")[source_index],
                    )
                    self.assertEqual(
                        raised.exception.context["invalid_returns"],
                        [{"index": 3, "return": invalid_return}],
                    )

    def test_repeated_negative_two_returns_fail_before_annualization(self) -> None:
        """Twelve negative-200-percent periods cannot produce an annual return."""
        returns = np.full(12, -2.0)

        with self.assertRaisesRegex(PparError, "exceed -100%"):
            RiskStatistics((returns, returns.copy()), Frequency.MONTHLY)

    def test_valid_leveraged_return_boundaries_are_accepted(self) -> None:
        """Returns above negative 100 percent remain valid without an upper cap."""
        returns = np.array([-0.999999999, -0.75, -0.01, 0.0, 1.0, 5.0])

        risk_statistics = RiskStatistics(
            (returns, returns.copy()),
            Frequency.MONTHLY,
        )

        self.assertFalse(risk_statistics.to_polars().is_empty())

    def test_performance_total_return_at_negative_one_is_rejected(self) -> None:
        """Portable preparation rejects an undefined wealth relative at entry."""
        source = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1), dt.date(2024, 2, 1)],
                cols.THRU_DATE: [dt.date(2024, 1, 31), dt.date(2024, 2, 29)],
                cols.IDENTIFIER: ["A", "A"],
                cols.RETURN: [-1.0, 0.02],
                cols.WEIGHT: [1.0, 1.0],
            }
        )
        with self.assertRaisesRegex(PparError, "greater than -1.0"):
            Performance(source)

    def test_derived_return_below_negative_one_cannot_be_annualized(self) -> None:
        """A valid regression cannot publish an invalid compounded alpha."""
        benchmark = np.array([0.80, 0.90] * 6)
        portfolio = -8.90 + (10.0 * benchmark)

        with self.assertRaisesRegex(PparError, "Annualized Alpha.*exceed -100%"):
            RiskStatistics((portfolio, benchmark), Frequency.MONTHLY)

    def test_invalid_financial_parameters_are_rejected(self) -> None:
        """Rates, confidence, portfolio value, and currency label are validated."""
        returns = (np.array([0.01, 0.02]), np.array([0.01, 0.02]))
        invalid_arguments = (
            {"annual_minimum_acceptable_return": float("inf")},
            {"annual_risk_free_rate": -1.0},
            {"confidence_level": 0.0},
            {"confidence_level": 1.0},
            {"portfolio_value": (-1.0, "$")},
            {"portfolio_value": (100_000.0, 1)},
        )
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(PparError):
                    RiskStatistics(
                        returns,
                        Frequency.MONTHLY,
                        **arguments,  # type: ignore[arg-type]
                    )

    def test_invalid_return_source_shapes_and_types_are_rejected(self) -> None:
        """Return inputs must be a homogeneous pair of one-dimensional arrays."""
        invalid_returns = (
            (np.array([[0.01, 0.02]]), np.array([[0.01, 0.02]])),
            (np.array(["bad", "data"]), np.array(["bad", "data"])),
            (np.array([0.01 + 0.02j, 0.03]), np.array([0.01, 0.02])),
            (np.array([0.01, 0.02]), [0.01, 0.02]),
        )
        for returns in invalid_returns:
            with self.subTest(returns=returns):
                with self.assertRaises(PparError):
                    RiskStatistics(returns, Frequency.MONTHLY)  # type: ignore[arg-type]

    def test_annualized_statistics_are_nan_for_less_than_one_year(self) -> None:
        """Annualized statistics require at least one year of return periods."""
        risk_statistics = RiskStatistics(
            (np.array([1, 2, 3]), np.array([4, 5, 6])),
            Frequency.QUARTERLY,
        )
        output = risk_statistics.to_polars()

        self.assertTrue(math.isnan(output["Portfolio"].item(2)))
        self.assertTrue(math.isnan(output["Benchmark"].item(2)))

    def test_parametric_var_uses_lower_tail_loss(self) -> None:
        """Value at risk reports lower-tail loss rather than upper-tail movement."""
        risk_statistics = RiskStatistics(
            (np.array([-0.01, 0.03]), np.array([-0.01, 0.03])),
            Frequency.MONTHLY,
            confidence_level=0.95,
            portfolio_value=(100_000, "$"),
        )
        output = risk_statistics.to_polars()
        value_at_risk = output.filter(pl.col("column") == "Monthly Value At Risk for $100,000")[
            "Portfolio"
        ].item()

        self.assertTrue(
            math.isclose(
                value_at_risk,
                2289.7072539029457,
            )
        )

    def test_performance_inputs_must_have_aligned_dates(self) -> None:
        """Direct Performance inputs require matching reporting periods."""
        portfolio = Performance(
            pl.DataFrame(
                {
                    cols.FROM_DATE: [dt.date(2023, 2, 1), dt.date(2023, 3, 1)],
                    cols.THRU_DATE: [dt.date(2023, 2, 28), dt.date(2023, 3, 31)],
                    cols.IDENTIFIER: ["A", "A"],
                    cols.RETURN: [0.01, 0.02],
                    cols.WEIGHT: [1.0, 1.0],
                }
            )
        )
        benchmark = Performance(
            pl.DataFrame(
                {
                    cols.FROM_DATE: [dt.date(2023, 3, 1), dt.date(2023, 4, 1)],
                    cols.THRU_DATE: [dt.date(2023, 3, 31), dt.date(2023, 4, 30)],
                    cols.IDENTIFIER: ["A", "A"],
                    cols.RETURN: [0.03, 0.04],
                    cols.WEIGHT: [1.0, 1.0],
                }
            )
        )

        with self.assertRaises(PparError):
            RiskStatistics((portfolio, benchmark), Frequency.MONTHLY)


if __name__ == "__main__":
    unittest.main()
