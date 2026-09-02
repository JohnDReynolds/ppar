"""Focused in-memory tests for performance input normalization and validation."""

# Python Imports
import datetime as dt
import math
from pathlib import Path
import tempfile
import unittest

# Third-Party Imports
import polars as pl

# Project Imports
import ppar.schema as cols
from ppar import Analytics
from ppar.attribution import View
from ppar.errors import PparError
from ppar.performance import Performance

_PERIODS = (
    (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
    (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
)


def _narrow_performance_df(include_names: bool = False) -> pl.DataFrame:
    """Return valid two-period, two-asset narrow input rows."""
    data: dict[str, list[dt.date] | list[str] | list[float]] = {
        cols.FROM_DATE: [_PERIODS[0][0], _PERIODS[0][0], _PERIODS[1][0], _PERIODS[1][0]],
        cols.THRU_DATE: [_PERIODS[0][1], _PERIODS[0][1], _PERIODS[1][1], _PERIODS[1][1]],
        cols.IDENTIFIER: ["A", "B", "A", "B"],
        cols.RETURN: [0.10, -0.05, 0.02, 0.03],
        cols.WEIGHT: [0.60, 0.40, 0.40, 0.60],
    }
    if include_names:
        data[cols.NAME] = ["Alpha", "Beta", "Alpha", "Beta"]
    return pl.DataFrame(data)


class TestPerformanceNormalization(unittest.TestCase):
    """Test narrow input forms and validation boundaries without CSV fixtures."""

    def test_polars_input_is_copied_before_normalization(self) -> None:
        """Mutating caller-owned Polars data cannot alter normalized state."""
        polars_input = _narrow_performance_df()
        from_polars = Performance(polars_input)
        polars_input[0, cols.RETURN] = 99.0

        self.assertNotEqual(from_polars.narrow_df[cols.RETURN].item(0), 99.0)

    def test_input_rows_are_sorted_by_thru_date(self) -> None:
        """Chronologically reversed input rows are normalized to period order."""
        expected = Performance(_narrow_performance_df())
        reversed_rows = Performance(_narrow_performance_df().reverse())

        self.assertTrue(expected.narrow_df.equals(reversed_rows.narrow_df))
        self.assertEqual(reversed_rows.period_totals()[cols.THRU_DATE].item(0), _PERIODS[0][1])

    def test_string_dates_are_normalized_before_requested_bounds(self) -> None:
        """In-memory ISO date strings support the same bounds as typed dates."""
        typed_dates = _narrow_performance_df()
        string_dates = _narrow_performance_df().with_columns(
            pl.col(cols.FROM_DATE).dt.to_string("%Y-%m-%d"),
            pl.col(cols.THRU_DATE).dt.to_string("%Y-%m-%d"),
        )

        from_strings = Performance(
            string_dates,
            from_date="2024-02-01",
            thru_date="2024-02-29",
        )
        from_typed_dates = Performance(
            typed_dates,
            from_date="2024-02-01",
            thru_date="2024-02-29",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "performance.csv"
            string_dates.write_csv(path)
            from_csv = Performance(
                path,
                from_date="2024-02-01",
                thru_date="2024-02-29",
            )

        self.assertEqual(
            from_strings.period_totals().select(cols.FROM_DATE, cols.THRU_DATE).row(0),
            _PERIODS[1],
        )
        self.assertTrue(from_strings.narrow_df.equals(from_typed_dates.narrow_df))
        self.assertTrue(from_strings.narrow_df.equals(from_csv.narrow_df))

    def test_csv_preserves_numeric_looking_identifiers(self) -> None:
        """CSV inference cannot alter textual security identities."""
        identifier_pairs = (
            ("001", "1"),
            ("99999999999999999999", "2"),
            ("A01", "B02"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "performance.csv"
            for identifiers in identifier_pairs:
                with self.subTest(identifiers=identifiers):
                    path.write_text(
                        "from_date,thru_date,identifier,return,weight\n"
                        f"2024-01-01,2024-01-31,{identifiers[0]},0.01,0.5\n"
                        f"2024-01-01,2024-01-31,{identifiers[1]},0.02,0.5\n",
                        encoding="utf-8",
                    )

                    performance = Performance(path)
                    detail = (
                        Analytics(path)
                        .attribution()
                        .to_polars(View.SUBPERIOD_ATTRIBUTION)
                    )

                    self.assertEqual(performance.identifiers, sorted(identifiers))
                    self.assertEqual(
                        sorted(detail[cols.CLASSIFICATION_IDENTIFIER].to_list()),
                        sorted(identifiers),
                    )

    def test_generic_performance_rejects_blank_identifiers(self) -> None:
        """Generic CSV and Polars identities must contain non-whitespace text."""
        for invalid_identifier in (None, "", " "):
            frame = pl.DataFrame(
                {
                    cols.FROM_DATE: [dt.date(2024, 1, 1)] * 2,
                    cols.THRU_DATE: [dt.date(2024, 1, 31)] * 2,
                    cols.IDENTIFIER: [invalid_identifier, "B"],
                    cols.RETURN: [0.01, 0.02],
                    cols.WEIGHT: [0.5, 0.5],
                }
            )
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "performance.csv"
                frame.write_csv(path)
                for data_source in (frame, path):
                    with self.subTest(
                        invalid_identifier=invalid_identifier,
                        source_type=type(data_source).__name__,
                    ):
                        with self.assertRaises(PparError) as context:
                            Performance(data_source)

                        self.assertIn("identifier", str(context.exception))
                        self.assertIn("non-null and nonblank", str(context.exception))
                        self.assertEqual(
                            context.exception.context.get("field"),
                            cols.IDENTIFIER,
                        )

    def test_generic_performance_trims_surrounding_whitespace(self) -> None:
        """Generic CSV and Polars identities and names are normalized at ingestion."""
        frame = _narrow_performance_df(include_names=True).with_columns(
            pl.col(cols.IDENTIFIER).map_elements(
                lambda value: f"  {value}  ",
                return_dtype=pl.String,
            ),
            pl.col(cols.NAME).map_elements(
                lambda value: f"  {value}  ",
                return_dtype=pl.String,
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "performance.csv"
            frame.write_csv(path)
            for data_source in (frame, path):
                with self.subTest(source_type=type(data_source).__name__):
                    performance = Performance(data_source)

                    self.assertEqual(performance.identifiers, ["A", "B"])
                    self.assertEqual(
                        performance.classification_items[cols.CLASSIFICATION_NAME].to_list(),
                        ["Alpha", "Beta"],
                    )

    def test_generic_performance_preserves_internal_identifier_spaces(self) -> None:
        """Internal spaces are identity content rather than surrounding padding."""
        frame = _narrow_performance_df().with_columns(
            pl.col(cols.IDENTIFIER).replace({"A": "Alpha Holding"})
        )

        performance = Performance(frame)

        self.assertEqual(performance.identifiers, ["Alpha Holding", "B"])

    def test_from_date_selects_periods_by_their_thru_date(self) -> None:
        """A lower bound before, at, or inside a period retains that full period."""
        frame = _narrow_performance_df()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "performance.csv"
            frame.write_csv(path)
            for data_source in (frame, path):
                for from_date in (
                    dt.date.min,
                    dt.date(2023, 12, 31),
                    dt.date(2024, 1, 31),
                    dt.date(2024, 1, 15),
                ):
                    with self.subTest(
                        source_type=type(data_source).__name__,
                        from_date=from_date,
                    ):
                        performance = Performance(data_source, from_date=from_date)
                        self.assertEqual(
                            performance.period_totals()[cols.THRU_DATE].to_list(),
                            [period[1] for period in _PERIODS],
                        )

    def test_invalid_in_memory_date_text_raises_ppar_error_with_bounds(self) -> None:
        """Malformed in-memory dates do not leak a raw Polars exception."""
        invalid_dates = _narrow_performance_df().with_columns(
            pl.col(cols.FROM_DATE).dt.to_string("%Y-%m-%d"),
            pl.when(pl.col(cols.THRU_DATE) == _PERIODS[0][1])
            .then(pl.lit("not-a-date"))
            .otherwise(pl.col(cols.THRU_DATE).dt.to_string("%Y-%m-%d"))
            .alias(cols.THRU_DATE),
        )

        with self.assertRaises(PparError):
            Performance(invalid_dates, from_date="2024-01-01")

    def test_input_column_order_does_not_affect_calculations(self) -> None:
        """Narrow input columns may arrive in any order."""
        expected = Performance(_narrow_performance_df())
        shuffled_columns = _narrow_performance_df().select(
            cols.WEIGHT,
            cols.THRU_DATE,
            cols.IDENTIFIER,
            cols.RETURN,
            cols.FROM_DATE,
        )
        normalized = Performance(shuffled_columns)

        self.assertEqual(normalized.identifiers, ["A", "B"])
        self.assertTrue(expected.narrow_df.equals(normalized.narrow_df))

    def test_inclusive_from_dates_are_preserved(self) -> None:
        """Inclusive month from dates are retained as supplied."""
        inclusive_input = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1), dt.date(2024, 2, 1)],
                cols.THRU_DATE: [dt.date(2024, 1, 31), dt.date(2024, 2, 29)],
                cols.IDENTIFIER: ["A", "A"],
                cols.RETURN: [0.01, 0.02],
                cols.WEIGHT: [1.0, 1.0],
            }
        )

        performance = Performance(inclusive_input)

        self.assertEqual(
            performance.period_totals()[cols.FROM_DATE].to_list(),
            [dt.date(2024, 1, 1), dt.date(2024, 2, 1)],
        )

    def test_narrow_names_populate_classification_items(self) -> None:
        """Narrow security names remain available for inferred classifications."""
        performance = Performance(_narrow_performance_df(include_names=True))
        items = performance.classification_items.sort(cols.CLASSIFICATION_IDENTIFIER)

        self.assertEqual(
            items.to_dict(as_series=False),
            {
                cols.CLASSIFICATION_IDENTIFIER: ["A", "B"],
                cols.CLASSIFICATION_NAME: ["Alpha", "Beta"],
            },
        )

    def test_inferred_names_use_latest_period_independent_of_row_order(self) -> None:
        """Physical input order cannot change an identifier's inferred name."""
        changing_names = _narrow_performance_df(include_names=True).with_columns(
            pl.when(
                (pl.col(cols.IDENTIFIER) == "A")
                & (pl.col(cols.THRU_DATE) == _PERIODS[0][1])
            )
            .then(pl.lit("Alpha Old"))
            .when(
                (pl.col(cols.IDENTIFIER) == "A")
                & (pl.col(cols.THRU_DATE) == _PERIODS[1][1])
            )
            .then(pl.lit("Alpha New"))
            .otherwise(pl.col(cols.NAME))
            .alias(cols.NAME)
        )

        chronological = Performance(changing_names).classification_items
        reversed_rows = Performance(changing_names.reverse()).classification_items

        self.assertTrue(chronological.equals(reversed_rows))
        alpha_name = chronological.filter(
            pl.col(cols.CLASSIFICATION_IDENTIFIER) == "A"
        )[cols.CLASSIFICATION_NAME].item()
        self.assertEqual(alpha_name, "Alpha New")

    def test_narrow_input_without_names_has_no_classification_items(self) -> None:
        """Narrow inputs retain calculated state without inferred classifications."""
        performance = Performance(_narrow_performance_df())

        self.assertTrue(performance.classification_items.is_empty())
        self.assertEqual(performance.narrow_df.height, 4)
        self.assertEqual(
            set(performance.narrow_df.columns),
            {
                cols.FROM_DATE,
                cols.THRU_DATE,
                cols.QUANTITY_OF_DAYS,
                cols.TOTAL_RETURN,
                cols.IDENTIFIER,
                cols.RETURN,
                cols.WEIGHT,
                cols.CONTRIBUTION,
            },
        )
        first_period = performance.narrow_df.filter(
            pl.col(cols.THRU_DATE) == dt.date(2024, 1, 31)
        )
        self.assertAlmostEqual(float(first_period[cols.CONTRIBUTION].sum()), 0.04)
        self.assertAlmostEqual(first_period[cols.TOTAL_RETURN].unique().item(), 0.04)

    def test_calculated_row_replacement_is_not_a_public_api(self) -> None:
        """Performance does not expose mutable calculated-state replacement."""
        self.assertFalse(hasattr(Performance(_narrow_performance_df()), "reset_narrow_df"))

    def test_overall_rows_are_a_defensive_copy(self) -> None:
        """Mutating an overall result cannot alter its cached calculation."""
        performance = Performance(_narrow_performance_df())
        returned = performance.df_overall()
        returned[0, cols.TOTAL_RETURN] = 999.0

        self.assertNotEqual(performance.df_overall()[cols.TOTAL_RETURN].item(0), 999.0)

    def test_gapped_overall_weights_use_observed_period_days(self) -> None:
        """Unobserved calendar gaps do not dilute overall weights."""
        performance = Performance(
            pl.DataFrame(
                {
                    cols.FROM_DATE: [dt.date(2024, 1, 1)] * 2
                    + [dt.date(2024, 3, 1)] * 2,
                    cols.THRU_DATE: [dt.date(2024, 1, 31)] * 2
                    + [dt.date(2024, 3, 31)] * 2,
                    cols.IDENTIFIER: ["A", "B", "A", "B"],
                    cols.RETURN: [0.02, 0.00, 0.01, 0.03],
                    cols.WEIGHT: [0.60, 0.40, 0.40, 0.60],
                }
            )
        )

        overall = performance.df_overall().sort(cols.IDENTIFIER)

        self.assertEqual(overall[cols.QUANTITY_OF_DAYS].unique().item(), 62)
        self.assertTrue(math.isclose(overall[cols.WEIGHT].sum(), 1.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(overall[cols.WEIGHT].item(0), 0.50, abs_tol=1e-12))
        self.assertTrue(math.isclose(overall[cols.WEIGHT].item(1), 0.50, abs_tol=1e-12))

    def test_overall_weights_day_weight_irregular_and_continuous_periods(self) -> None:
        """Observed-period weighting handles unequal lengths with or without gaps."""
        cases = (
            (
                (
                    (dt.date(2024, 1, 1), dt.date(2024, 1, 10)),
                    (dt.date(2024, 3, 1), dt.date(2024, 3, 30)),
                ),
                "gapped",
            ),
            (
                (
                    (dt.date(2024, 1, 1), dt.date(2024, 1, 10)),
                    (dt.date(2024, 1, 11), dt.date(2024, 2, 9)),
                ),
                "continuous",
            ),
        )
        for periods, label in cases:
            with self.subTest(label=label):
                performance = Performance(
                    pl.DataFrame(
                        {
                            cols.FROM_DATE: [periods[0][0]] * 2 + [periods[1][0]] * 2,
                            cols.THRU_DATE: [periods[0][1]] * 2 + [periods[1][1]] * 2,
                            cols.IDENTIFIER: ["A", "B", "A", "B"],
                            cols.RETURN: [0.01, 0.02, -0.01, 0.03],
                            cols.WEIGHT: [0.20, 0.80, 0.80, 0.20],
                        }
                    )
                )

                overall = performance.df_overall().sort(cols.IDENTIFIER)

                self.assertEqual(overall[cols.QUANTITY_OF_DAYS].unique().item(), 40)
                self.assertTrue(
                    math.isclose(overall[cols.WEIGHT].sum(), 1.0, abs_tol=1e-12)
                )
                self.assertTrue(
                    math.isclose(overall[cols.WEIGHT].item(0), 0.65, abs_tol=1e-12)
                )
                self.assertTrue(
                    math.isclose(overall[cols.WEIGHT].item(1), 0.35, abs_tol=1e-12)
                )

    def test_overall_contribution_links_two_positive_periods(self) -> None:
        """Two 10 percent contributions reconcile to the 21 percent linked return."""
        performance = Performance(
            pl.DataFrame(
                {
                    cols.FROM_DATE: [dt.date(2024, 1, 1), dt.date(2024, 2, 1)],
                    cols.THRU_DATE: [dt.date(2024, 1, 31), dt.date(2024, 2, 29)],
                    cols.IDENTIFIER: ["A", "A"],
                    cols.RETURN: [0.10, 0.10],
                    cols.WEIGHT: [1.0, 1.0],
                }
            )
        )

        overall = performance.df_overall()

        self.assertTrue(
            math.isclose(overall[cols.TOTAL_RETURN].item(), 0.21, abs_tol=1e-12)
        )
        self.assertTrue(
            math.isclose(overall[cols.CONTRIBUTION].item(), 0.21, abs_tol=1e-12)
        )

    def test_overall_contributions_match_independent_carino_linking(self) -> None:
        """Multiple signed period results agree with an independent Carino calculation."""
        performance = Performance(_narrow_performance_df())
        period_returns = performance.period_totals()[cols.TOTAL_RETURN].to_list()
        overall_return = math.prod(1.0 + value for value in period_returns) - 1.0

        def smoothing_coefficient(value: float) -> float:
            return math.log1p(value) / value if value != 0.0 else 1.0

        denominator = smoothing_coefficient(overall_return)
        period_coefficients = [
            smoothing_coefficient(value) / denominator for value in period_returns
        ]
        expected: dict[str, float] = {}
        for identifier in ("A", "B"):
            rows = performance.narrow_df.filter(pl.col(cols.IDENTIFIER) == identifier)
            expected[identifier] = sum(
                contribution * coefficient
                for contribution, coefficient in zip(
                    rows[cols.CONTRIBUTION], period_coefficients
                )
            )

        overall = performance.df_overall().sort(cols.IDENTIFIER)

        for identifier, contribution in zip(
            overall[cols.IDENTIFIER], overall[cols.CONTRIBUTION]
        ):
            self.assertTrue(
                math.isclose(contribution, expected[identifier], abs_tol=1e-12)
            )
        self.assertTrue(
            math.isclose(overall[cols.CONTRIBUTION].sum(), overall_return, abs_tol=1e-12)
        )

    def test_overall_contribution_handles_zero_linked_total_return(self) -> None:
        """The zero-overall-return branch still links contributions exactly."""
        performance = Performance(
            pl.DataFrame(
                {
                    cols.FROM_DATE: [dt.date(2024, 1, 1), dt.date(2024, 2, 1)],
                    cols.THRU_DATE: [dt.date(2024, 1, 31), dt.date(2024, 2, 29)],
                    cols.IDENTIFIER: ["A", "A"],
                    cols.RETURN: [0.10, -(1.0 / 11.0)],
                    cols.WEIGHT: [1.0, 1.0],
                }
            )
        )

        overall = performance.df_overall()

        self.assertTrue(math.isclose(overall[cols.TOTAL_RETURN].item(), 0.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(overall[cols.CONTRIBUTION].item(), 0.0, abs_tol=1e-12))

    def test_duplicate_thru_dates_are_rejected(self) -> None:
        """Two different input periods may not share an thru date."""
        duplicate_dates = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
                cols.THRU_DATE: [dt.date(2024, 1, 31), dt.date(2024, 1, 31)],
                cols.IDENTIFIER: ["A", "B"],
                cols.RETURN: [0.01, 0.02],
                cols.WEIGHT: [1.0, 1.0],
            }
        )

        with self.assertRaises(PparError):
            Performance(duplicate_dates)

    def test_empty_filtered_input_is_rejected(self) -> None:
        """Date filtering that leaves no periods reports an input error."""
        with self.assertRaises(PparError):
            Performance(_narrow_performance_df(), thru_date=dt.date(1900, 1, 31))

    def test_duplicate_narrow_date_identifier_rows_are_rejected(self) -> None:
        """A duplicate narrow asset row is rejected during validation."""
        duplicate = pl.concat([_narrow_performance_df(), _narrow_performance_df().head(1)])

        with self.assertRaises(PparError):
            Performance(duplicate)

    def test_weights_that_do_not_net_to_one_are_rejected(self) -> None:
        """Input rows whose weights do not sum to one are rejected."""
        invalid_weights = _narrow_performance_df().with_columns(
            pl.when(pl.col(cols.IDENTIFIER) == "B")
            .then(pl.lit(0.20))
            .otherwise(pl.col(cols.WEIGHT))
            .alias(cols.WEIGHT)
        )

        with self.assertRaises(PparError):
            Performance(invalid_weights)

    def test_null_returns_are_rejected(self) -> None:
        """Missing numeric observations are rejected from in-memory inputs."""
        null_returns = _narrow_performance_df().with_columns(
            pl.when(pl.col(cols.IDENTIFIER) == "A")
            .then(pl.lit(None))
            .otherwise(pl.col(cols.RETURN))
            .alias(cols.RETURN)
        )

        with self.assertRaises(PparError):
            Performance(null_returns)

    def test_infinite_returns_and_weights_are_rejected(self) -> None:
        """Infinite financial values are rejected with other invalid observations."""
        for column_name in (cols.RETURN, cols.WEIGHT):
            with self.subTest(column_name=column_name):
                invalid = _narrow_performance_df().with_columns(
                    pl.when(pl.col(cols.IDENTIFIER) == "A")
                    .then(pl.lit(float("inf")))
                    .otherwise(pl.col(column_name))
                    .alias(column_name)
                )

                with self.assertRaises(PparError):
                    Performance(invalid)

    def test_from_date_after_thru_date_is_rejected(self) -> None:
        """An input row may not start after its reporting date."""
        invalid_period = _narrow_performance_df().head(2).with_columns(
            pl.lit(dt.date(2024, 2, 1)).alias(cols.FROM_DATE)
        )

        with self.assertRaises(PparError):
            Performance(invalid_period)

    def test_overlapping_dates_are_rejected(self) -> None:
        """Overlapping adjacent performance periods are rejected."""
        overlapping = _narrow_performance_df().with_columns(
            pl.Series(
                cols.FROM_DATE,
                [dt.date(2024, 1, 1)] * 2 + [dt.date(2024, 1, 31)] * 2,
            )
        )

        with self.assertRaises(PparError):
            Performance(overlapping)

    def test_missing_return_and_weight_columns_are_rejected(self) -> None:
        """Legacy wide-format performance inputs are no longer accepted."""
        invalid_columns = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1)],
                cols.THRU_DATE: [dt.date(2024, 1, 31)],
                "A.ret": [0.01],
                "A.wgt": [1.0],
            }
        )

        with self.assertRaises(PparError):
            Performance(invalid_columns)

    def test_invalid_numeric_return_is_rejected(self) -> None:
        """An unparseable return value reports a numeric input error."""
        invalid_return = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1)],
                cols.THRU_DATE: [dt.date(2024, 1, 31)],
                cols.IDENTIFIER: ["A"],
                cols.RETURN: ["not-a-number"],
                cols.WEIGHT: [1.0],
            }
        )

        with self.assertRaises(PparError):
            Performance(invalid_return)

    def test_requested_from_date_after_thru_date_is_rejected(self) -> None:
        """A reversed requested date window is rejected before calculation."""
        with self.assertRaises(PparError):
            Performance(
                _narrow_performance_df(),
                from_date=dt.date(2024, 2, 1),
                thru_date=dt.date(2024, 1, 1),
            )

    def test_invalid_date_text_is_rejected(self) -> None:
        """A malformed requested date string is rejected during normalization."""
        with self.assertRaises(PparError):
            Performance(_narrow_performance_df(), from_date="2020-aa-bb")

    def test_missing_input_file_is_rejected(self) -> None:
        """A missing file data source reports the requested input path."""
        with self.assertRaises(PparError):
            Performance("_does_not_exist_")


if __name__ == "__main__":
    unittest.main()
