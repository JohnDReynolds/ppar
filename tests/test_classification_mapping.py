"""Focused in-memory tests for classification inference and mapping behavior."""

import datetime as dt
from pathlib import Path
import tempfile
import unittest

import polars as pl

from ppar import Analytics
from ppar.attribution import Chart, View
import ppar.schema as cols
from ppar.errors import PparError


def _named_performance(
    a_name: str = "Alpha",
    b_name: str = "Beta",
) -> pl.DataFrame:
    """Return a minimal named performance data set for classification tests."""
    return pl.DataFrame(
        {
            cols.FROM_DATE: [dt.date(2024, 1, 1)] * 2,
            cols.THRU_DATE: [dt.date(2024, 2, 1)] * 2,
            cols.IDENTIFIER: ["A", "B"],
            cols.RETURN: [0.10, -0.05],
            cols.WEIGHT: [0.60, 0.40],
            cols.NAME: [a_name, b_name],
        }
    )


def _narrow_performance() -> pl.DataFrame:
    """Return a minimal narrow performance data set for attribution tests."""
    return pl.DataFrame(
        {
            cols.FROM_DATE: [dt.date(2024, 1, 1)] * 2,
            cols.THRU_DATE: [dt.date(2024, 2, 1)] * 2,
            cols.IDENTIFIER: ["A", "B"],
            cols.RETURN: [0.10, -0.05],
            cols.WEIGHT: [0.60, 0.40],
        }
    )


def _monthly_performance() -> pl.DataFrame:
    """Return three monthly periods whose identifiers can change classification."""
    return pl.DataFrame(
        {
            cols.FROM_DATE: [
                dt.date(2024, 1, 1),
                dt.date(2024, 1, 1),
                dt.date(2024, 2, 1),
                dt.date(2024, 2, 1),
                dt.date(2024, 3, 1),
                dt.date(2024, 3, 1),
            ],
            cols.THRU_DATE: [
                dt.date(2024, 1, 31),
                dt.date(2024, 1, 31),
                dt.date(2024, 2, 29),
                dt.date(2024, 2, 29),
                dt.date(2024, 3, 31),
                dt.date(2024, 3, 31),
            ],
            cols.IDENTIFIER: ["A", "B"] * 3,
            cols.RETURN: [0.05, 0.025, 0.04, 0.02, -0.025, 0.03],
            cols.WEIGHT: [0.60, 0.40] * 3,
        }
    )


def _effective_mapping() -> pl.DataFrame:
    """Return positional dated assignments in the public Polars source shape."""
    return pl.DataFrame(
        {
            "start": [dt.date(2024, 1, 1), dt.date(2024, 2, 1), dt.date(2024, 1, 1)],
            "end": [dt.date(2024, 1, 31), dt.date(2024, 3, 31), dt.date(2024, 3, 31)],
            "source": ["A", "A", "B"],
            "target": ["EQ", "FI", "BOND"],
        }
    )


def _pairs(values: dict[str, str]) -> pl.DataFrame:
    """Return a two-column Polars source from a compact test mapping."""
    return pl.DataFrame({"key": list(values), "value": list(values.values())})


