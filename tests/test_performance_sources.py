"""Verify ppar's performance-source translation and presentation boundaries."""

import datetime as dt
from pathlib import Path
import tempfile
import unittest

import polars as pl
from polars.testing import assert_frame_equal

from ppar import Analytics
from ppar.attribution import View
from ppar.errors import PparError
import ppar.schema as cols


_PERIODS = (
    (dt.date(2024, 1, 1), dt.date(2024, 1, 31)),
    (dt.date(2024, 2, 1), dt.date(2024, 2, 29)),
)


def _performance_rows(*, include_names: bool = False) -> pl.DataFrame:
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


def _detail(
    source: str | Path | pl.DataFrame,
    benchmark: str | Path | pl.DataFrame | None = None,
    **arguments: object,
) -> pl.DataFrame:
    """Return public security-level detail for one translated source pair."""
    return Analytics(
        source,
        benchmark,
        portfolio_classification_name="Security",
        benchmark_classification_name="Security" if benchmark is not None else None,
        **arguments,  # type: ignore[arg-type]
    ).attribution().to_polars(View.SUBPERIOD_ATTRIBUTION)


class TestPerformanceSources(unittest.TestCase):
    """Test ppar-owned input translation, metadata, and error behavior."""

    def test_polars_input_is_owned_after_analytics_construction(self) -> None:
        """Mutating a caller-owned frame cannot alter an existing calculation."""
        source = _performance_rows()
        analytics = Analytics(source)
        expected = analytics.attribution().to_polars(View.SUBPERIOD_ATTRIBUTION)

        source[0, cols.RETURN] = 99.0

        assert_frame_equal(
            analytics.attribution().to_polars(View.SUBPERIOD_ATTRIBUTION),
            expected,
        )

    def test_csv_and_polars_inputs_produce_the_same_public_rows(self) -> None:
        """Both supported containers cross the adapter with equivalent results."""
        source = _performance_rows(include_names=True).with_columns(
            pl.col(cols.FROM_DATE).dt.to_string("%Y-%m-%d"),
            pl.col(cols.THRU_DATE).dt.to_string("%Y-%m-%d"),
        )
        expected = _detail(
            source,
            from_date="2024-02-01",
            thru_date="2024-02-29",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "performance.csv"
            source.write_csv(path)
            actual = _detail(
                path,
                from_date="2024-02-01",
                thru_date="2024-02-29",
            )

        assert_frame_equal(actual, expected)
        self.assertEqual(actual[cols.FROM_DATE].unique().item(), _PERIODS[1][0])
        self.assertEqual(actual[cols.THRU_DATE].unique().item(), _PERIODS[1][1])

    def test_csv_preserves_numeric_looking_identifiers(self) -> None:
        """CSV inference cannot alter textual security identities."""
        identifier_pairs = (
            ("001", "1"),
            ("99999999999999999999", "2"),
            ("A01", "B02"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "performance.csv"
            for identifiers in identifier_pairs:
                with self.subTest(identifiers=identifiers):
                    path.write_text(
                        "from_date,thru_date,identifier,return,weight\n"
                        f"2024-01-01,2024-01-31,{identifiers[0]},0.01,0.5\n"
                        f"2024-01-01,2024-01-31,{identifiers[1]},0.02,0.5\n",
                        encoding="utf-8",
                    )

                    identifiers_in_result = sorted(
                        _detail(path)[cols.CLASSIFICATION_IDENTIFIER].to_list()
                    )

                    self.assertEqual(identifiers_in_result, sorted(identifiers))

    def test_text_normalization_preserves_meaningful_internal_spaces(self) -> None:
        """Surrounding padding is removed without changing identity content."""
        source = _performance_rows(include_names=True).with_columns(
            pl.col(cols.IDENTIFIER).replace({"A": "  Alpha Holding  ", "B": "  B  "}),
            pl.col(cols.NAME).replace({"Alpha": "  Alpha Name  ", "Beta": "  Beta  "}),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "performance.csv"
            source.write_csv(path)
            for data_source in (source, path):
                with self.subTest(source_type=type(data_source).__name__):
                    detail = _detail(data_source).sort(cols.CLASSIFICATION_IDENTIFIER)
                    self.assertEqual(
                        detail[cols.CLASSIFICATION_IDENTIFIER].unique().sort().to_list(),
                        ["Alpha Holding", "B"],
                    )
                    names = (
                        detail.select(
                            cols.CLASSIFICATION_IDENTIFIER,
                            cols.CLASSIFICATION_NAME,
                        )
                        .unique()
                        .sort(cols.CLASSIFICATION_IDENTIFIER)
                    )
                    self.assertEqual(
                        names[cols.CLASSIFICATION_NAME].to_list(),
                        ["Alpha Name", "Beta"],
                    )

    def test_inferred_name_uses_latest_aligned_retained_period(self) -> None:
        """Excluded or unmatched history cannot affect a display name."""
        portfolio = pl.DataFrame(
            {
                cols.FROM_DATE: [period[0] for period in _PERIODS],
                cols.THRU_DATE: [period[1] for period in _PERIODS],
                cols.IDENTIFIER: ["A", "A"],
                cols.RETURN: [0.01, 0.02],
                cols.WEIGHT: [1.0, 1.0],
                cols.NAME: ["Alpha Old", "Alpha New"],
            }
        )
        first_period = _detail(portfolio, thru_date=_PERIODS[0][1])
        aligned_first_period = _detail(portfolio, portfolio.head(1))
        full_history = _detail(portfolio)

        self.assertEqual(first_period[cols.CLASSIFICATION_NAME].item(), "Alpha Old")
        self.assertEqual(
            aligned_first_period[cols.CLASSIFICATION_NAME].item(),
            "Alpha Old",
        )
        self.assertEqual(
            full_history[cols.CLASSIFICATION_NAME].unique().to_list(),
            ["Alpha New"],
        )

    def test_supplied_contribution_does_not_override_public_input_semantics(self) -> None:
        """Generic inputs continue to derive contribution from weight and return."""
        source = _performance_rows().with_columns(
            pl.Series(cols.CONTRIBUTION, [0.07, -0.03, 0.01, 0.01])
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "performance.csv"
            source.write_csv(path)
            for data_source in (source, path):
                with self.subTest(source_type=type(data_source).__name__):
                    detail = Analytics(data_source).attribution().to_polars(
                        View.SUBPERIOD_ATTRIBUTION
                    )
                    self.assertEqual(
                        detail[cols.PORTFOLIO_CONTRIB_SIMPLE].round(12).to_list(),
                        [0.06, -0.02, 0.008, 0.018],
                    )

    def test_invalid_sources_are_translated_to_ppar_errors(self) -> None:
        """Representative Polars and filesystem failures retain ppar's error type."""
        invalid_sources: tuple[str | pl.DataFrame, ...] = (
            _performance_rows().drop(cols.RETURN),
            _performance_rows().with_columns(pl.lit("bad-date").alias(cols.FROM_DATE)),
            "_does_not_exist_",
        )
        for source in invalid_sources:
            with self.subTest(source_type=type(source).__name__):
                with self.assertRaises(PparError):
                    Analytics(source)

    def test_missing_csv_error_identifies_the_user_path(self) -> None:
        """A missing input names its path without exposing the portable core."""
        with tempfile.TemporaryDirectory() as temporary:
            missing_path = Path(temporary) / "missing-performance.csv"

            with self.assertRaises(PparError) as context:
                Analytics(missing_path)

        self.assertEqual(
            str(context.exception),
            f"Performance CSV path must identify an existing local file: "
            f"{str(missing_path)!r}.",
        )
        self.assertEqual(
            context.exception.context,
            {"boundary": "Performance CSV", "path": str(missing_path)},
        )
        self.assertNotIn("perfattr", str(context.exception))


if __name__ == "__main__":
    unittest.main()
