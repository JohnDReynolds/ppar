"""Contract tests for both packaged ppar demonstration workspaces."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import shlex
import tempfile
import subprocess
import sys
import unittest

import polars as pl

from ppar import Analytics
from ppar.attribution import View
from ppar.cli.setup import setup
from ppar.frequency import Frequency
import ppar.schema as cols


_EXPECTED_ARTIFACTS = {
    "classification_cumulative_attribution.html",
    "classification_cumulative_attribution.png",
    "classification_cumulative_return.png",
    "classification_heatmap_active_contribution.png",
    "classification_heatmap_attribution.png",
    "classification_overall_attribution.html",
    "classification_overall_attribution.png",
    "classification_overall_contribution.png",
    "classification_subperiod_attribution.png",
    "risk_statistics.html",
    "security_overall_attribution.html",
}
_INPUT = Path("src/ppar/templates/generic/input")


class TestMegaCapDemoDataContract(unittest.TestCase):
    """The packaged inputs remain complete, coherent, and immediately runnable."""

    def test_generic_performance_has_sixty_consecutive_months(self) -> None:
        """Portfolio and benchmark contain the same complete 60-month history."""
        portfolio = pl.read_csv(
            _INPUT / "performance" / "Mega-Cap Alpha Portfolio.csv",
            try_parse_dates=True,
        )
        benchmark = pl.read_csv(
            _INPUT / "performance" / "Mega-Cap Benchmark.csv",
            try_parse_dates=True,
        )
        portfolio_periods = portfolio.select(cols.FROM_DATE, cols.THRU_DATE).unique().sort(
            cols.FROM_DATE
        )
        benchmark_periods = benchmark.select(cols.FROM_DATE, cols.THRU_DATE).unique().sort(
            cols.FROM_DATE
        )
        self.assertEqual(portfolio_periods.height, 60)
        self.assertTrue(portfolio_periods.equals(benchmark_periods))
        self.assertEqual(portfolio_periods[cols.THRU_DATE].item(33), dt.date(2024, 3, 28))

    def test_generic_financial_story_and_period_coverage(self) -> None:
        """The demo retains its attribution rows and completed quarterly buckets."""
        analytics = Analytics(
            _INPUT / "performance" / "Mega-Cap Alpha Portfolio.csv",
            _INPUT / "performance" / "Mega-Cap Benchmark.csv",
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
            frequency=Frequency.QUARTERLY,
            holidays=_INPUT / "holidays.csv",
        )
        security = analytics.attribution(
            "Security", _INPUT / "classifications" / "Security.csv"
        ).to_polars(View.OVERALL_ATTRIBUTION)
        summary = analytics.attribution().to_polars(View.SUBPERIOD_SUMMARY)
        self.assertGreater(security.height, 1)
        self.assertIn("Intel Corporation", security[cols.CLASSIFICATION_NAME].to_list())
        self.assertEqual(summary.height, 20)
        self.assertEqual(summary[cols.THRU_DATE].item(-1), dt.date(2026, 3, 31))

    def test_setup_variants_are_valid_and_run_complete_workflows(self) -> None:
        """Both generated tutorial scripts run complete workflows without YAML."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source, axys_apx in (("generic", False), ("axys_apx", True)):
                directory = setup(root / source, axys_apx=axys_apx)
                readme = (directory / "README.md").read_text(encoding="utf-8")
                self.assertIn(
                    f"python {shlex.quote(str(directory / 'ppar_demo.py'))}",
                    readme,
                )
                self.assertNotIn("__PPAR_DEMO_PATH__", readme)
                completed = subprocess.run(
                    [sys.executable, directory / "ppar_demo.py"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                output_lines = completed.stdout.splitlines()
                self.assertEqual(output_lines[0], "Output files:")
                self.assertNotIn("Output directory:", completed.stdout)
                artifacts = {
                    path.name for path in (directory / "output").iterdir() if path.is_file()
                }
                self.assertEqual(artifacts, _EXPECTED_ARTIFACTS)
                self.assertFalse((directory / "ppar.yaml").exists())
                self.assertEqual(
                    [path.name for path in directory.rglob("*.py")],
                    ["ppar_demo.py"],
                )


if __name__ == "__main__":
    unittest.main()
