"""Contracts for optional values that use ``None`` as the sole omission marker."""

# Python imports
import datetime as dt
import unittest

# Third-party imports
import polars as pl

# Project imports
from ppar import Analytics
from ppar.attribution import Chart, View
from ppar.errors import PparError
from ppar.performance import Performance
import ppar.schema as cols
import ppar.utilities as util


def _performance_rows() -> pl.DataFrame:
    """Return minimal narrow performance rows for optional-value tests."""
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
    """Verify omission uses ``None`` and supplied blank strings are errors."""

    def test_optional_string_accepts_none_and_rejects_blank_values(self) -> None:
        """The shared optional-string boundary never converts blanks to omission."""
        self.assertIsNone(util.normalize_optional_string(None, "display_name"))
        self.assertEqual(
            util.normalize_optional_string("Security", "display_name"),
            "Security",
        )
        for value in ("", "   "):
            with self.subTest(value=value):
                with self.assertRaisesRegex(PparError, "display_name must not be blank"):
                    util.normalize_optional_string(value, "display_name")

    def test_omitted_performance_metadata_uses_none(self) -> None:
        """Absent public performance metadata is stored as ``None``."""
        performance = Performance(_performance_rows())

        self.assertIsNone(performance.name)
        self.assertIsNone(performance.classification_name)

    def test_blank_analytics_metadata_is_rejected(self) -> None:
        """Names and classifications cannot masquerade as omitted values."""
        with self.assertRaisesRegex(PparError, "portfolio_name must not be blank"):
            Analytics(_performance_rows(), portfolio_name=" ")
        with self.assertRaisesRegex(PparError, "benchmark_name must not be blank"):
            Analytics(
                _performance_rows(),
                _performance_rows(),
                benchmark_name=" ",
            )
        with self.assertRaisesRegex(
            PparError,
            "portfolio_classification_name must not be blank",
        ):
            Analytics(_performance_rows(), portfolio_classification_name=" ")
        with self.assertRaisesRegex(
            PparError,
            "benchmark_classification_name must not be blank",
        ):
            Analytics(
                _performance_rows(),
                _performance_rows(),
                benchmark_classification_name=" ",
            )

    def test_blank_benchmark_path_is_not_treated_as_omitted(self) -> None:
        """A supplied blank benchmark path cannot select portfolio-as-benchmark."""
        with self.assertRaisesRegex(PparError, "path must not be blank"):
            Analytics(_performance_rows(), "")

    def test_blank_attribution_arguments_are_rejected(self) -> None:
        """Classification inputs and labels require ``None`` for omission."""
        analytics = Analytics(_performance_rows())
        with self.assertRaisesRegex(PparError, "classification_name"):
            analytics.attribution(classification_name="")
        with self.assertRaisesRegex(PparError, "path must not be blank"):
            analytics.attribution(classification_data_source=" ")
        with self.assertRaisesRegex(PparError, "paths must not be blank"):
            analytics.attribution(mapping_data_sources=("", None))
        with self.assertRaisesRegex(PparError, "classification_label"):
            analytics.attribution(classification_label="")

    def test_omitted_attribution_sources_return_default_output(self) -> None:
        """Explicit ``None`` source arguments select default attribution output."""
        analytics = Analytics(_performance_rows())

        attribution = analytics.attribution(
            classification_name=None,
            classification_data_source=None,
            mapping_data_sources=(None, None),
        )
        self.assertGreater(
            attribution.to_polars(View.OVERALL_ATTRIBUTION).height,
            0,
        )

    def test_blank_sort_column_is_rejected_for_tables_and_charts(self) -> None:
        """A blank sort column cannot silently select default ordering."""
        attribution = Analytics(_performance_rows()).attribution()

        with self.assertRaisesRegex(PparError, "columns_to_sort must not be blank"):
            attribution.to_polars(View.OVERALL_ATTRIBUTION, columns_to_sort=" ")
        with self.assertRaisesRegex(PparError, "columns_to_sort must not be blank"):
            attribution.to_chart(Chart.OVERALL_ATTRIBUTION, columns_to_sort="")


if __name__ == "__main__":
    unittest.main()
