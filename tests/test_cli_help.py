"""Tests for the public command-line help surface."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import unittest
from unittest import mock

from ppar.cli import main


class CliHelpTests(unittest.TestCase):
    """Ensure CLI help consistently describes the setup directory."""

    def test_top_level_help_describes_commands(self) -> None:
        """Top-level help explains the command surface."""
        output = StringIO()

        with redirect_stdout(output), self.assertRaisesRegex(SystemExit, "0"):
            main(["--help"])

        help_text = output.getvalue()
        normalized_help = " ".join(help_text.split())
        self.assertIn("Create a local directory for running portfolio analytics.", help_text)
        self.assertIn(
            "Create and populate a directory for running portfolio analytics.",
            normalized_help,
        )
        self.assertIn("ppar setup DIRECTORY", help_text)
        self.assertIn("DIRECTORY is the local directory that setup creates", help_text)
        self.assertIn("editable ppar_demo.py script", normalized_help)
        self.assertIn("ppar setup ./my_ppar", help_text)
        self.assertIn("ppar setup ./my_ppar_axys_apx --axys-apx", help_text)
        self.assertIn("Show this help message.", help_text)
        self.assertIn("Show the ppar version.", help_text)
        self.assertNotIn("and exit", help_text)

    def test_setup_help_defines_directory_argument(self) -> None:
        """Setup help makes the local-directory destination explicit."""
        output = StringIO()

        with redirect_stdout(output), self.assertRaisesRegex(SystemExit, "0"):
            main(["setup", "--help"])

        help_text = output.getvalue()
        self.assertIn("ppar setup [-h] [--axys-apx] DIRECTORY", help_text)
        self.assertIn("Local directory to create and populate", help_text)
        self.assertIn("ppar setup ./my_ppar", help_text)
        self.assertNotIn("workspace", help_text.lower())
        self.assertNotIn("PPAR", help_text)

    def test_setup_missing_directory_names_required_value(self) -> None:
        """A setup syntax error identifies the missing value as a directory."""
        output = StringIO()

        with redirect_stderr(output), self.assertRaisesRegex(SystemExit, "2"):
            main(["setup"])

        error_text = output.getvalue()
        self.assertIn("ppar setup [-h] [--axys-apx] DIRECTORY", error_text)
        self.assertIn("the following arguments are required: DIRECTORY", error_text)

    def test_setup_success_identifies_created_directory(self) -> None:
        """Setup output uses the same directory terminology as its help."""
        output = StringIO()
        directory = Path("/example/my_ppar")

        with (
            mock.patch("ppar.cli.main.setup", return_value=directory),
            redirect_stdout(output),
        ):
            self.assertEqual(main(["setup", str(directory)]), 0)

        self.assertEqual(
            output.getvalue().splitlines(),
            [
                f"Directory: {directory}",
                "",
                f"The next step is to read {directory / 'README.md'}.",
                (
                    "It contains instructions on how to run the demo and create "
                    "reports using your own data."
                ),
                "",
            ],
        )

    def test_axys_setup_success_identifies_data_source(self) -> None:
        """Axys/APX setup identifies its nondefault data source."""
        output = StringIO()
        directory = Path("/example/my_ppar_axys_apx")

        with (
            mock.patch("ppar.cli.main.setup", return_value=directory),
            redirect_stdout(output),
        ):
            self.assertEqual(main(["setup", str(directory), "--axys-apx"]), 0)

        self.assertEqual(
            output.getvalue().splitlines(),
            [
                f"Directory: {directory}",
                "Data source: axys_apx",
                "",
                f"The next step is to read {directory / 'README.md'}.",
                (
                    "It contains instructions on how to run the demo and create "
                    "reports using your own data."
                ),
                "",
            ],
        )


if __name__ == "__main__":
    unittest.main()