class ClassificationTests(unittest.TestCase):
    """Verify ppar's public classification presentation boundary."""

    def test_classification_is_inferred_from_named_performances(self) -> None:
        """Matching named inputs provide an inferred classification."""
        attribution = Analytics(
            _named_performance(),
            _named_performance(),
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        ).attribution()
        detail = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

        self.assertEqual(
            detail.select(
                cols.CLASSIFICATION_IDENTIFIER,
                cols.CLASSIFICATION_NAME,
            )
            .unique()
            .sort(cols.CLASSIFICATION_IDENTIFIER)
            .to_dict(as_series=False),
            {
                cols.CLASSIFICATION_IDENTIFIER: ["A", "B"],
                cols.CLASSIFICATION_NAME: ["Alpha", "Beta"],
            },
        )

    def test_inferred_classification_rejects_conflicting_names(self) -> None:
        """Portfolio and benchmark cannot assign different names to one identifier."""
        with self.assertRaisesRegex(PparError, "conflicting values.*A"):
            Analytics(
                _named_performance(a_name="Portfolio Alpha"),
                _named_performance(a_name="Benchmark Alpha"),
                portfolio_classification_name="Security",
                benchmark_classification_name="Security",
            ).attribution()

    def test_explicit_classification_accepts_exact_duplicate_pairs(self) -> None:
        """Exact duplicate names collapse deterministically after filtering."""
        source = pl.DataFrame(
            {
                "identifier": [" A ", "A", " B ", "UNUSED"],
                "name": [" Alpha ", "Alpha", " Beta ", "Unused"],
            }
        )

        detail = Analytics(
            _named_performance(),
            portfolio_classification_name="Security",
        ).attribution(
            "Security",
            source,
        ).to_polars(View.SUBPERIOD_ATTRIBUTION)

        self.assertEqual(
            detail.select(
                cols.CLASSIFICATION_IDENTIFIER,
                cols.CLASSIFICATION_NAME,
            )
            .unique()
            .sort(cols.CLASSIFICATION_IDENTIFIER)
            .to_dict(as_series=False),
            {
                cols.CLASSIFICATION_IDENTIFIER: ["A", "B"],
                cols.CLASSIFICATION_NAME: ["Alpha", "Beta"],
            },
        )

    def test_explicit_classification_rejects_conflicts_for_dataframe_and_csv(
        self,
    ) -> None:
        """Conflicting names fail identically for Polars and headerless CSV sources."""
        source = pl.DataFrame(
            {
                "identifier": ["A", " A ", "B"],
                "name": ["Alpha", "Alternate Alpha", "Beta"],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "classification.csv"
            source.write_csv(path, include_header=False)
            for data_source in (source, source.reverse(), path):
                with self.subTest(source_type=type(data_source).__name__):
                    with self.assertRaisesRegex(PparError, "conflicting values.*A"):
                        Analytics(
                            _named_performance(),
                            portfolio_classification_name="Security",
                        ).attribution(
                            "Security",
                            data_source,
                        )

    def test_one_column_classification_source_is_rejected(self) -> None:
        """Explicit classification sources must supply identifier and name columns."""
        source = pl.DataFrame({"identifier": ["A", "B"]})

        with self.assertRaises(PparError):
            Analytics(
                _named_performance(),
                portfolio_classification_name="Security",
            ).attribution("Security", source)


class MappingTests(unittest.TestCase):
    """Verify portable mapping through ppar's public attribution workflow."""

    def test_mapped_attribution_rollup_preserves_portfolio_contribution(self) -> None:
        """Mapped attribution totals retain underlying portfolio contribution."""
        analytics = Analytics(
            _narrow_performance(),
            _narrow_performance(),
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )

        attribution = analytics.attribution(
            "Sector",
            _pairs({"TECH": "Technology"}),
            (_pairs({"A": "TECH", "B": "TECH"}),) * 2,
        )
        details = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)

        self.assertEqual(details.height, 1)
        self.assertEqual(details[cols.CLASSIFICATION_IDENTIFIER].item(), "TECH")
        self.assertEqual(details[cols.CLASSIFICATION_NAME].item(), "Technology")
        self.assertAlmostEqual(details[cols.PORTFOLIO_WEIGHT].item(), 1.0)
        self.assertAlmostEqual(details[cols.PORTFOLIO_CONTRIB_SIMPLE].item(), 0.04)

    def test_effective_mapping_csv_and_polars_sources_have_identical_results(
        self,
    ) -> None:
        """The existing generic workflow should expose portable dated assignment.

        Identifier A belongs to EQ only in January and to FI in February and March;
        B remains in BOND. The test compares every public attribution field from a
        headerless CSV with the corresponding positional Polars input, proving that
        ppar performs only container translation and delegates temporal assignment and
        financial calculation to ``perfattr``.
        """
        analytics = Analytics(
            _monthly_performance(),
            _monthly_performance(),
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )
        classification = _pairs(
            {"BOND": "Bonds", "EQ": "Equity", "FI": "Fixed Income"}
        )
        mapping = _effective_mapping()

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "effective_mapping.csv"
            mapping.write_csv(path, include_header=False)
            polars_result = analytics.attribution(
                "Sector",
                classification,
                (mapping, mapping),
            ).to_polars(View.SUBPERIOD_ATTRIBUTION)
            csv_result = analytics.attribution(
                "Sector",
                classification,
                (path, path),
            ).to_polars(View.SUBPERIOD_ATTRIBUTION)

        self.assertTrue(polars_result.equals(csv_result))
        self.assertEqual(
            polars_result.select(
                cols.THRU_DATE,
                cols.CLASSIFICATION_IDENTIFIER,
            ).rows(),
            [
                (dt.date(2024, 1, 31), "BOND"),
                (dt.date(2024, 1, 31), "EQ"),
                (dt.date(2024, 2, 29), "BOND"),
                (dt.date(2024, 2, 29), "FI"),
                (dt.date(2024, 3, 31), "BOND"),
                (dt.date(2024, 3, 31), "FI"),
            ],
        )

    def test_mapping_polars_source_rejects_unsupported_width(self) -> None:
        """The host adapter should accept only portable two- or four-column forms."""
        analytics = Analytics(
            _narrow_performance(),
            portfolio_classification_name="Security",
        )
        mapping = pl.DataFrame({"one": ["A"], "two": ["EQ"], "three": ["extra"]})

        with self.assertRaisesRegex(PparError, "exactly two or four columns"):
            analytics.attribution(
                "Sector",
                mapping_data_sources=(mapping, mapping),
            )

    def test_zero_net_mapped_group_preserves_contribution_and_effects(self) -> None:
        """Undefined group returns do not erase contribution or attribution effects."""
        portfolio = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1)] * 3,
                cols.THRU_DATE: [dt.date(2024, 1, 31)] * 3,
                cols.IDENTIFIER: ["LONG", "SHORT", "CORE"],
                cols.RETURN: [0.20, 0.10, 0.02],
                cols.WEIGHT: [0.50, -0.50, 1.0],
            }
        )
        benchmark = portfolio.with_columns(
            pl.Series(cols.RETURN, [0.10, 0.04, 0.01])
        )
        mapping = _pairs({"LONG": "HEDGE", "SHORT": "HEDGE", "CORE": "CORE"})
        analytics = Analytics(
            portfolio,
            benchmark,
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )

        attribution = analytics.attribution(
            "Strategy",
            _pairs({"HEDGE": "Hedge", "CORE": "Core"}),
            (mapping, mapping),
        )
        details = attribution.to_polars(View.SUBPERIOD_ATTRIBUTION)
        hedge = details.filter(pl.col(cols.CLASSIFICATION_IDENTIFIER) == "HEDGE")
        summary = attribution.to_polars(View.SUBPERIOD_SUMMARY)
        overall = attribution.to_polars(View.OVERALL_ATTRIBUTION)
        overall_hedge = overall.filter(
            pl.col(cols.CLASSIFICATION_IDENTIFIER) == "HEDGE"
        )

        self.assertAlmostEqual(hedge[cols.PORTFOLIO_WEIGHT].item(), 0.0)
        self.assertAlmostEqual(hedge[cols.BENCHMARK_WEIGHT].item(), 0.0)
        self.assertIsNone(hedge[cols.PORTFOLIO_RETURN].item())
        self.assertIsNone(hedge[cols.BENCHMARK_RETURN].item())
        self.assertIsNone(hedge[cols.ACTIVE_RETURN].item())
        self.assertAlmostEqual(hedge[cols.PORTFOLIO_CONTRIB_SIMPLE].item(), 0.05)
        self.assertAlmostEqual(hedge[cols.BENCHMARK_CONTRIB_SIMPLE].item(), 0.03)
        self.assertAlmostEqual(hedge[cols.ACTIVE_CONTRIB_SIMPLE].item(), 0.02)
        self.assertAlmostEqual(hedge[cols.ALLOCATION_EFFECT_SIMPLE].item(), 0.0)
        self.assertAlmostEqual(hedge[cols.SELECTION_EFFECT_SIMPLE].item(), 0.02)
        self.assertAlmostEqual(hedge[cols.TOTAL_EFFECT_SIMPLE].item(), 0.02)
        self.assertAlmostEqual(
            overall_hedge[cols.ALLOCATION_EFFECT_SMOOTHED].item(), 0.0
        )
        self.assertAlmostEqual(
            overall_hedge[cols.SELECTION_EFFECT_SMOOTHED].item(), 0.02
        )
        self.assertAlmostEqual(
            overall_hedge[cols.TOTAL_EFFECT_SMOOTHED].item(), 0.02
        )
        self.assertIsNone(overall_hedge[cols.PORTFOLIO_RETURN].item())
        self.assertIsNone(overall_hedge[cols.BENCHMARK_RETURN].item())
        self.assertAlmostEqual(
            summary[cols.TOTAL_EFFECT_SIMPLE].item(),
            summary[cols.ACTIVE_RETURN].item(),
        )
        self.assertAlmostEqual(
            overall[-1, cols.TOTAL_EFFECT_SMOOTHED],
            overall[-1, cols.ACTIVE_RETURN],
        )

        self.assertIn("Hedge", attribution.to_html(View.SUBPERIOD_ATTRIBUTION))
        with tempfile.TemporaryDirectory() as temporary:
            csv_path = Path(temporary) / "attribution.csv"
            attribution.write_csv(View.SUBPERIOD_ATTRIBUTION, csv_path)
            self.assertIn("HEDGE", csv_path.read_text(encoding="utf-8"))
        png = attribution.to_chart(Chart.OVERALL_ATTRIBUTION)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_zero_net_portfolio_group_keeps_defined_benchmark_allocation(self) -> None:
        """A defined benchmark group return retains the standard allocation effect."""
        portfolio = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1)] * 3,
                cols.THRU_DATE: [dt.date(2024, 1, 31)] * 3,
                cols.IDENTIFIER: ["LONG", "SHORT", "CORE"],
                cols.RETURN: [0.20, 0.10, 0.02],
                cols.WEIGHT: [0.50, -0.50, 1.0],
            }
        )
        benchmark = portfolio.with_columns(
            pl.Series(cols.RETURN, [0.10, 0.04, 0.00]),
            pl.Series(cols.WEIGHT, [0.60, -0.50, 0.90]),
        )
        mapping = _pairs({"LONG": "HEDGE", "SHORT": "HEDGE", "CORE": "CORE"})
        analytics = Analytics(
            portfolio,
            benchmark,
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )

        details = analytics.attribution(
            "Strategy",
            mapping_data_sources=(mapping, mapping),
        ).to_polars(View.SUBPERIOD_ATTRIBUTION)
        hedge = details.filter(pl.col(cols.CLASSIFICATION_IDENTIFIER) == "HEDGE")

        expected_allocation = -0.10 * (0.40 - 0.04)
        expected_total = 0.01 - (-0.10 * 0.04)
        self.assertIsNone(hedge[cols.PORTFOLIO_RETURN].item())
        self.assertAlmostEqual(hedge[cols.BENCHMARK_RETURN].item(), 0.40)
        self.assertAlmostEqual(
            hedge[cols.ALLOCATION_EFFECT_SIMPLE].item(), expected_allocation
        )
        self.assertAlmostEqual(
            hedge[cols.TOTAL_EFFECT_SIMPLE].item(), expected_total
        )
        self.assertAlmostEqual(
            hedge[cols.SELECTION_EFFECT_SIMPLE].item(),
            expected_total - expected_allocation,
        )

    def test_zero_weight_zero_contribution_mapped_group_has_zero_return(self) -> None:
        """A zero-exposure group with no contribution retains a defined zero return."""
        performance = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1)] * 3,
                cols.THRU_DATE: [dt.date(2024, 1, 31)] * 3,
                cols.IDENTIFIER: ["LONG", "SHORT", "CORE"],
                cols.RETURN: [0.10, 0.10, 0.02],
                cols.WEIGHT: [0.50, -0.50, 1.0],
            }
        )
        mapping = _pairs({"LONG": "HEDGE", "SHORT": "HEDGE", "CORE": "CORE"})
        analytics = Analytics(
            performance,
            performance,
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )

        details = analytics.attribution(
            "Strategy",
            mapping_data_sources=(mapping, mapping),
        ).to_polars(View.SUBPERIOD_ATTRIBUTION)
        hedge = details.filter(pl.col(cols.CLASSIFICATION_IDENTIFIER) == "HEDGE")

        self.assertAlmostEqual(hedge[cols.PORTFOLIO_WEIGHT].item(), 0.0)
        self.assertAlmostEqual(hedge[cols.PORTFOLIO_CONTRIB_SIMPLE].item(), 0.0)
        self.assertAlmostEqual(hedge[cols.PORTFOLIO_RETURN].item(), 0.0)

    def test_near_zero_mapped_weight_is_not_treated_as_exact_zero(self) -> None:
        """A nonzero net exposure keeps its mathematically defined mapped return."""
        epsilon = 1e-12
        performance = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1)] * 3,
                cols.THRU_DATE: [dt.date(2024, 1, 31)] * 3,
                cols.IDENTIFIER: ["LONG", "SHORT", "CORE"],
                cols.RETURN: [0.10, -0.10, 0.0],
                cols.WEIGHT: [0.50 + epsilon, -0.50, 1.0 - epsilon],
            }
        )
        mapping = _pairs({"LONG": "HEDGE", "SHORT": "HEDGE", "CORE": "CORE"})
        analytics = Analytics(
            performance,
            performance,
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )

        details = analytics.attribution(
            "Strategy",
            mapping_data_sources=(mapping, mapping),
        ).to_polars(View.SUBPERIOD_ATTRIBUTION)
        hedge = details.filter(pl.col(cols.CLASSIFICATION_IDENTIFIER) == "HEDGE")

        self.assertNotEqual(hedge[cols.PORTFOLIO_WEIGHT].item(), 0.0)
        self.assertIsNotNone(hedge[cols.PORTFOLIO_RETURN].item())
        self.assertGreater(abs(hedge[cols.PORTFOLIO_RETURN].item()), 1e6)

    def test_attribution_requests_use_current_mapping_source_contents(self) -> None:
        """Each attribution reflects the mapping contents supplied to that call."""
        analytics = Analytics(
            _narrow_performance(),
            _narrow_performance(),
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )
        mapping = _pairs({"A": "TECH", "B": "TECH"})

        first = analytics.attribution(
            "Sector",
            mapping_data_sources=(mapping, mapping),
        )
        mapping[1, "value"] = "FIN"
        second = analytics.attribution(
            "Sector",
            mapping_data_sources=(mapping, mapping),
        )

        self.assertIsNot(first, second)
        self.assertEqual(
            set(
                first.to_polars(View.SUBPERIOD_ATTRIBUTION)[
                    cols.CLASSIFICATION_IDENTIFIER
                ].to_list()
            ),
            {"TECH"},
        )
        self.assertEqual(
            set(
                second.to_polars(View.SUBPERIOD_ATTRIBUTION)[
                    cols.CLASSIFICATION_IDENTIFIER
                ].to_list()
            ),
            {"TECH", "FIN"},
        )

    def test_missing_required_mapping_source_is_rejected(self) -> None:
        """A requested roll-up still requires an actual mapping source."""
        analytics = Analytics(
            _narrow_performance(),
            _narrow_performance(),
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )

        with self.assertRaises(PparError):
            analytics.attribution("Sector", mapping_data_sources=(None, None))


if __name__ == "__main__":
    unittest.main()
