"""Deterministic property tests for core Analytics financial identities."""

# Python imports
import datetime as dt
import math
import unittest

# Third-party imports
import numpy as np
import polars as pl

# Project imports
from ppar import Analytics
from ppar.attribution import View
import ppar.schema as cols


_PERIODS = (
    (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
    (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
    (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
    (dt.date(2024, 4, 1), dt.date(2024, 4, 30)),
)
_IDENTIFIERS = ("A", "B", "C", "D", "E")


def _random_performance(
    rng: np.random.Generator,
) -> tuple[pl.DataFrame, list[float]]:
    """Return reproducible long/short performance rows and independent totals."""
    rows: list[dict[str, object]] = []
    expected_returns: list[float] = []
    for from_date, thru_date in _PERIODS:
        partial_weights = rng.uniform(-0.25, 0.65, len(_IDENTIFIERS) - 1)
        weights = np.append(partial_weights, 1.0 - partial_weights.sum())
        returns = rng.uniform(-0.20, 0.20, len(_IDENTIFIERS))
        expected_returns.append(float(np.dot(weights, returns)))
        rows.extend(
            {
                cols.FROM_DATE: from_date,
                cols.THRU_DATE: thru_date,
                cols.IDENTIFIER: identifier,
                cols.WEIGHT: float(weight),
                cols.RETURN: float(return_value),
            }
            for identifier, weight, return_value in zip(
                _IDENTIFIERS,
                weights,
                returns,
            )
        )
    return pl.DataFrame(rows), expected_returns


class TestFinancialMetamorphicInvariants(unittest.TestCase):
    """Exercise identities over varied inputs without depending on golden files."""

    def test_varied_inputs_are_order_independent_and_reconcile(self) -> None:
        """Row permutations preserve results and every calculation level foots."""
        for seed in range(10):
            with self.subTest(seed=seed):
                rng = np.random.default_rng(seed)
                portfolio, expected_portfolio_returns = _random_performance(rng)
                benchmark, expected_benchmark_returns = _random_performance(rng)

                attribution = Analytics(portfolio, benchmark).attribution()
                shuffled_attribution = Analytics(
                    portfolio.sample(fraction=1.0, shuffle=True, seed=seed),
                    benchmark.sample(fraction=1.0, shuffle=True, seed=seed + 100),
                ).attribution()

                for view in View:
                    self.assertTrue(
                        attribution.to_polars(view).equals(
                            shuffled_attribution.to_polars(view)
                        ),
                        msg=f"{view.value} changed after source-row permutation",
                    )

                summary = attribution.to_polars(View.SUBPERIOD_SUMMARY)
                for row_index, (portfolio_return, benchmark_return) in enumerate(
                    zip(expected_portfolio_returns, expected_benchmark_returns)
                ):
                    active_return = portfolio_return - benchmark_return
                    self.assertTrue(
                        math.isclose(
                            summary[cols.PORTFOLIO_RETURN].item(row_index),
                            portfolio_return,
                            abs_tol=1e-12,
                        )
                    )
                    self.assertTrue(
                        math.isclose(
                            summary[cols.BENCHMARK_RETURN].item(row_index),
                            benchmark_return,
                            abs_tol=1e-12,
                        )
                    )
                    self.assertTrue(
                        math.isclose(
                            summary[cols.ACTIVE_RETURN].item(row_index),
                            active_return,
                            abs_tol=1e-12,
                        )
                    )
                    self.assertTrue(
                        math.isclose(
                            summary[cols.TOTAL_EFFECT_SIMPLE].item(row_index),
                            active_return,
                            abs_tol=1e-12,
                        )
                    )

                expected_linked_portfolio = (
                    math.prod(1.0 + value for value in expected_portfolio_returns) - 1.0
                )
                expected_linked_benchmark = (
                    math.prod(1.0 + value for value in expected_benchmark_returns) - 1.0
                )
                expected_linked_active = (
                    expected_linked_portfolio - expected_linked_benchmark
                )
                overall_total = attribution.to_polars(View.OVERALL_ATTRIBUTION)[-1]

                self.assertTrue(
                    math.isclose(
                        overall_total[cols.PORTFOLIO_RETURN].item(),
                        expected_linked_portfolio,
                        abs_tol=1e-12,
                    )
                )
                self.assertTrue(
                    math.isclose(
                        overall_total[cols.BENCHMARK_RETURN].item(),
                        expected_linked_benchmark,
                        abs_tol=1e-12,
                    )
                )
                self.assertTrue(
                    math.isclose(
                        overall_total[cols.TOTAL_EFFECT_SMOOTHED].item(),
                        expected_linked_active,
                        abs_tol=1e-12,
                    )
                )


if __name__ == "__main__":
    unittest.main()
