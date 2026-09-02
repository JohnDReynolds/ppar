"""End-to-end user journeys across documented and generated entry points."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import polars as pl

from ppar.cli.setup import setup
import ppar.schema as cols


_ROOT = Path(__file__).resolve().parents[1]
_STANDARD_REPORTS = {
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


def _python_example(path: Path, heading: str, next_heading: str | None = None) -> str:
    """Return the one fenced Python example beneath a Markdown heading.

    Args:
        path: Markdown document containing the example.
        heading: Heading that begins the relevant section.
        next_heading: Optional heading that ends the relevant section.

    Returns:
        Python source inside the section's one fenced block.
    """
    section = path.read_text(encoding="utf-8").split(f"{heading}\n", maxsplit=1)[1]
    if next_heading is not None:
        section = section.split(f"{next_heading}\n", maxsplit=1)[0]
    blocks = section.split("```python\n")[1:]
    if len(blocks) != 1:
        raise AssertionError(f"Expected one Python example beneath {heading!r}.")
    return blocks[0].split("```", maxsplit=1)[0]


def _write_own_generic_performance(directory: Path) -> None:
    """Replace both generic performance files with a small valid user history."""
    periods = (
        (dt.date(2021, 7, 1), dt.date(2021, 9, 30)),
        (dt.date(2021, 10, 1), dt.date(2021, 12, 31)),
        (dt.date(2022, 1, 1), dt.date(2022, 3, 31)),
        (dt.date(2022, 4, 1), dt.date(2022, 6, 30)),
    )
    sources = (
        (
            "Mega-Cap Alpha Portfolio.csv",
            (0.10, 0.05, 0.02, 0.04, -0.03, 0.01, 0.06, 0.02),
            (0.60, 0.40),
        ),
        (
            "Mega-Cap Benchmark.csv",
            (0.08, 0.04, 0.01, 0.03, -0.02, 0.00, 0.04, 0.01),
            (0.50, 0.50),
        ),
    )
    for file_name, returns, weights in sources:
        rows: list[dict[str, object]] = []
        for period_index, (from_date, thru_date) in enumerate(periods):
            for security_index, identifier in enumerate(("AAPL", "MSFT")):
                rows.append(
                    {
                        cols.FROM_DATE: from_date,
                        cols.THRU_DATE: thru_date,
                        cols.IDENTIFIER: identifier,
                        cols.WEIGHT: weights[security_index],
                        cols.RETURN: returns[(period_index * 2) + security_index],
                    }
                )
        pl.DataFrame(rows).write_csv(directory / "input" / "performance" / file_name)


def _replace_axys_portfolio_codes(directory: Path) -> None:
    """Customize Axys account codes and names as a user would in exported files."""
    code_mapping = {
        "MEGA_ALPHA": "CLIENT_PORT",
        "MEGA_BENCH": "CLIENT_BENCH",
    }
    for file_name in ("portperf.csv", "secperf.csv"):
        path = directory / "input" / file_name
        frame = pl.read_csv(path).with_columns(
            pl.col("Portfolio Code").replace(code_mapping)
        )
        if "Portfolio Name" in frame.columns:
            frame = frame.with_columns(
                pl.col("Portfolio Name").replace(
                    {
                        "Mega-Cap Alpha Portfolio": "Client Portfolio",
                        "Mega-Cap Benchmark": "Client Benchmark",
                    }
                )
            )
        frame.write_csv(path)

    script_path = directory / "ppar_demo.py"
    script = script_path.read_text(encoding="utf-8")
    script = script.replace(
        'PORTFOLIO = "MEGA_ALPHA"',
        'PORTFOLIO = "CLIENT_PORT"',
    ).replace(
        'BENCHMARK = "MEGA_BENCH"',
        'BENCHMARK = "CLIENT_BENCH"',
    )
    script_path.write_text(script, encoding="utf-8")


def _run_demo(directory: Path) -> subprocess.CompletedProcess[str]:
    """Run one generated demonstration and return its completed process."""
    return subprocess.run(
        [sys.executable, directory / "ppar_demo.py"],
        check=True,
        capture_output=True,
        text=True,
    )


def _report_names(directory: Path) -> set[str]:
    """Return file names written to a generated directory's output folder."""
    return {
        path.name
        for path in (directory / "output").iterdir()
        if path.is_file()
    }


class TestDocumentedUserJourneys(unittest.TestCase):
    """The concise documentation examples execute against supported public APIs."""

    def test_root_example_runs_after_replacing_generic_performance(self) -> None:
        """A user can substitute valid CSVs, run the example, and create all reports."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = setup(root / "my_ppar")
            _write_own_generic_performance(directory)
            example = _python_example(
                _ROOT / "README.md",
                "## Python",
                "## Documentation",
            )

            completed = subprocess.run(
                [sys.executable, "-c", example],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("shape: (1, 3)", completed.stdout)
            self.assertIn("Portfolio_Return", completed.stdout)
            self.assertIn("Benchmark_Return", completed.stdout)
            self.assertIn("Active_Return", completed.stdout)
            demo = _run_demo(directory)
            self.assertEqual(demo.stdout.splitlines()[0], "Output files:")
            self.assertEqual(_report_names(directory), _STANDARD_REPORTS)
            overall_html = (
                directory / "output" / "classification_overall_attribution.html"
            ).read_text(encoding="utf-8")
            self.assertIn("from 2021-07-01 to 2022-06-30", overall_html)

    def test_direct_risk_example_executes(self) -> None:
        """The distinct lower-level risk example remains executable as documented."""
        example = _python_example(
            _ROOT / "docs" / "python_api.md",
            "## Direct risk arrays",
            "## Axys/APX values",
        )

        completed = subprocess.run(
            [sys.executable, "-c", example],
            cwd=_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_axys_demo_runs_with_customized_account_codes(self) -> None:
        """An Axys user can select site account codes and retain the full bundle."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = setup(Path(temporary) / "my_ppar", axys_apx=True)
            _replace_axys_portfolio_codes(directory)

            completed = _run_demo(directory)

            self.assertEqual(completed.stdout.splitlines()[0], "Output files:")
            self.assertEqual(_report_names(directory), _STANDARD_REPORTS)
            overall_html = (
                directory / "output" / "classification_overall_attribution.html"
            ).read_text(encoding="utf-8")
            self.assertIn("CLIENT_PORT - Client Portfolio", overall_html)
            self.assertIn("CLIENT_BENCH - Client Benchmark", overall_html)


if __name__ == "__main__":
    unittest.main()
