"""Focused tests for Polars, CSV, HTML, and chart outputs."""

from __future__ import annotations

import datetime as dt
import html as html_lib
from pathlib import Path
import tempfile
import unittest

import numpy as np
import polars as pl
from polars.testing import assert_frame_equal

from ppar import Analytics
from ppar.attribution import Chart, View
from ppar.errors import PparError
from ppar.frequency import Frequency
from ppar.risk import RiskStatistics
import ppar.schema as cols
import ppar.tables as html_table


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


def _risk_statistics(
    *,
    annual_minimum_acceptable_return: float = 0.0,
    annual_risk_free_rate: float = 0.03,
    confidence_level: float = 0.95,
) -> RiskStatistics:
    """Return monthly statistics with stable values and configurable assumptions.

    Args:
        annual_minimum_acceptable_return: Annual downside-risk hurdle.
        annual_risk_free_rate: Annual cash rate for risk-adjusted metrics.
        confidence_level: Confidence level for value at risk.

    Returns:
        Calculated monthly risk statistics.
    """
    portfolio = np.array([0.01, -0.02, 0.03, 0.01, -0.01, 0.02] * 2)
    benchmark = np.array([0.005, -0.01, 0.02, 0.015, -0.005, 0.01] * 2)
    return RiskStatistics(
        (portfolio, benchmark),
        Frequency.MONTHLY,
        annual_minimum_acceptable_return=annual_minimum_acceptable_return,
        annual_risk_free_rate=annual_risk_free_rate,
        confidence_level=confidence_level,
        portfolio_value=(250_000.0, "$"),
    )


def _html_row(html: str, label: str) -> str:
    """Return the rendered table-row fragment containing one row label."""
    row_start = html.index(f">{html_lib.escape(label, quote=True)}</th>")
    return html[row_start : html.index("</tr>", row_start)]


