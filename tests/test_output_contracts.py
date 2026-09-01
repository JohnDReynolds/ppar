"""Focused tests for Polars, CSV, HTML, and chart outputs."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import tempfile
import unittest

import numpy as np
import polars as pl

from ppar import Analytics
from ppar.attribution import Chart, View
from ppar.errors import PparError
from ppar.frequency import Frequency
from ppar.risk import RiskStatistics
import ppar.schema as cols


def _attribution():  # type annotation would repeat the obvious public call result
    """Return a small attribution result for output tests."""
    performance = pl.DataFrame(
        {
            cols.FROM_DATE: [dt.date(2024, 1, 1)] * 2 + [dt.date(2024, 2, 1)] * 2,
            cols.THRU_DATE: [dt.date(2024, 1, 31)] * 2 + [dt.date(2024, 2, 29)] * 2,
            cols.IDENTIFIER: ["A", "B", "A", "B"],
            cols.RETURN: [0.10, -0.05, 0.02, 0.03],
            cols.WEIGHT: [0.60, 0.40, 0.40, 0.60],
        }
    )
    classifications = pl.DataFrame({"id": ["A", "B"], "name": ["Alpha", "Beta"]})
    return Analytics(
        performance,
        portfolio_classification_name="Security",
    ).attribution("Security", classifications)


def _risk_statistics() -> RiskStatistics:
    """Return monthly statistics with stable values."""
    portfolio = np.array([0.01, -0.02, 0.03, 0.01, -0.01, 0.02] * 2)
    benchmark = np.array([0.005, -0.01, 0.02, 0.015, -0.005, 0.01] * 2)
    return RiskStatistics(
        (portfolio, benchmark),
        Frequency.MONTHLY,
        portfolio_value=(250_000.0, "$"),
    )


class TestAttributionOutputs(unittest.TestCase):
    """Attribution exposes one machine-readable table API plus presentation APIs."""

    def test_polars_contains_the_total_row(self) -> None:
        """The focused table API retains the calculated view contract."""
        frame = _attribution().to_polars(View.OVERALL_ATTRIBUTION)
        self.assertIsInstance(frame, pl.DataFrame)
        self.assertEqual(frame[cols.CLASSIFICATION_NAME].item(-1), "Total")

    def test_csv_preserves_polars_columns_and_precision(self) -> None:
        """CSV output preserves the selected view's established columns."""
        attribution = _attribution()
        expected = attribution.to_polars(View.OVERALL_ATTRIBUTION)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attribution.csv"
            attribution.write_csv(View.OVERALL_ATTRIBUTION, path, float_precision=6)
            actual = pl.read_csv(path)
        self.assertEqual(actual.columns, expected.columns)
        self.assertEqual(actual.height, expected.height)

    def test_html_and_png_chart_render(self) -> None:
        """Both retained presentation boundaries produce complete artifacts."""
        attribution = _attribution()
        html = attribution.to_html(View.OVERALL_ATTRIBUTION)
        png = attribution.to_chart(Chart.OVERALL_ATTRIBUTION)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_unnamed_dataframe_inputs_use_title_fallbacks(self) -> None:
        """Presentation output never exposes an empty comparison title."""
        html = _attribution().to_html(View.OVERALL_ATTRIBUTION)

        self.assertIn("Portfolio vs Benchmark", html)
        self.assertNotIn("> vs <", html)

    def test_removed_conversion_methods_are_absent(self) -> None:
        """The public table surface does not duplicate dataframe libraries."""
        attribution = _attribution()
        for method in ("to_json", "to_pandas", "to_table", "to_xml"):
            self.assertFalse(hasattr(attribution, method))

    def test_invalid_float_precision_is_rejected(self) -> None:
        """Serialization keeps its bounded precision invariant."""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PparError):
                _attribution().write_csv(
                    View.OVERALL_ATTRIBUTION,
                    Path(directory) / "result.csv",
                    float_precision=16,
                )


class TestRiskOutputs(unittest.TestCase):
    """Risk statistics use the same focused output conventions."""

    def test_polars_html_and_csv_render(self) -> None:
        """Every retained output boundary returns its documented representation."""
        risk = _risk_statistics()
        self.assertIsInstance(risk.to_polars(), pl.DataFrame)
        self.assertTrue(risk.to_html().startswith("<!DOCTYPE html>"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "risk.csv"
            risk.write_csv(path, float_precision=3)
            self.assertEqual(pl.read_csv(path).columns, risk.to_polars().columns)

    def test_direct_arrays_omit_unavailable_dates_from_html(self) -> None:
        """Array-backed risk output uses fallbacks without sentinel dates."""
        html = _risk_statistics().to_html()

        self.assertIn("Portfolio vs Benchmark", html)
        self.assertIn("Ex-Post Risk Statistics: Monthly", html)
        self.assertNotIn("Ex-Post Risk Statistics: Monthly from", html)
        self.assertNotIn("0001-01-01", html)
        self.assertNotIn("9999-12-31", html)

    def test_public_risk_labels_use_standard_spelling(self) -> None:
        """Risk result labels use conventional punctuation and possessives."""
        labels = _risk_statistics().to_polars()["column"].to_list()

        self.assertIn("Monthly M-Squared", labels)
        self.assertIn("Monthly Jensen's Alpha", labels)
        self.assertIn("Annualized Jensen's Alpha", labels)

    def test_removed_conversion_methods_are_absent(self) -> None:
        """Risk output does not carry redundant conversion methods."""
        risk = _risk_statistics()
        for method in ("to_json", "to_pandas", "to_table", "to_xml"):
            self.assertFalse(hasattr(risk, method))

    def test_invalid_float_precision_is_rejected(self) -> None:
        """Risk serialization keeps its bounded precision invariant."""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PparError):
                _risk_statistics().write_csv(
                    Path(directory) / "risk.csv",
                    float_precision=16,
                )


if __name__ == "__main__":
    unittest.main()
