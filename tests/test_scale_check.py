"""Tests that lock ppar's established scale-gate boundaries."""

from __future__ import annotations

from contextlib import redirect_stdout
import datetime as dt
import io
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock

import polars as pl

import ppar.core as core_module
from scripts import check_scale


class TestScaleCheck(unittest.TestCase):
    """Scale construction, equivalence, and retained thresholds remain stable."""

    def test_scale_choices_include_required_500x(self) -> None:
        """Routine levels and the release-candidate stress level remain available."""
        for scale in (*range(10, 101, 10), 500):
            self.assertEqual(check_scale._parse_args(["--scale", str(scale)]).scale, scale)
        for scale in (0, 1, 9, 11, 101, 499, 501, 1000):
            with self.subTest(scale=scale), self.assertRaises(SystemExit):
                check_scale._parse_args(["--scale", str(scale)])
        self.assertFalse(check_scale._parse_args(["--scale", "500"]).diagnostics)
        self.assertTrue(
            check_scale._parse_args(["--scale", "500", "--diagnostics"]).diagnostics
        )

    def test_timing_samples_retain_each_observation(self) -> None:
        """The scale report retains raw samples instead of only their median."""
        with mock.patch.object(
            check_scale,
            "_run",
            side_effect=(1.2, 1.0, 1.1),
        ):
            samples = check_scale._run_elapsed_samples(("python", "demo.py"))

        self.assertEqual(samples, (1.2, 1.0, 1.1))

    def test_large_site_timing_is_observational_after_one_complete_pair(self) -> None:
        """A slow but equivalent 500x bundle reports timing without failing."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            scaled = root / "scaled"
            for site in (baseline, scaled):
                output = site / "output"
                output.mkdir(parents=True)
                (output / "table.html").write_bytes(b"same table")
                (output / "chart.png").write_bytes(b"same chart")
            stream = io.StringIO()
            with (
                mock.patch.object(
                    check_scale,
                    "_prepare_large_site",
                    side_effect=((baseline, 100), (scaled, 50_000)),
                ),
                mock.patch.object(
                    check_scale,
                    "_run",
                    side_effect=(1.0, 9.0),
                ) as run,
                redirect_stdout(stream),
            ):
                check_scale._check_large_site(root, 500)

        self.assertEqual(run.call_count, 2)
        self.assertIn("PASS Analytics large-site equivalence 500x", stream.getvalue())
        self.assertIn("observation only", stream.getvalue())
        self.assertIn("9.000x", stream.getvalue())

    def test_large_site_compares_every_report_artifact(self) -> None:
        """A non-HTML report difference fails the 500x equivalence check."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            scaled = root / "scaled"
            for site, chart in ((baseline, b"baseline"), (scaled, b"changed")):
                output = site / "output"
                output.mkdir(parents=True)
                (output / "table.html").write_bytes(b"same table")
                (output / "chart.png").write_bytes(chart)
            with (
                mock.patch.object(
                    check_scale,
                    "_prepare_large_site",
                    side_effect=((baseline, 100), (scaled, 50_000)),
                ),
                mock.patch.object(check_scale, "_run", side_effect=(1.0, 1.1)),
                self.assertRaisesRegex(RuntimeError, "report bundle differs"),
            ):
                check_scale._check_large_site(root, 500)

    def test_history_caps_are_unchanged(self) -> None:
        """The fivefold long-history thresholds retain their observed shape."""
        history = check_scale._sublinear_scaling_result("history", 5, 1.0, 1.0)
        self.assertAlmostEqual(history[2], 1.575)
        self.assertAlmostEqual(history[3], 1.65)

    def test_slow_equivalent_selected_workload_is_observational(self) -> None:
        """Machine-dependent selected timing cannot reject equivalent results."""
        baseline_security = pl.DataFrame(
            {"Classification_Identifier": ["A", None]}
        )
        scaled_security = pl.DataFrame(
            {
                "Classification_Identifier": [
                    *[f"A{index}" for index in range(10)],
                    None,
                ]
            }
        )
        sector = pl.DataFrame({"Effect": [0.25]})
        risk = pl.DataFrame(
            {"Portfolio": [0.5], "Benchmark": [0.25], "Difference": [0.25]}
        )
        stream = io.StringIO()
        with (
            mock.patch.object(
                check_scale,
                "_prepare_large_site",
                return_value=(Path("baseline"), 100),
            ),
            mock.patch.object(
                check_scale,
                "_prepare_selected",
                return_value=(Path("scaled"), 1_000),
            ),
            mock.patch.object(
                check_scale,
                "_selected_tables",
                side_effect=(
                    (baseline_security, sector, risk),
                    (scaled_security, sector, risk),
                ),
            ),
            mock.patch.object(
                check_scale.time,
                "perf_counter",
                side_effect=(0.0, 1.0, 2.0, 12.0),
            ),
            redirect_stdout(stream),
        ):
            check_scale._check_selected(Path("unused"))

        output = stream.getvalue()
        self.assertIn("PASS Analytics selected-workload 10x", output)
        self.assertIn("10.000x", output)
        self.assertIn("no performance threshold", output)

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

    def test_demo_thru_date_update_is_checked_and_executable(self) -> None:
        """Updating the history bound must change exactly one executable assignment."""
        with tempfile.TemporaryDirectory() as directory:
            demo_path = Path(directory) / "ppar_demo.py"
            demo_path.write_text(
                "import datetime as dt\nTHRU_DATE = dt.date(2026, 5, 29)\n",
                encoding="utf-8",
            )
            expected = dt.date(2046, 5, 31)

            check_scale._set_demo_thru_date(demo_path, expected)

            self.assertEqual(runpy.run_path(str(demo_path))["THRU_DATE"], expected)
            demo_path.write_text("import datetime as dt\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "exactly one THRU_DATE"):
                check_scale._set_demo_thru_date(demo_path, expected)

    def test_history_periods_cover_leap_weekend_and_holiday_endpoints(self) -> None:
        """Synthetic months are gapless and use the configured business endpoints."""
        periods = check_scale._monthly_history_periods(
            dt.date(2024, 1, 1),
            7,
            frozenset({dt.date(2024, 3, 29)}),
        )

        self.assertEqual(
            [thru_date for _, thru_date in periods],
            [
                dt.date(2024, 1, 31),
                dt.date(2024, 2, 29),
                dt.date(2024, 3, 28),
                dt.date(2024, 4, 30),
                dt.date(2024, 5, 31),
                dt.date(2024, 6, 28),
                dt.date(2024, 7, 31),
            ],
        )
        for (_, prior_thru_date), (from_date, _) in zip(periods, periods[1:]):
            self.assertEqual(from_date, prior_thru_date + dt.timedelta(days=1))

    def test_prepared_history_has_300_gapless_matching_periods(self) -> None:
        """Both Axys/APX files and the demo bound cover the complete 25 years."""
        with tempfile.TemporaryDirectory() as directory:
            site, _, period_count = check_scale._prepare_history(Path(directory) / "site")
            portfolio = pl.read_csv(
                site / "input" / "portperf.csv", try_parse_dates=True
            )
            security = pl.read_csv(
                site / "input" / "secperf.csv", try_parse_dates=True
            )
            portfolio_periods = (
                portfolio.filter(pl.col("Portfolio Code") == "MEGA_ALPHA")
                .select("From Date", "Thru Date")
                .unique()
                .sort("Thru Date")
            )
            security_periods = (
                security.filter(pl.col("Portfolio Code") == "MEGA_ALPHA")
                .select("From Date", "Thru Date")
                .unique()
                .sort("Thru Date")
            )

            self.assertEqual(period_count, 300)
            self.assertTrue(portfolio_periods.equals(security_periods))
            self.assertEqual(
                runpy.run_path(str(site / "ppar_demo.py"))["THRU_DATE"],
                dt.date(2046, 5, 31),
            )
            periods = list(portfolio_periods.iter_rows())
            for (_, prior_thru_date), (from_date, _) in zip(periods, periods[1:]):
                self.assertEqual(from_date, prior_thru_date + dt.timedelta(days=1))

    def test_prepared_history_reaches_the_calculated_reporting_horizon(self) -> None:
        """The fivefold source history produces all 99 complete quarterly periods."""
        with tempfile.TemporaryDirectory() as directory:
            site, _, _ = check_scale._prepare_history(Path(directory) / "site")

            periods = check_scale._history_reporting_periods(site)

        self.assertEqual(periods.height, 99)
        self.assertEqual(periods["from_date"].item(0), dt.date(2021, 7, 1))
        self.assertEqual(periods["thru_date"].item(-1), dt.date(2046, 3, 30))

    def test_reporting_workflow_uses_portable_pair_boundaries(self) -> None:
        """Long-history alignment and later mapping each delegate once."""
        with tempfile.TemporaryDirectory() as directory:
            site, _, _ = check_scale._prepare_history(Path(directory) / "site")
            with mock.patch.object(
                core_module,
                "prepare_performance_sources",
                wraps=core_module.prepare_performance_sources,
            ) as prepare_sources, mock.patch.object(
                core_module,
                "prepare_performances",
                wraps=core_module.prepare_performances,
            ) as prepare_performances:
                check_scale._history_reporting_periods(site)

        self.assertEqual(prepare_sources.call_count, 1)
        self.assertEqual(prepare_performances.call_count, 1)


if __name__ == "__main__":
    unittest.main()
