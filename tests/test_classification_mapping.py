"""Focused in-memory tests for classification inference and mapping behavior."""

import datetime as dt
import unittest

import polars as pl

from ppar import Analytics
from ppar.attribution import View
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

    def test_inferred_classification_prefers_portfolio_name_on_overlap(self) -> None:
        """Portfolio names take precedence for identifiers present in both inputs."""
        portfolio = _named_performance(a_name="Portfolio Alpha")
        benchmark = _named_performance(a_name="Benchmark Alpha")

        classification = Classification("", None, (portfolio, benchmark))

        names = dict(
            zip(
                classification.df[cols.CLASSIFICATION_IDENTIFIER].to_list(),
                classification.df[cols.CLASSIFICATION_NAME].to_list(),
            )
        )
        self.assertEqual(names["A"], "Portfolio Alpha")

    def test_inferred_classification_is_empty_when_names_differ(self) -> None:
        """Different input classification names prevent implicit classification."""
        portfolio = _named_performance(classification_name="Security")
        benchmark = _named_performance(classification_name="Holding")

        classification = Classification("", None, (portfolio, benchmark))

        self.assertIsNone(classification.name)
        self.assertEqual(classification.df.columns, list(cols.CLASSIFICATION_COLUMNS))
        self.assertTrue(classification.df.is_empty())

    def test_explicit_classification_filters_and_keeps_last_duplicate(self) -> None:
        """Explicit sources filter unused items and use the last duplicate name."""
        source = pl.DataFrame(
            {
                "identifier": ["A", "A", "B", "UNUSED"],
                "name": ["Old Alpha", "Alpha", "Beta", "Unused"],
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

    def test_one_column_classification_source_raises_error_302(self) -> None:
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

    def test_mapping_duplicate_source_item_uses_last_value(self) -> None:
        """Duplicate mapping rows resolve to the final target value."""
        mapping = Mapping(
            ("A",),
            pl.DataFrame({"from": ["A", "A"], "to": ["TECH", "HEALTH"]}),
        )

        self.assertEqual(dict(mapping.to_froms), {"HEALTH": ["A"]})

    def test_mapping_dictionary_is_a_defensive_copy(self) -> None:
        """Mutating a returned reverse mapping cannot alter stored mappings."""
        mapping = Mapping(("A", "B"), _pairs({"A": "TECH", "B": "TECH"}))
        returned = mapping.to_froms
        returned["TECH"].append("CHANGED")

        self.assertEqual(dict(mapping.to_froms), {"TECH": ["A", "B"]})

    def test_one_column_mapping_source_raises_error_353(self) -> None:
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

    def test_zero_weight_mapped_group_preserves_nonzero_contribution(self) -> None:
        """Offsetting mapped weights do not erase their combined contribution."""
        performance = pl.DataFrame(
            {
                cols.FROM_DATE: [dt.date(2024, 1, 1)] * 3,
                cols.THRU_DATE: [dt.date(2024, 1, 31)] * 3,
                cols.IDENTIFIER: ["LONG", "SHORT", "CORE"],
                cols.RETURN: [0.10, -0.10, 0.0],
                cols.WEIGHT: [0.50, -0.50, 1.0],
            }
        )
        mapping = _pairs({"LONG": "HEDGE", "SHORT": "HEDGE", "CORE": "CORE"})
        analytics = Analytics(
            performance,
            performance.clone(),
            portfolio_classification_name="Security",
            benchmark_classification_name="Security",
        )

        details = analytics.attribution(
            "Strategy",
            _pairs({"HEDGE": "Hedge", "CORE": "Core"}),
            (mapping, mapping),
        ).to_polars(View.SUBPERIOD_ATTRIBUTION)
        hedge = details.filter(pl.col(cols.CLASSIFICATION_IDENTIFIER) == "HEDGE")

        self.assertAlmostEqual(hedge[cols.PORTFOLIO_WEIGHT].item(), 0.0)
        self.assertAlmostEqual(hedge[cols.PORTFOLIO_CONTRIB_SIMPLE].item(), 0.10)
        self.assertAlmostEqual(details[cols.PORTFOLIO_CONTRIB_SIMPLE].sum(), 0.10)

    def test_attribution_cache_distinguishes_mapping_sources(self) -> None:
        """A classification label alone cannot identify a mapped calculation."""
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

    def test_missing_required_mapping_source_raises_error_804(self) -> None:
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
