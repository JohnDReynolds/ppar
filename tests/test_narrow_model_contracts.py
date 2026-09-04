"""Verify the ppar-owned risk calculation from narrow performance input."""

import datetime as dt
import unittest

from ppar import Analytics
from ppar.frequency import Frequency
from tests import helpers as test_util


_MONTHLY_PERIODS: tuple[test_util.Period, ...] = (
    (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
    (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
    (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
    (dt.date(2024, 4, 1), dt.date(2024, 4, 30)),
    (dt.date(2024, 5, 1), dt.date(2024, 5, 31)),
    (dt.date(2024, 6, 1), dt.date(2024, 6, 30)),
    (dt.date(2024, 7, 1), dt.date(2024, 7, 31)),
    (dt.date(2024, 8, 1), dt.date(2024, 8, 31)),
    (dt.date(2024, 9, 1), dt.date(2024, 9, 30)),
    (dt.date(2024, 10, 1), dt.date(2024, 10, 31)),
    (dt.date(2024, 11, 1), dt.date(2024, 11, 30)),
    (dt.date(2024, 12, 1), dt.date(2024, 12, 31)),
)


class TestNarrowModelContracts(unittest.TestCase):
    """Keep the narrow-input contract for calculations still owned by ppar."""

    def test_risk_statistics_values_from_narrow_inputs_are_stable(self) -> None:
        """Narrow monthly inputs feed stable ppar risk-statistics results."""
        portfolio = test_util.make_performance_df(
            _MONTHLY_PERIODS,
            {"A": ([0.01, -0.02, 0.03, 0.01, -0.01, 0.02] * 2, [1.0] * 12)},
        )
        benchmark = test_util.make_performance_df(
            _MONTHLY_PERIODS,
            {"A": ([0.005, -0.01, 0.02, 0.015, -0.005, 0.01] * 2, [1.0] * 12)},
        )

        output = Analytics(
            portfolio,
            benchmark,
            frequency=Frequency.MONTHLY,
        ).risk_statistics().to_polars()
        portfolio_values = dict(zip(output["column"], output["Portfolio"]))
        benchmark_values = dict(zip(output["column"], output["Benchmark"]))

        self.assertAlmostEqual(
            portfolio_values["Monthly Mean Return"],
            0.006666666666666666,
        )
        self.assertAlmostEqual(
            benchmark_values["Monthly Mean Return"],
            0.005833333333333333,
        )
        self.assertAlmostEqual(
            portfolio_values["Monthly Tracking Error"],
            0.007861650943380503,
        )


if __name__ == "__main__":
    unittest.main()
