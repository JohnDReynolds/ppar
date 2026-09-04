"""Verify ppar's retained reporting-frequency integration boundary."""

import datetime as dt
from pathlib import Path
import tempfile
import unittest
import warnings

from ppar import Analytics
from ppar.attribution import View
from ppar.errors import PparError
from ppar.frequency import Frequency, load_holidays
import ppar.schema as cols
import ppar.utilities as util
from tests import helpers as test_util


_HOLIDAYS_PATH = test_util.HOLIDAYS_PATH


class TestFrequencyIntegration(unittest.TestCase):
    """Exercise translation, presentation, warnings, and host-owned holiday I/O."""

    def test_daily_to_monthly(self) -> None:
        """One real fixture proves consolidation reaches ppar's public result schema."""
        analytics = Analytics(
            test_util.performance_data_path("big2_daily"),
            test_util.performance_data_path("Big 2"),
            from_date=dt.date(2021, 1, 1),
            frequency=Frequency.MONTHLY,
            holidays=_HOLIDAYS_PATH,
        )
        output = test_util.attribution(analytics).to_polars(
            View.SUBPERIOD_ATTRIBUTION
        )

        self.assertEqual(output[cols.FROM_DATE].item(0), dt.date(2021, 1, 1))
        self.assertEqual(output[cols.THRU_DATE].item(4), dt.date(2021, 3, 31))
        self.assertTrue(
            util.are_near(
                output[cols.TOTAL_EFFECT_SIMPLE].item(3),
                0.0012545960452570828,
            )
        )
        self.assertTrue(
            util.are_near(
                output[cols.SELECTION_EFFECT_SIMPLE].item(14),
                0.001057705826113624,
            )
        )

    def test_map_mixed_frequency(self) -> None:
        """Mapping and consolidation compose through the host's public workflow."""
        analytics = Analytics(
            test_util.performance_data_path("Magnificent 7"),
            test_util.performance_data_path("economic_sector_daily"),
            portfolio_classification_name="Security",
            benchmark_classification_name="Economic Sector",
            frequency=Frequency.MONTHLY,
            holidays=_HOLIDAYS_PATH,
        )
        attribution = test_util.attribution(analytics, "Economic Sector")
        classifications = attribution.to_polars(View.OVERALL_ATTRIBUTION)[
            cols.CLASSIFICATION_IDENTIFIER
        ]

        self.assertEqual(
            classifications[:6].to_list(),
            ["CD", "CO", "EN", "HC", "IT", "MA"],
        )
        self.assertEqual(
            attribution.to_polars(View.SUBPERIOD_SUMMARY).shape,
            (141, 11),
        )

    def test_asymmetric_terminal_bucket_uses_ppar_error_contract(self) -> None:
        """One real alignment failure must cross the adapter as a PparError."""
        portfolio = test_util.make_performance_df(
            (
                (dt.date(2023, 11, 1), dt.date(2023, 11, 30)),
                (dt.date(2023, 12, 1), dt.date(2023, 12, 28)),
            ),
            {"A": ([0.01, 0.02], [1.0, 1.0])},
        )
        benchmark = test_util.make_performance_df(
            (
                (dt.date(2023, 11, 1), dt.date(2023, 11, 30)),
                (dt.date(2023, 12, 1), dt.date(2023, 12, 31)),
            ),
            {"A": ([0.01, 0.02], [1.0, 1.0])},
        )

        with self.assertRaisesRegex(PparError, "terminal-bucket completeness"):
            Analytics(portfolio, benchmark, frequency=Frequency.MONTHLY)

    def test_incomplete_interior_bucket_preserves_portable_warning(self) -> None:
        """One public case retains truncation output and warning detail."""
        performance = test_util.make_performance_df(
            (
                (dt.date(2023, 11, 1), dt.date(2023, 11, 30)),
                (dt.date(2023, 12, 1), dt.date(2023, 12, 28)),
                (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
            ),
            {"A": ([0.01, 0.02, 0.03], [1.0, 1.0, 1.0])},
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            summary = Analytics(
                performance,
                performance.clone(),
                frequency=Frequency.MONTHLY,
            ).attribution().to_polars(View.SUBPERIOD_SUMMARY)

        self.assertEqual(summary[cols.THRU_DATE].to_list(), [dt.date(2023, 11, 30)])
        self.assertEqual(len(caught), 1)
        self.assertIn("source endpoint 2023-12-28", str(caught[0].message))
        self.assertIn("expected endpoint 2023-12-29", str(caught[0].message))

    def test_holiday_file_authorizes_the_prior_business_endpoint(self) -> None:
        """Host-loaded holidays must reach portable quarter-end preparation."""
        performance = test_util.make_performance_df(
            (
                (dt.date(2023, 10, 1), dt.date(2023, 12, 29)),
                (dt.date(2023, 12, 30), dt.date(2024, 3, 28)),
                (dt.date(2024, 3, 29), dt.date(2024, 6, 28)),
            ),
            {"A": ([0.01, 0.02, 0.03], [1.0, 1.0, 1.0])},
        )

        with tempfile.TemporaryDirectory() as directory:
            holidays_path = Path(directory) / "holidays.csv"
            holidays_path.write_text("2024-03-29\n", encoding="utf-8")
            summary = Analytics(
                performance,
                performance.clone(),
                frequency=Frequency.QUARTERLY,
                holidays=holidays_path,
            ).attribution().to_polars(View.SUBPERIOD_SUMMARY)

        self.assertEqual(
            summary[cols.THRU_DATE].to_list(),
            [
                dt.date(2023, 12, 29),
                dt.date(2024, 3, 28),
                dt.date(2024, 6, 28),
            ],
        )

    def test_headerless_holidays_file_is_strict(self) -> None:
        """The retained ppar holiday-file loader enforces its host contract."""
        with tempfile.TemporaryDirectory() as directory:
            holidays_path = Path(directory) / "holidays.csv"
            holidays_path.write_text(
                "2024-03-29\n2024-12-25\n",
                encoding="utf-8",
            )
            self.assertEqual(
                load_holidays(holidays_path),
                frozenset((dt.date(2024, 3, 29), dt.date(2024, 12, 25))),
            )

            for invalid_text in (
                "date\n2024-03-29\n",
                "2024-03-29,Good Friday\n",
                "2024-03-29\n2024-03-29\n",
                "\n",
            ):
                with self.subTest(invalid_text=invalid_text):
                    holidays_path.write_text(invalid_text, encoding="utf-8")
                    with self.assertRaises(PparError):
                        load_holidays(holidays_path)


if __name__ == "__main__":
    unittest.main()
