"""Integration tests for consolidation across dates and report frequencies."""

# Calculation regression checks exercise internal calculated frames.
# pylint: disable=protected-access
# pyright: reportPrivateUsage=false

# Python Imports
import datetime as dt
from pathlib import Path
import tempfile
import unittest
import warnings

# Test Imports
from tests import test_utilities as test_util

# Project Imports
from ppar import Analytics
from ppar.attribution import View
import ppar.schema as cols
from ppar.frequency import (
    date_matches_frequency,
    Frequency,
    frequency_bucket,
    frequency_bucket_end,
    frequency_bucket_effective_end,
    load_holidays,
)
from ppar.performance import Performance
from ppar.errors import PparError
import ppar.utilities as util

_HOLIDAYS_PATH = Path("tests/data/holidays.csv")


class TestFrequencyIntegration(unittest.TestCase):
    """Verify fixture-based consolidation and date-window workflows."""

    def test_fixed_frequency_endpoint_candidates_are_conservative(self) -> None:
        """Calendar and weekend endpoints do not accept incomplete weekdays."""
        cases = (
            (dt.date(2022, 12, 30), Frequency.MONTHLY, True),
            (dt.date(2023, 12, 29), Frequency.MONTHLY, True),
            (dt.date(2023, 12, 28), Frequency.MONTHLY, False),
            (dt.date(2023, 7, 28), Frequency.MONTHLY, False),
            (dt.date(2023, 7, 29), Frequency.MONTHLY, False),
            (dt.date(2024, 1, 31), Frequency.MONTHLY, True),
            (dt.date(2024, 2, 29), Frequency.MONTHLY, True),
            (dt.date(2021, 2, 26), Frequency.MONTHLY, True),
            (dt.date(2022, 2, 25), Frequency.MONTHLY, False),
            (dt.date(2024, 3, 28), Frequency.QUARTERLY, False),
            (dt.date(2024, 3, 29), Frequency.QUARTERLY, True),
            (dt.date(2023, 8, 31), Frequency.QUARTERLY, False),
            (dt.date(2023, 9, 29), Frequency.QUARTERLY, True),
            (dt.date(2022, 12, 30), Frequency.YEARLY, True),
            (dt.date(2023, 12, 28), Frequency.YEARLY, False),
        )

        for date, frequency, expected in cases:
            with self.subTest(date=date, frequency=frequency):
                self.assertEqual(
                    date_matches_frequency(date, frequency),
                    expected,
                )
        good_friday = frozenset((dt.date(2024, 3, 29),))
        self.assertFalse(
            date_matches_frequency(
                dt.date(2024, 3, 29),
                Frequency.QUARTERLY,
                good_friday,
            )
        )
        self.assertTrue(
            date_matches_frequency(
                dt.date(2024, 3, 28),
                Frequency.QUARTERLY,
                good_friday,
            )
        )

    def test_frequency_bucket_end_remains_the_nominal_calendar_boundary(self) -> None:
        """Bucket metadata retains its calendar boundary."""
        for date, frequency, expected_end in (
            (
                dt.date(2023, 12, 29),
                Frequency.MONTHLY,
                dt.date(2023, 12, 31),
            ),
            (
                dt.date(2023, 9, 29),
                Frequency.QUARTERLY,
                dt.date(2023, 9, 30),
            ),
            (
                dt.date(2022, 12, 30),
                Frequency.YEARLY,
                dt.date(2022, 12, 31),
            ),
        ):
            with self.subTest(date=date, frequency=frequency):
                self.assertEqual(
                    frequency_bucket_end(
                        frequency_bucket(date, frequency),
                        frequency,
                    ),
                    expected_end,
                )

    def test_effective_end_rolls_over_weekends_and_consecutive_holidays(
        self,
    ) -> None:
        """Configured closures roll backward until a usable weekday is found."""
        cases = (
            (
                dt.date(2023, 7, 31),
                Frequency.MONTHLY,
                frozenset((dt.date(2023, 7, 31),)),
                dt.date(2023, 7, 28),
            ),
            (
                dt.date(2024, 3, 31),
                Frequency.QUARTERLY,
                frozenset((dt.date(2024, 3, 29),)),
                dt.date(2024, 3, 28),
            ),
            (
                dt.date(2023, 12, 31),
                Frequency.YEARLY,
                frozenset(
                    (
                        dt.date(2023, 12, 28),
                        dt.date(2023, 12, 29),
                    )
                ),
                dt.date(2023, 12, 27),
            ),
        )

        for nominal_end, frequency, holidays, expected_end in cases:
            with self.subTest(
                nominal_end=nominal_end,
                frequency=frequency,
            ):
                bucket = frequency_bucket(nominal_end, frequency)
                self.assertEqual(
                    frequency_bucket_effective_end(
                        bucket,
                        frequency,
                        holidays,
                    ),
                    expected_end,
                )
                self.assertTrue(
                    date_matches_frequency(
                        expected_end,
                        frequency,
                        holidays,
                    )
                )

    def test_crazy_frequency(self) -> None:
        """Incompatible irregular intervals require an explicit fixed frequency."""
        with self.assertRaises(PparError):
            Analytics(
                test_util.performance_data_path("case_mixed_frequency"),
                test_util.performance_data_path("case_crazy_frequency"),
            )

    def test_daily_to_monthly(self) -> None:
        """Daily performance consolidates to expected monthly attribution values."""
        analytics = Analytics(
            test_util.performance_data_path("big2_daily"),
            test_util.performance_data_path("Big 2"),
            from_date=dt.date(2021, 1, 1),
            frequency=Frequency.MONTHLY,
            holidays=_HOLIDAYS_PATH,
        )
        attribution = test_util.attribution(analytics)
        output = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

        self.assertEqual(output[cols.FROM_DATE].item(0), dt.date(2021, 1, 1))
        self.assertEqual(output[cols.THRU_DATE].item(4), dt.date(2021, 3, 31))
        self.assertTrue(
            util.are_near(output[cols.TOTAL_EFFECT_SIMPLE].item(3), 0.0012545960452570828)
        )
        self.assertTrue(
            util.are_near(output[cols.SELECTION_EFFECT_SIMPLE].item(14), 0.001057705826113624)
        )

        detail = attribution._construct_df_for_detail_views(View.SUBPERIOD_ATTRIBUTION).collect()
        self.assertTrue(
            util.are_near(detail[cols.TOTAL_EFFECT_SMOOTHED].item(3), 0.002038295249203867)
        )
        self.assertTrue(
            util.are_near(detail[cols.SELECTION_EFFECT_SMOOTHED].item(14), 0.0015709213702753996)
        )

    def test_daily_to_quarterly(self) -> None:
        """Daily performance consolidates to expected quarterly attribution values."""
        analytics = Analytics(
            test_util.performance_data_path("big2_daily"),
            test_util.performance_data_path("Big 2"),
            from_date=dt.date(2021, 1, 1),
            frequency=Frequency.QUARTERLY,
            holidays=_HOLIDAYS_PATH,
        )
        attribution = test_util.attribution(analytics)
        output = attribution.to_polars(View.SUBPERIOD_SUMMARY)

        self.assertEqual(output[cols.FROM_DATE].item(0), dt.date(2021, 1, 1))
        self.assertEqual(output[cols.THRU_DATE].item(4), dt.date(2022, 3, 31))
        self.assertTrue(
            util.are_near(output[cols.TOTAL_EFFECT_SIMPLE].item(3), -0.0020721529010043226)
        )
        self.assertTrue(util.are_near(output[cols.PORTFOLIO_RETURN].item(8), 0.2401702546346276))
        self.assertTrue(
            util.are_near(
                attribution._df[cols.TOTAL_EFFECT_SMOOTHED].item(3),
                -0.0027455892808818704,
            )
        )

    def test_map_mixed_frequency(self) -> None:
        """Mixed-frequency inputs map correctly to an economic-sector view."""
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

        self.assertEqual(classifications[:6].to_list(), ["CD", "CO", "EN", "HC", "IT", "MA"])
        self.assertEqual(attribution.to_polars(View.SUBPERIOD_SUMMARY).shape, (141, 11))

    def test_mixed_frequency(self) -> None:
        """Mixed-frequency input files align to their shared reporting periods."""
        analytics = Analytics(
            test_util.performance_data_path("case_mixed_frequency"),
            test_util.performance_data_path("case_monthly_frequency"),
            frequency=Frequency.MONTHLY,
        )

        self.assertEqual(
            len(test_util.attribution(analytics).to_polars(View.SUBPERIOD_SUMMARY)),
            3,
        )

    def test_monthly_to_yearly(self) -> None:
        """Monthly input consolidates to yearly reporting periods."""
        analytics = Analytics(
            test_util.performance_data_path("Big 2"),
            test_util.performance_data_path("big2_daily"),
            from_date=dt.date(2021, 1, 1),
            frequency=Frequency.YEARLY,
        )
        output = test_util.attribution(analytics).to_polars(View.SUBPERIOD_SUMMARY)

        self.assertEqual(len(output), 3)
        self.assertEqual(output[cols.FROM_DATE].item(0), dt.date(2021, 1, 1))
        self.assertEqual(output[cols.THRU_DATE].item(2), dt.date(2023, 12, 31))

    def test_fixed_frequency_rejects_missing_source_coverage(self) -> None:
        """A fixed monthly series cannot silently skip a month of source-data coverage."""
        performance = test_util.make_performance_df(
            (
                (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
                (dt.date(2024, 3, 1), dt.date(2024, 3, 31)),
            ),
            {"A": ([0.01, 0.02], [1.0, 1.0])},
        )

        with self.assertRaises(PparError):
            Analytics(
                performance,
                performance.clone(),
                frequency=Frequency.MONTHLY,
            )

    def test_fixed_frequency_recognizes_weekend_adjusted_month_end(self) -> None:
        """Friday before a weekend month-end closes its own reporting bucket."""
        performance = test_util.make_performance_df(
            (
                (dt.date(2021, 1, 1), dt.date(2021, 1, 29)),
                (dt.date(2021, 2, 1), dt.date(2021, 2, 28)),
            ),
            {"A": ([0.01, 0.02], [1.0, 1.0])},
        )

        analytics = Analytics(
            performance,
            performance.clone(),
            frequency=Frequency.MONTHLY,
        )

        summary = analytics.attribution().to_polars(View.SUBPERIOD_SUMMARY)
        self.assertEqual(summary.height, 2)
        self.assertEqual(
            summary[cols.THRU_DATE].to_list(),
            [dt.date(2021, 1, 29), dt.date(2021, 2, 28)],
        )

    def test_fixed_frequency_rejects_different_actual_source_end_dates(self) -> None:
        """Portfolio and benchmark must use the same actual reporting endpoint."""
        portfolio = test_util.make_performance_df(
            ((dt.date(2023, 12, 1), dt.date(2023, 12, 29)),),
            {"A": ([0.01], [1.0])},
        )
        benchmark = test_util.make_performance_df(
            ((dt.date(2023, 12, 1), dt.date(2023, 12, 31)),),
            {"A": ([0.02], [1.0])},
        )

        with self.assertRaises(PparError):
            Analytics(
                portfolio,
                benchmark,
                frequency=Frequency.MONTHLY,
            )

    def test_fixed_frequency_rejects_different_actual_source_start_dates(self) -> None:
        """A shared monthly label cannot hide unequal January return coverage."""
        portfolio = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 1, 31)),),
            {"A": ([0.01], [1.0])},
        )
        benchmark = test_util.make_performance_df(
            ((dt.date(2024, 1, 15), dt.date(2024, 1, 31)),),
            {"A": ([0.02], [1.0])},
        )

        with self.assertRaises(PparError) as context:
            Analytics(portfolio, benchmark, frequency=Frequency.MONTHLY)

        self.assertIn("2024-01-01", str(context.exception))
        self.assertIn("2024-01-15", str(context.exception))

    def test_fixed_frequency_rejects_a_source_period_wider_than_its_bucket(self) -> None:
        """A two-month return cannot be relabeled as a February monthly return."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 1), dt.date(2024, 2, 29)),),
            {"A": ([0.02], [1.0])},
        )

        with self.assertRaises(PparError) as context:
            Analytics(
                performance,
                performance.clone(),
                frequency=Frequency.MONTHLY,
            )

        self.assertIn("2024-01-01", str(context.exception))
        self.assertIn("2024-02", str(context.exception))

    def test_fixed_frequency_rejects_a_gap_inside_a_reporting_bucket(self) -> None:
        """Endpoint completeness cannot hide an unobserved day within a month."""
        performance = test_util.make_performance_df(
            (
                (dt.date(2024, 1, 1), dt.date(2024, 1, 10)),
                (dt.date(2024, 1, 12), dt.date(2024, 1, 31)),
            ),
            {"A": ([0.01, 0.02], [1.0, 1.0])},
        )

        with self.assertRaises(PparError) as context:
            Analytics(
                performance,
                performance.clone(),
                frequency=Frequency.MONTHLY,
            )

        self.assertIn("2024-01-11", str(context.exception))

    def test_fixed_frequency_accepts_different_partitions_of_equal_coverage(self) -> None:
        """Daily and monthly partitions may differ when their covered dates agree."""
        portfolio = test_util.make_performance_df(
            ((dt.date(2024, 2, 1), dt.date(2024, 2, 29)),),
            {"A": ([0.02], [1.0])},
        )
        benchmark = test_util.make_performance_df(
            (
                (dt.date(2024, 2, 1), dt.date(2024, 2, 14)),
                (dt.date(2024, 2, 15), dt.date(2024, 2, 29)),
            ),
            {"A": ([0.01, 0.01], [1.0, 1.0])},
        )

        summary = Analytics(
            portfolio,
            benchmark,
            frequency=Frequency.MONTHLY,
        ).attribution().to_polars(View.SUBPERIOD_SUMMARY)

        self.assertEqual(
            summary.select(cols.DATE_COLUMNS).row(0),
            (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
        )

    def test_fixed_frequency_rejects_a_partial_first_bucket(self) -> None:
        """Matching midmonth histories do not constitute a complete monthly return."""
        performance = test_util.make_performance_df(
            ((dt.date(2024, 1, 15), dt.date(2024, 1, 31)),),
            {"A": ([0.02], [1.0])},
        )

        with self.assertRaises(PparError) as context:
            Analytics(
                performance,
                performance.clone(),
                frequency=Frequency.MONTHLY,
            )

        self.assertIn("2024-01-15", str(context.exception))

    def test_fixed_frequency_prefers_one_bucket_when_two_endpoints_qualify(
        self,
    ) -> None:
        """Friday and literal weekend rows consolidate into one observation."""
        performance = test_util.make_performance_df(
            (
                (dt.date(2023, 12, 1), dt.date(2023, 12, 29)),
                (dt.date(2023, 12, 30), dt.date(2023, 12, 31)),
            ),
            {"A": ([0.01, 0.02], [1.0, 1.0])},
        )

        summary = Analytics(
            performance,
            performance.clone(),
            frequency=Frequency.MONTHLY,
        ).attribution().to_polars(View.SUBPERIOD_SUMMARY)

        self.assertEqual(summary.height, 1)
        self.assertEqual(summary[cols.THRU_DATE].item(), dt.date(2023, 12, 31))
        self.assertTrue(
            util.are_near(summary[cols.PORTFOLIO_RETURN].item(), 0.0302)
        )

    def test_fixed_frequency_omits_incomplete_terminal_bucket(self) -> None:
        """A terminal Thursday does not masquerade as a completed month."""
        performance = test_util.make_performance_df(
            (
                (dt.date(2023, 11, 1), dt.date(2023, 11, 30)),
                (dt.date(2023, 12, 1), dt.date(2023, 12, 28)),
            ),
            {"A": ([0.01, 0.02], [1.0, 1.0])},
        )

        summary = Analytics(
            performance,
            performance.clone(),
            frequency=Frequency.MONTHLY,
        ).attribution().to_polars(View.SUBPERIOD_SUMMARY)

        self.assertEqual(summary.height, 1)
        self.assertEqual(summary[cols.THRU_DATE].item(), dt.date(2023, 11, 30))

    def test_fixed_frequency_rejects_only_incomplete_terminal_bucket(self) -> None:
        """A Thursday-only terminal month cannot align to a complete benchmark."""
        portfolio = test_util.make_performance_df(
            ((dt.date(2023, 12, 1), dt.date(2023, 12, 28)),),
            {"A": ([0.01], [1.0])},
        )
        benchmark = test_util.make_performance_df(
            ((dt.date(2023, 12, 1), dt.date(2023, 12, 31)),),
            {"A": ([0.02], [1.0])},
        )

        with self.assertRaises(PparError):
            Analytics(
                portfolio,
                benchmark,
                frequency=Frequency.MONTHLY,
            )

    def test_fixed_frequency_rejects_asymmetric_terminal_bucket_after_history(
        self,
    ) -> None:
        """A shared prior month cannot hide unequal terminal completeness."""
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
            Analytics(
                portfolio,
                benchmark,
                frequency=Frequency.MONTHLY,
            )

    def test_fixed_frequency_truncates_at_incomplete_interior_bucket(self) -> None:
        """An incomplete month truncates later output with an explicit warning."""
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
        """A configured Friday holiday makes Thursday the accepted endpoint."""
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
        """Holiday files require unique ISO dates and exactly one column."""
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

    def test_specify_dates(self) -> None:
        """Explicit dates filter the fixture performance rows inclusively."""
        performance = Performance(
            test_util.performance_data_path("case_adjust_from_dates"),
            from_date="2023-01-31",
            thru_date="2023-02-28",
        )

        self.assertEqual(
            performance.period_totals()[cols.FROM_DATE].item(0), dt.date(2023, 1, 2)
        )
        self.assertEqual(
            performance.period_totals()[cols.THRU_DATE].to_list(),
            [dt.date(2023, 1, 31), dt.date(2023, 2, 12), dt.date(2023, 2, 28)],
        )


if __name__ == "__main__":
    unittest.main()
