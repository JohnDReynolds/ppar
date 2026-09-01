"""Test focused utility functions."""

# Python imports
import datetime as dt
from pathlib import Path
import tempfile
import unittest

# Third-party imports
import polars as pl

# Project imports
from ppar.errors import PparError
import ppar.utilities as util


class TestUtilities(unittest.TestCase):
    """Verify internal numerical and path utility behavior."""

    def test_are_near(self) -> None:
        """Float nearness respects the selected tolerance."""
        self.assertTrue(util.are_near(1.0000000000001, 1.0, util.Tolerance.HIGH))
        self.assertFalse(util.are_near(1.0001, 1.0, util.Tolerance.LOW))

    def test_carino_linking_coefficient_rejects_undefined_returns(self) -> None:
        """Carino linking rejects returns at or below negative one."""
        with self.assertRaises(PparError):
            util.carino_linking_coefficient(-1.0, 0.03)

        with self.assertRaises(PparError):
            util.carino_linking_coefficient(0.05, -1.0)

    def test_carino_linking_coefficient_valid(self) -> None:
        """Valid Carino inputs return a floating-point coefficient."""
        self.assertIsInstance(util.carino_linking_coefficient(0.05, 0.03), float)

    def test_date_str(self) -> None:
        """Date formatting uses the package's ISO-style format."""
        self.assertEqual(util.date_str(dt.date(2023, 1, 5)), "2023-01-05")

    def test_file_basename_without_extension(self) -> None:
        """File basenames are extracted from strings and Path instances."""
        path = "/some/path/to/myfile.csv"
        self.assertEqual(util.file_basename_without_extension(path), "myfile")
        self.assertEqual(util.file_basename_without_extension(Path(path)), "myfile")
        self.assertEqual(
            util.file_basename_without_extension("/some/path/portfolio.v2.csv"),
            "portfolio.v2",
        )

    def test_file_path_exists(self) -> None:
        """File-existence detection handles existing and missing paths."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_name = temp_file.name
        try:
            self.assertTrue(util.file_path_exists(temp_name))
            self.assertTrue(util.file_path_exists(Path(temp_name)))
        finally:
            Path(temp_name).unlink()

        self.assertFalse(util.file_path_exists("not_a_real_file.xyz"))
        self.assertFalse(util.file_path_exists(Path("not_a_real_file.xyz")))

    def test_empty_file_path_error_is_actionable(self) -> None:
        """An empty requested file path explains the missing input."""
        self.assertEqual(
            util.file_path_error(""),
            "Data source path must not be blank.",
        )

    def test_demo_data_sources_return_paths(self) -> None:
        """Packaged demo data helpers resolve existing Path instances."""
        performance_path = (
            Path("src/ppar/templates/generic/input/performance")
            / "Mega-Cap Benchmark.csv"
        )
        classification_path = (
            Path("src/ppar/templates/generic/input/classifications")
            / "Security.csv"
        )

        self.assertIsInstance(performance_path, Path)
        self.assertIsInstance(classification_path, Path)
        self.assertTrue(util.file_path_exists(performance_path))
        self.assertTrue(util.file_path_exists(classification_path))

    def test_logarithmic_linking_coefficient_series(self) -> None:
        """Paired Polars Series produce a result for each observation."""
        result = util.logarithmic_linking_coefficient_series(
            pl.Series([0.02, 0.03, 0.05]),
            pl.Series([0.01, 0.02, 0.025]),
        )

        self.assertIsInstance(result, pl.Series)
        self.assertEqual(result.len(), 3)

    def test_logarithmic_linking_coefficients(self) -> None:
        """One total return produces one coefficient per period return."""
        result = util.logarithmic_linking_coefficients(
            0.08,
            pl.Series([0.01, 0.02, 0.03]),
        )

        self.assertIsInstance(result, pl.Series)
        self.assertEqual(result.len(), 3)

    def test_near_zero(self) -> None:
        """Near-zero detection respects the selected tolerance."""
        self.assertTrue(util.near_zero(0.0000000000001, util.Tolerance.HIGH))
        self.assertFalse(util.near_zero(0.001, util.Tolerance.LOW))


if __name__ == "__main__":
    unittest.main()
