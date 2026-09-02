"""Tests for the informational optimization benchmark harness."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

import polars as pl

from scripts import benchmark_optimizations as benchmark


class TestBenchmarkOptimizations(unittest.TestCase):
    """Benchmark sampling and fixture helpers remain deterministic."""

    def test_arguments_default_to_all_scenarios_and_positive_samples(self) -> None:
        """The complete benchmark is the default and invalid counts fail."""
        args = benchmark._parse_args([])

        self.assertEqual(args.samples, 3)
        self.assertEqual(args.scenario, benchmark._SCENARIOS)
        with self.assertRaises(SystemExit):
            benchmark._parse_args(["--samples", "0"])

    def test_repeated_scenario_arguments_preserve_first_order(self) -> None:
        """Focused runs deduplicate scenarios without reordering them."""
        args = benchmark._parse_args(
            [
                "--scenario",
                "bulk",
                "--scenario",
                "generic",
                "--scenario",
                "bulk",
            ]
        )

        self.assertEqual(args.scenario, ("bulk", "generic"))

    def test_measured_values_retain_samples_and_verify_results(self) -> None:
        """Every timing observation and output-equivalence check is retained."""
        results = iter(("same", "same", "same"))
        with mock.patch.object(
            benchmark.time,
            "perf_counter",
            side_effect=(1.0, 1.2, 2.0, 2.3, 3.0, 3.4),
        ):
            samples, latest = benchmark._measured_values(
                lambda: next(results),
                3,
                lambda expected, actual: self.assertEqual(expected, actual),
            )

        for actual, expected in zip(samples, (0.2, 0.3, 0.4)):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(latest, "same")
        with self.assertRaisesRegex(ValueError, "positive"):
            benchmark._measured_values(lambda: "unused", 0, self.assertEqual)

    def test_artifact_snapshot_includes_only_files(self) -> None:
        """Report comparisons include complete bytes but ignore directories."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            (root / "b.html").write_bytes(b"second")
            (root / "a.png").write_bytes(b"first")

            snapshot = benchmark._artifact_snapshot(root)

        self.assertEqual(snapshot, {"a.png": b"first", "b.html": b"second"})

    def test_monthly_expansion_preserves_period_totals_and_unique_ids(self) -> None:
        """Scaling holdings changes lineage without changing total exposure."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "performance.csv"
            pl.DataFrame(
                {
                    "identifier": ["001", "A"],
                    "weight": [0.6, 0.4],
                    "return": [0.1, 0.2],
                }
            ).write_csv(path)

            expanded = benchmark._expanded_monthly_frame(path, 5)

        self.assertEqual(expanded.height, 10)
        self.assertEqual(expanded["identifier"].n_unique(), 10)
        self.assertAlmostEqual(expanded["weight"].sum(), 1.0)
        self.assertEqual(
            expanded.filter(pl.col("identifier").str.starts_with("001"))["return"]
            .unique()
            .to_list(),
            [0.1],
        )


if __name__ == "__main__":
    unittest.main()
