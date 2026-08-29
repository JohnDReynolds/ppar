"""Contracts for optional values normalized to ``None``."""

# Python Imports
import datetime as dt
import unittest

# Third-Party Imports
import polars as pl

# Project Imports
from ppar import Analytics
from ppar.attribution import View
import ppar.schema as cols
from ppar.performance import Performance
import ppar.utilities as util


def _performance_rows() -> pl.DataFrame:
    """Return minimal narrow performance rows for sentinel compatibility tests."""
    return pl.DataFrame(
        {
            cols.FROM_DATE: [dt.date(2024, 1, 1)] * 2,
            cols.THRU_DATE: [dt.date(2024, 2, 1)] * 2,
            cols.IDENTIFIER: ["A", "B"],
            cols.RETURN: [0.10, -0.05],
            cols.WEIGHT: [0.60, 0.40],
        }
    )


class TestOptionalValueContracts(unittest.TestCase):
    """Verify optional values use ``None`` while blank input remains accepted."""

    def test_optional_strings_normalize_to_none(self) -> None:
        """Omitted and blank optional strings normalize to ``None``."""
        for value in (None, "", "   "):
            with self.subTest(value=value):
                self.assertIsNone(util.normalize_optional_string(value))

        self.assertEqual(util.normalize_optional_string("Security"), "Security")
        self.assertEqual(util.normalize_optional_string("_empty_"), "_empty_")

    def test_omitted_performance_metadata_uses_none(self) -> None:
        """Absent public performance metadata is stored as ``None``."""
        performance = Performance(_performance_rows())

        self.assertIsNone(performance.name)
        self.assertIsNone(performance.classification_name)

    def test_blank_attribution_arguments_match_omitted_arguments(self) -> None:
        """Blank string arguments select the same output as omissions."""
        implicit = Analytics(_performance_rows()).attribution()
        explicit = Analytics(_performance_rows()).attribution(
            classification_name="",
            classification_data_source="",
            mapping_data_sources=("", ""),
            classification_label="",
        )

        for view in View:
            with self.subTest(view=view):
                self.assertTrue(implicit.to_polars(view).equals(explicit.to_polars(view)))

        implicit_html = implicit.to_table(View.OVERALL_ATTRIBUTION).as_raw_html(make_page=False)
        explicit_html = explicit.to_table(View.OVERALL_ATTRIBUTION).as_raw_html(make_page=False)
        self.assertEqual(implicit_html, explicit_html)
        self.assertNotIn("_empty_", implicit_html)

    def test_omitted_attribution_sources_return_default_output(self) -> None:
        """Omitted attribution source arguments select default analytics output."""
        analytics = Analytics(_performance_rows())

        attribution = analytics.attribution(
            classification_name=None,
            classification_data_source=None,
            mapping_data_sources=(None, None),
        )
        self.assertTrue(attribution.to_polars(View.OVERALL_ATTRIBUTION).height > 0)

    def test_blank_sort_string_matches_omitted_sorting(self) -> None:
        """A blank sorting argument preserves default output ordering."""
        attribution = Analytics(_performance_rows()).attribution()

        default_output = attribution.to_polars(View.OVERALL_ATTRIBUTION)
        legacy_output = attribution.to_polars(
            View.OVERALL_ATTRIBUTION,
            columns_to_sort="",
        )

        self.assertTrue(default_output.equals(legacy_output))


if __name__ == "__main__":
    unittest.main()
