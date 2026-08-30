"""Tests for atomic report-directory publication."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from ppar.attribution import Chart, View
from ppar.errors import PparError
from ppar.publication import atomic_output_directory, write_report_bundle


class AtomicOutputDirectoryTests(unittest.TestCase):
    """The prior report bundle survives failures and is replaced on success."""

    def test_success_replaces_complete_output(self) -> None:
        """A successful context publishes only the new files."""
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            output.mkdir()
            (output / "old.txt").write_text("old", encoding="utf-8")

            with atomic_output_directory(output) as staging:
                (staging / "new.txt").write_text("new", encoding="utf-8")

            self.assertEqual([path.name for path in output.iterdir()], ["new.txt"])

    def test_failure_preserves_prior_output(self) -> None:
        """An exception discards staging and leaves the prior bundle untouched."""
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            output.mkdir()
            (output / "old.txt").write_text("old", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "stop"):
                with atomic_output_directory(output) as staging:
                    (staging / "partial.txt").write_text("partial", encoding="utf-8")
                    raise RuntimeError("stop")

            self.assertEqual((output / "old.txt").read_text(encoding="utf-8"), "old")
            self.assertFalse((output / "partial.txt").exists())


class WriteReportBundleTests(unittest.TestCase):
    """The shared writer renders selected reports in deterministic order."""

    def test_writes_selected_reports_and_returns_names(self) -> None:
        """Selected tables, charts, and risk statistics use predictable names."""
        security_attribution = MagicMock()
        security_attribution.to_html.return_value = "<security>"
        classification_attribution = MagicMock()
        classification_attribution.to_html.return_value = "<classification>"
        classification_attribution.to_chart.return_value = b"chart"
        risk_statistics = MagicMock()
        risk_statistics.to_html.return_value = "<risk>"

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "reports"
            names = write_report_bundle(
                output_directory=output,
                security_attribution=security_attribution,
                security_views=(View.OVERALL_ATTRIBUTION,),
                classification_attribution=classification_attribution,
                classification_views=(View.CUMULATIVE_ATTRIBUTION,),
                classification_charts=(Chart.CUMULATIVE_RETURN,),
                risk_statistics=risk_statistics,
            )

            self.assertEqual(
                names,
                (
                    "security_overall_attribution.html",
                    "classification_cumulative_attribution.html",
                    "classification_cumulative_return.png",
                    "risk_statistics.html",
                ),
            )
            self.assertEqual(
                (output / "security_overall_attribution.html").read_text(
                    encoding="utf-8"
                ),
                "<security>",
            )
            self.assertEqual(
                (output / "classification_cumulative_attribution.html").read_text(
                    encoding="utf-8"
                ),
                "<classification>",
            )
            self.assertEqual(
                (output / "classification_cumulative_return.png").read_bytes(),
                b"chart",
            )
            self.assertEqual(
                (output / "risk_statistics.html").read_text(encoding="utf-8"),
                "<risk>",
            )

    def test_writes_one_report_without_unrelated_calculations(self) -> None:
        """A caller can select one report and omit every unrelated input."""
        security_attribution = MagicMock()
        security_attribution.to_html.return_value = "<security>"

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "reports"
            names = write_report_bundle(
                output_directory=output,
                security_attribution=security_attribution,
                security_views=(View.OVERALL_ATTRIBUTION,),
            )

            self.assertEqual(names, ("security_overall_attribution.html",))
            self.assertEqual(
                (output / names[0]).read_text(encoding="utf-8"),
                "<security>",
            )

    def test_rejects_selected_category_without_its_calculation(self) -> None:
        """A selected report category must have its corresponding calculation."""
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "reports"
            with self.assertRaisesRegex(PparError, "security_attribution is required"):
                write_report_bundle(
                    output_directory=output,
                    security_views=(View.OVERALL_ATTRIBUTION,),
                )

            self.assertFalse(output.exists())

    def test_rejects_empty_report_selection(self) -> None:
        """An empty call raises an actionable error without creating output."""
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "reports"
            with self.assertRaisesRegex(PparError, "At least one report"):
                write_report_bundle(output_directory=output)

            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
