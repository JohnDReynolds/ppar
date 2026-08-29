"""Tests that lock ppar's established scale-gate boundaries."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import polars as pl

from scripts import check_scale


class TestScaleCheck(unittest.TestCase):
    """Scale construction and thresholds remain unchanged."""

    def test_scale_choices_include_required_500x(self) -> None:
        """Routine levels and the release-candidate stress level remain available."""
        for scale in (*range(10, 101, 10), 500):
            self.assertEqual(check_scale._parse_args(["--scale", str(scale)]).scale, scale)
        for scale in (0, 1, 9, 11, 101, 499, 501, 1000):
            with self.subTest(scale=scale), self.assertRaises(SystemExit):
                check_scale._parse_args(["--scale", str(scale)])

    def test_large_site_caps_are_unchanged(self) -> None:
        """Large-site timing warns above 1.05x and fails above 1.10x."""
        self.assertEqual(check_scale._analytics_scaling_result(2.0, 2.10)[0], "PASS")
        self.assertEqual(check_scale._analytics_scaling_result(2.0, 2.16)[0], "WARN")
        with self.assertRaisesRegex(RuntimeError, "1.10x failure threshold"):
            check_scale._analytics_scaling_result(2.0, 2.21)

    def test_selected_and_history_caps_are_unchanged(self) -> None:
        """10x selected and 5x history thresholds retain their observed shape."""
        selected = check_scale._sublinear_scaling_result("selected", 10, 1.0, 1.0)
        history = check_scale._sublinear_scaling_result("history", 5, 1.0, 1.0)
        self.assertEqual(selected[2:], (2.10, 2.20))
        self.assertAlmostEqual(history[2], 1.575)
        self.assertAlmostEqual(history[3], 1.65)

    def test_large_site_expansion_preserves_values(self) -> None:
        """Synthetic copies change only portfolio identity."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            pl.DataFrame(
                {"Portfolio Code": ["P1"], "Value": [123.45]}
            ).write_csv(path)
            expanded = check_scale._expanded_frame(path, 3)
        self.assertEqual(expanded.get_column("Value").to_list(), [123.45] * 3)
        self.assertEqual(
            expanded.get_column("Portfolio Code").to_list(),
            ["P1", "P1_SCALE_001", "P1_SCALE_002"],
        )

    def test_selected_expansion_preserves_financial_totals(self) -> None:
        """Unique copied securities retain total weights and contributions."""
        performance = pl.DataFrame(
            {
                "Security Symbol": ["A", "B"],
                "Beginning Weight": [0.6, 0.4],
                "Contribution": [0.06, 0.02],
            }
        )
        reference = pl.DataFrame(
            {"Security Symbol": ["A", "B"], "Security Name": ["Alpha", "Beta"]}
        )
        expanded, references = check_scale._expanded_selected_frames(
            performance, reference, 10
        )
        self.assertEqual(expanded.height, 20)
        self.assertEqual(references.height, 20)
        self.assertAlmostEqual(expanded["Beginning Weight"].sum(), 1.0)
        self.assertAlmostEqual(expanded["Contribution"].sum(), 0.08)


if __name__ == "__main__":
    unittest.main()
