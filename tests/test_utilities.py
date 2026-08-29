"""Provide reusable test-data paths and focused utility-function tests."""

# Python imports
from collections.abc import Mapping, Sequence
import datetime as dt
from pathlib import Path
import tempfile
from typing import Iterable
import unittest

# Third-party imports
import polars as pl

# Project imports
from ppar import Analytics
from ppar.attribution import Attribution
import ppar.schema as cols
from ppar.errors import PparError
import ppar.utilities as util

Period = tuple[dt.date, dt.date]
AssetValues = tuple[Sequence[float], Sequence[float]]

# Directories containing the test data.
_DATA_DIRECTORIES = (
    Path("tests/data"),
    Path("../tests/data"),
    Path("data"),
)
_AXYS_DIRECTORIES = [directory / "axys" for directory in _DATA_DIRECTORIES]
_DEFAULT_AXYS_SNAPSHOT_DIRECTORY = "snapshots/axys_a"
_CLASSIFICATION_DIRECTORIES = [directory / "classifications" for directory in _DATA_DIRECTORIES]
_MAPPING_DIRECTORIES = [directory / "mappings" for directory in _DATA_DIRECTORIES]
_PERFORMANCE_DIRECTORIES = [directory / "performance" for directory in _DATA_DIRECTORIES]

def make_performance_df(
    periods: Sequence[Period],
    assets: Mapping[str, AssetValues],
) -> pl.DataFrame:
    """Create narrow performance rows from aligned asset return and weight values.

    Args:
        periods: From and thru dates for each input period.
        assets: Asset identifiers mapped to return and weight sequences.

    Returns:
        Narrow-format Polars DataFrame accepted by ``Analytics`` and
        ``Performance``.
    """
    rows: list[dict[str, dt.date | str | float]] = []
    for period_index, (from_date, thru_date) in enumerate(periods):
        for identifier, (returns, weights) in assets.items():
            rows.append(
                {
                    cols.FROM_DATE: from_date,
                    cols.THRU_DATE: thru_date,
                    cols.IDENTIFIER: identifier,
                    cols.RETURN: returns[period_index],
                    cols.WEIGHT: weights[period_index],
                }
            )
    return pl.DataFrame(rows)


def axys_data_path(file_name: str, suffix: str = ".csv") -> Path:
    """Return a resolved path to an Axys fixture file.

    Args:
        file_name: Base name of the Axys fixture. Simple file names resolve
            from the Axys fixture root or the default ``snapshots/axys_a``
            snapshot.
        suffix: File suffix to append when not already present.

    Returns:
        Resolved path to the fixture file.

    Raises:
        PparError: If the named fixture is not found.
    """
    candidate_file_names = [file_name]
    if not Path(file_name).parent.parts:
        candidate_file_names.append(f"{_DEFAULT_AXYS_SNAPSHOT_DIRECTORY}/{file_name}")
    for candidate_file_name in candidate_file_names:
        try:
            return resolve_file_path(_AXYS_DIRECTORIES, candidate_file_name, suffix).resolve()
        except PparError:
            continue
    return resolve_file_path(_AXYS_DIRECTORIES, file_name, suffix).resolve()


def classification_data_path(classification_name: str | None) -> util.PathLike | None:
    """Return a classification fixture path or ``None``.

    Args:
        classification_name: Classification whose fixture is requested.

    Returns:
        Classification fixture path, or ``None`` when no classification was
        requested.

    Raises:
        PparError: If a requested fixture is not found.
    """
    if classification_name is None:
        return None
    return resolve_file_path(_CLASSIFICATION_DIRECTORIES, classification_name, ".csv")


