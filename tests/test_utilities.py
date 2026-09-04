"""Test focused utility functions."""

# Python imports
from pathlib import Path
import tempfile
import unittest

# Project imports
import ppar.utilities as util


class TestUtilities(unittest.TestCase):
    """Verify internal numerical and path utility behavior."""

    def test_are_near(self) -> None:
        """Float nearness respects the selected tolerance."""
        self.assertTrue(util.are_near(1.0000000000001, 1.0, util.Tolerance.HIGH))
        self.assertFalse(util.are_near(1.0001, 1.0, util.Tolerance.LOW))

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



if __name__ == "__main__":
    unittest.main()
