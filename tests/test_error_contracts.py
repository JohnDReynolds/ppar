"""Public contracts for structured ppar errors and exact pair inputs."""

import unittest
from typing import cast, Sequence

import numpy as np

from ppar.attribution import Attribution
from ppar.frequency import Frequency
from ppar.performance import Performance
from ppar.risk import RiskStatistics
from ppar.errors import PparError


class TestPparErrorContracts(unittest.TestCase):
    """Verify package failures expose concise text and optional context."""

    def test_error_exposes_message_and_context(self) -> None:
        """Diagnostic context supplements rather than replaces readable text."""
        error = PparError(
            "calculation detail",
            context={"portfolio_id": "BALANCED", "period": "2024-01"},
        )

        self.assertEqual(
            error.context,
            {"portfolio_id": "BALANCED", "period": "2024-01"},
        )
        self.assertEqual(str(error), "calculation detail")

    def test_error_defaults_to_empty_context(self) -> None:
        """Callers need not provide diagnostic context."""
        error = PparError("plain detail")

        self.assertEqual(error.context, {})
        self.assertEqual(str(error), "plain detail")


class TestExactPairContracts(unittest.TestCase):
    """Verify public portfolio/benchmark boundaries require exactly two items."""

    def test_risk_statistics_rejects_wrong_sequence_lengths(self) -> None:
        """Risk inputs cannot raise IndexError or silently ignore extra arrays."""
        returns = np.array([0.01, 0.02], dtype=np.float64)
        for sequence in ((), (returns,), (returns, returns, returns)):
            with self.subTest(length=len(sequence)):
                with self.assertRaises(PparError):
                    RiskStatistics(sequence, Frequency.MONTHLY)

    def test_attribution_rejects_wrong_performance_sequence_lengths(self) -> None:
        """Direct Attribution construction validates its pair before indexing."""
        for sequence in ((), (None,), (None, None, None)):
            with self.subTest(length=len(sequence)):
                with self.assertRaises(PparError):
                    Attribution(
                        cast(Sequence[Performance], sequence),
                        classification_name=None,
                        classification_data_source=None,
                        frequency=Frequency.AS_OFTEN_AS_POSSIBLE,
                    )


if __name__ == "__main__":
    unittest.main()
