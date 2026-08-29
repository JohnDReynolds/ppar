"""Integration tests for the two supported public table representations."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import tempfile
import unittest

import polars as pl

from ppar import Analytics
from ppar.attribution import View
from ppar.errors import PparError
import ppar.schema as cols


def _performance() -> pl.DataFrame:
    """Return a two-period narrow performance table."""
    return pl.DataFrame(
        {
            cols.FROM_DATE: [dt.date(2024, 1, 1)] * 2 + [dt.date(2024, 2, 1)] * 2,
            cols.THRU_DATE: [dt.date(2024, 1, 31)] * 2 + [dt.date(2024, 2, 29)] * 2,
            cols.IDENTIFIER: ["A", "B", "A", "B"],
            cols.WEIGHT: [0.6, 0.4, 0.5, 0.5],
            cols.RETURN: [0.02, 0.01, -0.01, 0.03],
        }
    )


class TestDataSourceFormats(unittest.TestCase):
    """Equivalent CSV-path and Polars sources produce equivalent output."""

    def test_performance_accepts_path_and_polars(self) -> None:
        """The focused performance boundary has exactly two representations."""
        frame = _performance()
        polars_result = Analytics(frame, frame).attribution().to_polars(
            View.OVERALL_ATTRIBUTION
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "performance.csv"
            frame.write_csv(path)
            path_result = Analytics(path, path).attribution().to_polars(
                View.OVERALL_ATTRIBUTION
            )
        self.assertTrue(polars_result.equals(path_result))

    def test_classification_and_mapping_accept_path_and_polars(self) -> None:
        """Classification and mapping boundaries share the same two forms."""
        analytics = Analytics(
            _performance(),
            _performance(),
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )
        classifications = pl.DataFrame({"id": ["X"], "name": ["Group"]})
        mappings = pl.DataFrame({"id": ["A", "B"], "group": ["X", "X"]})
        expected = analytics.attribution(
            "Group", classifications, (mappings, mappings)
        ).to_polars(View.OVERALL_ATTRIBUTION)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            classification_path = root / "classification.csv"
            mapping_path = root / "mapping.csv"
            classifications.write_csv(classification_path, include_header=False)
            mappings.write_csv(mapping_path, include_header=False)
            actual = analytics.attribution(
                "Group", classification_path, (mapping_path, mapping_path)
            ).to_polars(View.OVERALL_ATTRIBUTION)
        self.assertTrue(expected.equals(actual))

    def test_dictionary_sources_are_rejected(self) -> None:
        """Compatibility dictionaries are outside the focused public contract."""
        with self.assertRaises((AttributeError, PparError, TypeError)):
            Analytics({"from_date": []})  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
