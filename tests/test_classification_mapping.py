"""Focused in-memory tests for classification inference and mapping behavior."""

import datetime as dt
from pathlib import Path
import tempfile
import unittest

import polars as pl

from ppar import Analytics
from ppar.attribution import Chart, View
from ppar.classification import Classification
import ppar.schema as cols
from ppar.errors import PparError
from ppar.mapping import Mapping
from ppar.performance import Performance


def _named_performance(
    a_name: str = "Alpha",
    b_name: str = "Beta",
    classification_name: str = "Security",
) -> Performance:
    """Return a minimal named performance data set for classification tests."""
    return Performance(
        pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1)] * 2,
                cols.THRU_DATE: [dt.date(2024, 2, 1)] * 2,
                cols.IDENTIFIER: ["A", "B"],
                cols.RETURN: [0.10, -0.05],
                cols.WEIGHT: [0.60, 0.40],
                cols.NAME: [a_name, b_name],
            }
        ),
        classification_name=classification_name,
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


def _pairs(values: dict[str, str]) -> pl.DataFrame:
    """Return a two-column Polars source from a compact test mapping."""
    return pl.DataFrame({"key": list(values), "value": list(values.values())})


class ClassificationTests(unittest.TestCase):
    """Verify classification inference and explicit classification sources."""

    def test_classification_is_inferred_from_named_performances(self) -> None:
        """Matching named inputs provide an inferred classification."""
        portfolio = _named_performance()
        benchmark = _named_performance()

        classification = Classification("", None, (portfolio, benchmark))

        self.assertEqual(classification.name, "Security")
        self.assertEqual(
            classification.df.sort(cols.CLASSIFICATION_IDENTIFIER).to_dict(as_series=False),
            {
                cols.CLASSIFICATION_IDENTIFIER: ["A", "B"],
                cols.CLASSIFICATION_NAME: ["Alpha", "Beta"],
            },
        )

    def test_inferred_classification_rejects_conflicting_names(self) -> None:
        """Portfolio and benchmark cannot assign different names to one identifier."""
        portfolio = _named_performance(a_name="Portfolio Alpha")
        benchmark = _named_performance(a_name="Benchmark Alpha")

        with self.assertRaisesRegex(PparError, "conflicting values.*A"):
            Classification("", None, (portfolio, benchmark))

    def test_inferred_classification_is_empty_when_names_differ(self) -> None:
        """Different input classification names prevent implicit classification."""
        portfolio = _named_performance(classification_name="Security")
        benchmark = _named_performance(classification_name="Holding")

        classification = Classification("", None, (portfolio, benchmark))

        self.assertIsNone(classification.name)
        self.assertEqual(classification.df.columns, list(cols.CLASSIFICATION_COLUMNS))
        self.assertTrue(classification.df.is_empty())

    def test_explicit_classification_accepts_exact_duplicate_pairs(self) -> None:
        """Exact duplicate names collapse deterministically after filtering."""
        source = pl.DataFrame(
            {
                "identifier": ["A", "A", "B", "UNUSED"],
                "name": ["Alpha", "Alpha", "Beta", "Unused"],
            }
        )

        classification = Classification(
            "Security",
            source,
            (_named_performance(), _named_performance()),
        )

        self.assertEqual(
            classification.df.sort(cols.CLASSIFICATION_IDENTIFIER).to_dict(as_series=False),
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
                "identifier": ["A", "A", "B"],
                "name": ["Alpha", "Alternate Alpha", "Beta"],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "classification.csv"
            source.write_csv(path, include_header=False)
            for data_source in (source, source.reverse(), path):
                with self.subTest(source_type=type(data_source).__name__):
                    with self.assertRaisesRegex(PparError, "conflicting values.*A"):
                        Classification(
                            "Security",
                            data_source,
                            (_named_performance(), _named_performance()),
                        )

    def test_classification_dataframe_is_a_defensive_copy(self) -> None:
        """Mutating a returned classification table cannot alter stored metadata."""
        classification = Classification(
            "Security",
            _pairs({"A": "Alpha", "B": "Beta"}),
            (_named_performance(), _named_performance()),
        )
        returned = classification.df
        returned[0, cols.CLASSIFICATION_NAME] = "Changed"

        self.assertEqual(
            classification.df.sort(cols.CLASSIFICATION_IDENTIFIER)[
                cols.CLASSIFICATION_NAME
            ].to_list(),
            ["Alpha", "Beta"],
        )

    def test_one_column_classification_source_is_rejected(self) -> None:
        """Explicit classification sources must supply identifier and name columns."""
        source = pl.DataFrame({"identifier": ["A", "B"]})

        with self.assertRaises(PparError):
            Classification("Security", source, (_named_performance(), _named_performance()))


class MappingTests(unittest.TestCase):
    """Verify the direct mapping contract and mapped attribution result."""

    def test_mapping_rolls_multiple_items_to_same_target(self) -> None:
        """Several source identifiers may roll up to one target identifier."""
        mapping = Mapping(("A", "B"), _pairs({"A": "TECH", "B": "TECH"}))

        self.assertEqual(dict(mapping.to_froms), {"TECH": ["A", "B"]})

    def test_mapping_keeps_unmapped_item_at_its_own_identifier(self) -> None:
        """An unmapped identifier remains a standalone mapped group."""
        mapping = Mapping(("A", "B"), _pairs({"A": "TECH"}))

        self.assertEqual(
            dict(mapping.to_froms),
            {"TECH": ["A"], "B": ["B"]},
        )

    def test_mapping_filters_unused_source_items(self) -> None:
        """Mappings for identifiers outside the source performance are discarded."""
        mapping = Mapping(
            ("A", "B"),
            _pairs({"A": "TECH", "B": "FIN", "C": "OTHER"}),
        )

        self.assertEqual(
            dict(mapping.to_froms),
            {"TECH": ["A"], "FIN": ["B"]},
        )

    def test_mapping_accepts_exact_duplicate_pairs(self) -> None:
        """Exact duplicate mapping rows collapse to one source-to-target pair."""
        mapping = Mapping(
            ("A",),
            pl.DataFrame({"from": ["A", "A"], "to": ["TECH", "TECH"]}),
        )

        self.assertEqual(dict(mapping.to_froms), {"TECH": ["A"]})

    def test_mapping_rejects_conflicts_for_dataframe_and_csv(self) -> None:
        """Conflicting destinations fail identically for Polars and CSV sources."""
        source = pl.DataFrame(
            {"from": ["A", "A"], "to": ["TECH", "HEALTH"]}
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mapping.csv"
            source.write_csv(path, include_header=False)
            for data_source in (source, source.reverse(), path):
                with self.subTest(source_type=type(data_source).__name__):
                    with self.assertRaisesRegex(PparError, "conflicting values.*A"):
                        Mapping(("A",), data_source)

    def test_mapping_rejects_blank_source_and_destination_identities(self) -> None:
        """Mapping identifiers must contain non-whitespace text before filtering."""
        for invalid_value in (None, "", " "):
            for invalid_column in ("from", "to"):
                values = {
                    "from": [invalid_value if invalid_column == "from" else "A"],
                    "to": [invalid_value if invalid_column == "to" else "TECH"],
                }
                source = pl.DataFrame(values)
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "mapping.csv"
                    source.write_csv(path, include_header=False)
                    for data_source in (source, path):
                        with self.subTest(
                            invalid_value=invalid_value,
                            invalid_column=invalid_column,
                            source_type=type(data_source).__name__,
                        ):
                            with self.assertRaises(PparError) as context:
                                Mapping(("A",), data_source)

                            self.assertIn("Mapping data", str(context.exception))
                            self.assertIn(
                                "non-null and nonblank",
                                str(context.exception),
                            )
                            self.assertEqual(
                                context.exception.context.get("field"),
                                cols.FROM_TO_COLUMNS[
                                    0 if invalid_column == "from" else 1
                                ],
                            )

    def test_mapping_trims_surrounding_whitespace(self) -> None:
        """Mapping source and destination identities are normalized consistently."""
        source = pl.DataFrame({"from": [" A "], "to": [" TECH "]})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mapping.csv"
            source.write_csv(path, include_header=False)
            for data_source in (source, path):
                with self.subTest(source_type=type(data_source).__name__):
                    mapping = Mapping(("A",), data_source)

                    self.assertEqual(mapping.to_froms, {"TECH": ["A"]})

    def test_mapping_rejects_conflicts_created_by_trimming(self) -> None:
        """Normalization cannot silently choose between conflicting targets."""
        source = pl.DataFrame(
            {"from": ["A", " A "], "to": ["TECH", "HEALTH"]}
        )

        with self.assertRaisesRegex(PparError, "conflicting values.*A"):
            Mapping(("A",), source)

    def test_classification_trims_surrounding_whitespace(self) -> None:
        """Classification identifiers and display names are normalized together."""
        performance = _named_performance()
        source = pl.DataFrame(
            {"identifier": [" A ", " B "], "name": [" Alpha ", " Beta "]}
        )

        classification = Classification(
            "Security",
            source,
            (performance, performance),
        )

        self.assertEqual(
            classification.df.to_dict(as_series=False),
            {
                cols.CLASSIFICATION_IDENTIFIER: ["A", "B"],
                cols.CLASSIFICATION_NAME: ["Alpha", "Beta"],
            },
        )

    def test_classification_rejects_conflicts_created_by_trimming(self) -> None:
        """Normalized duplicate identifiers cannot retain conflicting names."""
        performance = _named_performance()
        source = pl.DataFrame(
            {"identifier": ["A", " A ", "B"], "name": ["Alpha", "Other", "Beta"]}
        )

        with self.assertRaisesRegex(PparError, "conflicting values.*A"):
            Classification("Security", source, (performance, performance))

    def test_mapping_preserves_internal_identifier_spaces(self) -> None:
        """Mapping identities may contain meaningful internal spaces."""
        mapping = Mapping(
            ("Alpha Holding",),
            pl.DataFrame(
                {
                    "from": ["Alpha Holding"],
                    "to": ["Core Strategy"],
                }
            ),
        )

        self.assertEqual(mapping.to_froms, {"Core Strategy": ["Alpha Holding"]})

    def test_mapping_dictionary_is_a_defensive_copy(self) -> None:
        """Mutating a returned reverse mapping cannot alter stored mappings."""
        mapping = Mapping(("A", "B"), _pairs({"A": "TECH", "B": "TECH"}))
        returned = mapping.to_froms
        returned["TECH"].append("CHANGED")

        self.assertEqual(dict(mapping.to_froms), {"TECH": ["A", "B"]})

    def test_one_column_mapping_source_is_rejected(self) -> None:
        """Mapping sources must supply both from and to identifier columns."""
        with self.assertRaises(PparError):
            Mapping(("A", "B"), pl.DataFrame({"from": ["A", "B"]}))

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