def attribution(
    analytics: Analytics,
    classification_name: str | None = None,
    classification_data_source: util.ClassificationDataSource | None = None,
    mapping_data_source: util.MappingDataSource | None = None,
) -> Attribution:
    """Return attribution using inferred fixture sources where needed.

    Args:
        analytics: Analytics instance to query.
        classification_name: Classification name used when resolving a
            fixture source.
        classification_data_source: Optional classification source to use
            instead of resolving a fixture path.
        mapping_data_source: Optional mapping source to use for both portfolio
            and benchmark.

    Returns:
        Calculated attribution object.

    Raises:
        PparError: If a required fixture cannot be found or attribution
            construction fails.
    """
    classification_name = util.normalize_optional_string(classification_name)

    if classification_data_source is None or (
        isinstance(classification_data_source, str) and not classification_data_source.strip()
    ):
        classification_data_source = classification_data_path(classification_name)

    if mapping_data_source is None or (
        isinstance(mapping_data_source, str) and not mapping_data_source.strip()
    ):
        mapping_data_sources = mapping_data_paths(analytics, classification_name)
    else:
        mapping_data_sources = (mapping_data_source, mapping_data_source)

    return analytics.attribution(
        classification_name,
        classification_data_source,
        mapping_data_sources,
    )


def html_table_lines(html_string: str) -> list[str]:
    """Return table markup lines from an HTML string.

    Args:
        html_string: HTML string to scan for the first table.

    Returns:
        Lines from at the first HTML table found in the input.
    """
    # html_lines = html_string.split("\n")
    lines: list[str] = []
    on_table = False
    for line in html_string.split("\n"):
        if not on_table and line.startswith("<table "):
            on_table = True
        if on_table:
            lines.append(line)
    return lines


def mapping_data_paths(
    analytics: Analytics, to_classification_name: str | None
) -> tuple[util.MappingDataSource | None, util.MappingDataSource | None]:
    """Return fixture mapping sources for portfolio and benchmark.

    Args:
        analytics: Analytics instance whose classification names determine the
            source mappings.
        to_classification_name: Destination classification name.

    Returns:
        Two-item tuple of portfolio and benchmark mapping sources.

    Raises:
        PparError: If a required mapping fixture cannot be found.
    """
    if to_classification_name is None:
        return (None, None)

    # Build the tuple of mapping data sources containing the csv file paths.
    mapping_list: list[util.MappingDataSource | None] = [
        (
            None
            if from_classification_name == to_classification_name
            else resolve_file_path(
                _MAPPING_DIRECTORIES,
                f"{from_classification_name}--to--{to_classification_name}.csv",
            )
        )
        for from_classification_name in analytics.classification_names()
    ]

    return (mapping_list[0], mapping_list[1])


def performance_data_path(performance_name: str) -> Path:
    """Return a resolved path to a performance fixture file.

    Args:
        performance_name: Base name of the performance fixture.

    Returns:
        Resolved performance fixture path.

    Raises:
        PparError: If the fixture is not found.
    """
    return resolve_file_path(_PERFORMANCE_DIRECTORIES, performance_name, ".csv")


def resolve_file_path(
    directories: Iterable[util.PathLike], file_name: str, suffix: str | None = None
) -> Path:
    """Return the first existing fixture path matching a file name.

    Args:
        directories: Potential directories where file_name may be located.
        file_name: File name to find.
        suffix: Optional suffix appended when absent from ``file_name``.

    Returns:
        First matching file path.

    Raises:
        PparError: If the file does not exist in any candidate directory.
    """
    # Append ".csv".
    if suffix is not None and not file_name.endswith(suffix):
        file_name = f"{file_name}{suffix}"

    # Find the file_path.
    for directory in directories:
        file_path = Path(directory) / file_name
        if file_path.exists():
            return file_path

    # Throw exception if file_path was not found.
    raise PparError(util.file_path_error(file_name))


class TestUtilities(unittest.TestCase):
    """Verify utility calculations and file/data-source helpers."""

    def test_are_near(self) -> None:
        """Float nearness respects the selected tolerance."""
        self.assertTrue(util.are_near(1.0000000000001, 1.0, util.Tolerance.HIGH))
        self.assertFalse(util.are_near(1.0001, 1.0, util.Tolerance.LOW))

    def test_carino_linking_coefficient_rejects_undefined_returns(self) -> None:
        """Carino linking reports error 203 for returns at or below negative one."""
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
        self.assertEqual(util.file_path_error(""), "Missing data source.")

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