class TestAttributionOutputs(unittest.TestCase):
    """Attribution exposes one machine-readable table API plus presentation APIs."""

    def test_polars_contains_the_total_row(self) -> None:
        """The focused table API retains the calculated view contract."""
        frame = _attribution().to_polars(View.OVERALL_ATTRIBUTION)
        self.assertIsInstance(frame, pl.DataFrame)
        self.assertEqual(frame[cols.CLASSIFICATION_NAME].item(-1), "Total")

    def test_csv_preserves_polars_columns_and_precision(self) -> None:
        """CSV output preserves decimals rather than presentation percentages."""
        attribution = _attribution()
        expected = attribution.to_polars(View.OVERALL_ATTRIBUTION)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attribution.csv"
            attribution.write_csv(View.OVERALL_ATTRIBUTION, path, float_precision=6)
            actual = pl.read_csv(path)
            csv_text = path.read_text(encoding="utf-8")
        self.assertEqual(actual.columns, expected.columns)
        self.assertEqual(actual.height, expected.height)
        self.assertNotIn("%", csv_text)
        self.assertAlmostEqual(
            actual[cols.PORTFOLIO_WEIGHT].item(0),
            expected[cols.PORTFOLIO_WEIGHT].item(0),
            places=6,
        )

    def test_html_uses_percentages_without_mutating_polars_values(self) -> None:
        """Attribution HTML presents percentages while Polars retains decimals."""
        attribution = _attribution()
        expected = attribution.to_polars(View.OVERALL_ATTRIBUTION)

        html = attribution.to_html(View.OVERALL_ATTRIBUTION)

        self.assertIn("50.33%", html)
        self.assertIn("100.00%", html)
        assert_frame_equal(attribution.to_polars(View.OVERALL_ATTRIBUTION), expected)

    def test_html_and_png_chart_render(self) -> None:
        """Both retained presentation boundaries produce complete artifacts."""
        attribution = _attribution()
        html = attribution.to_html(View.OVERALL_ATTRIBUTION)
        png = attribution.to_chart(Chart.OVERALL_ATTRIBUTION)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_html_document_exposes_accessible_structure(self) -> None:
        """Reports provide browser metadata and semantic table navigation cues."""
        attribution_html = _attribution().to_html(View.OVERALL_ATTRIBUTION)
        risk_html = _risk_statistics().to_html()

        self.assertIn(
            '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
            attribution_html,
        )
        self.assertIn(
            "<title>Portfolio vs Benchmark — Overall Attribution", attribution_html
        )
        self.assertIn(
            'aria-label="Portfolio vs Benchmark — Overall Attribution',
            attribution_html,
        )
        self.assertIn('scope="colgroup"', attribution_html)
        self.assertIn("position: sticky;", attribution_html)
        self.assertIn('scope="rowgroup"', risk_html)

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
            self.assertNotIn("%", path.read_text(encoding="utf-8"))

    def test_html_formats_risk_statistics_according_to_their_units(self) -> None:
        """Risk presentation distinguishes percentages, ratios, and currency."""
        html = _risk_statistics().to_html()
        percentage_statistics = (
            "Monthly Return Range",
            "Monthly Mean Return",
            "Annualized Mean Return",
            "Monthly Standard Deviation",
            "Annualized Standard Deviation",
            "Monthly Downside Probability",
            "Monthly Expected Downside Value",
            "Monthly Downside Deviation",
            "Annualized Downside Deviation",
            "Monthly Tracking Error",
            "Annualized Tracking Error",
            "Monthly M-Squared",
            "Monthly Treynor Ratio",
            "Monthly Alpha",
            "Annualized Alpha",
            "Monthly Jensen's Alpha",
            "Annualized Jensen's Alpha",
        )
        unitless_statistics = (
            "Monthly Correlation",
            "Monthly R-Squared",
            "Monthly Sharpe Ratio",
            "Annualized Sharpe Ratio",
            "Monthly Sortino Ratio",
            "Annualized Sortino Ratio",
            "Monthly Information Ratio",
            "Monthly Beta",
        )

        for statistic in percentage_statistics:
            with self.subTest(statistic=statistic):
                self.assertIn("%", _html_row(html, statistic))
        for statistic in unitless_statistics:
            with self.subTest(statistic=statistic):
                self.assertNotIn("%", _html_row(html, statistic))
        self.assertIn("$5,323", _html_row(html, "Monthly Value At Risk for $250,000"))

    def test_html_does_not_mutate_risk_polars_values(self) -> None:
        """Risk HTML formatting leaves the machine-readable frame unchanged."""
        risk = _risk_statistics()
        expected = risk.to_polars()

        risk.to_html()

        assert_frame_equal(risk.to_polars(), expected)

    def test_html_places_configured_assumptions_below_the_subtitle(self) -> None:
        """Risk HTML identifies its three configured rate assumptions up front."""
        html = _risk_statistics(
            annual_minimum_acceptable_return=-0.0123,
            annual_risk_free_rate=0.0456,
            confidence_level=0.9876,
        ).to_html()
        assumptions = (
            "Assumptions: Annual risk-free rate: 4.56% · "
            "Annual minimum acceptable return: -1.23% · "
            "VaR confidence level: 98.76%"
        )

        self.assertIn(assumptions, html)
        self.assertLess(html.index("Ex-Post Risk Statistics"), html.index(assumptions))
        self.assertLess(html.index(assumptions), html.index(">Portfolio</th>"))
        self.assertEqual(html.count("$250,000"), 1)

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


class TestPresentationFormatting(unittest.TestCase):
    """Presentation-only formatting does not expose rounded negative zero."""

    def test_html_normalizes_negative_zero_for_percentages_and_numbers(self) -> None:
        """Values that round to zero display without a misleading minus sign."""
        table = html_table.HtmlTable(
            df=pl.DataFrame({"percentage": [-0.000001], "number": [-0.00001]}),
            columns=(
                html_table.ColumnSpec("percentage", format="percentage"),
                html_table.ColumnSpec("number", format="number"),
            ),
        )

        html = table.as_raw_html()

        self.assertIn(">0.00%</td>", html)
        self.assertIn(">0.0000</td>", html)
        self.assertNotIn("&minus;0.00", html)


if __name__ == "__main__":
    unittest.main()
