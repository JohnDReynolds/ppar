"""Focused regressions for attribution chart preparation."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch
import unittest

import numpy as np
import polars as pl

from ppar import charts
import ppar.schema as cols


_VALUE_COLUMN = cols.TOTAL_EFFECT_SIMPLE


def _heatmap_frame(names: list[str]) -> pl.DataFrame:
    """Return two classifications across two heatmap dates."""
    return pl.DataFrame(
        {
            cols.THRU_DATE: [
                dt.date(2024, 1, 31),
                dt.date(2024, 1, 31),
                dt.date(2024, 2, 29),
                dt.date(2024, 2, 29),
            ],
            cols.CLASSIFICATION_IDENTIFIER: ["A", "B", "A", "B"],
            cols.CLASSIFICATION_NAME: names,
            cols.PORTFOLIO_WEIGHT: [0.5, 0.5, 0.5, 0.5],
            _VALUE_COLUMN: [1.0, 2.0, 3.0, 4.0],
        }
    )


def _rendered_rows(df: pl.DataFrame) -> dict[str, list[float]]:
    """Capture the labeled matrix passed to Seaborn by the public renderer."""
    axis = MagicMock()
    axis.get_yticklabels.return_value = []
    with patch.object(charts.sns, "heatmap", return_value=axis) as render:
        png = charts.heatmap(
            df,
            _VALUE_COLUMN,
            ("Portfolio vs Benchmark", "Attribution"),
            columns_to_sort=cols.CLASSIFICATION_NAME,
        )

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    matrix = np.asarray(render.call_args.args[0])
    labels = render.call_args.kwargs["yticklabels"]
    return dict(zip(labels, matrix.tolist(), strict=True))


class TestHeatmapIdentity(unittest.TestCase):
    """Heatmap rows retain classifications independently of display-name changes."""

    def test_later_duplicate_name_keeps_both_identifier_series(self) -> None:
        """A display-name collision after the first date cannot discard values."""
        rows = _rendered_rows(_heatmap_frame(["Shared", "Unique", "Shared", "Shared"]))

        self.assertEqual(rows, {"A: Shared": [1.0, 3.0], "B: Shared": [2.0, 4.0]})

    def test_first_date_duplicate_name_keeps_both_identifier_series(self) -> None:
        """Names duplicated from the outset remain separately identifiable."""
        rows = _rendered_rows(_heatmap_frame(["Shared"] * 4))

        self.assertEqual(rows, {"A: Shared": [1.0, 3.0], "B: Shared": [2.0, 4.0]})

    def test_name_change_uses_one_stable_row_with_latest_name(self) -> None:
        """One identifier's historical name change must not split its values."""
        rows = _rendered_rows(_heatmap_frame(["Old Alpha", "Beta", "New Alpha", "Beta"]))

        self.assertEqual(rows, {"Beta": [2.0, 4.0], "New Alpha": [1.0, 3.0]})

    def test_duplicate_identifier_within_date_is_rejected_before_pivot(self) -> None:
        """The renderer cannot silently aggregate duplicate identifier values."""
        duplicate = _heatmap_frame(["Alpha", "Beta", "Alpha", "Beta"]).with_columns(
            pl.when(pl.int_range(pl.len()) == 1)
            .then(pl.lit("A"))
            .otherwise(pl.col(cols.CLASSIFICATION_IDENTIFIER))
            .alias(cols.CLASSIFICATION_IDENTIFIER)
        )

        with self.assertRaisesRegex(ValueError, "one value per date"):
            charts.heatmap(duplicate, _VALUE_COLUMN, ("Title", "Subtitle"))

    def test_cell_annotations_are_excluded_only_from_layout_measurement(self) -> None:
        """Cell text remains rendered without participating in expensive layout."""
        annotations = [MagicMock(), MagicMock()]
        axis = MagicMock()
        axis.texts = annotations
        axis.get_yticklabels.return_value = []

        with patch.object(charts.sns, "heatmap", return_value=axis):
            charts.heatmap(
                _heatmap_frame(["Alpha", "Beta", "Alpha", "Beta"]),
                _VALUE_COLUMN,
                ("Title", "Subtitle"),
            )

        for annotation in annotations:
            annotation.set_in_layout.assert_called_once_with(False)
            annotation.set_visible.assert_not_called()

    def test_large_heatmap_uses_the_complete_raster_annotation_path(self) -> None:
        """Large matrices retain all cells without constructing text artists."""
        dates = [dt.date(2024, 1, 1) + dt.timedelta(days=offset) for offset in range(51)]
        identifiers = [f"ID{index:02d}" for index in range(11)]
        rows = [(date, identifier) for date in dates for identifier in identifiers]
        frame = pl.DataFrame(
            {
                cols.THRU_DATE: [date for date, _ in rows],
                cols.CLASSIFICATION_IDENTIFIER: [identifier for _, identifier in rows],
                cols.CLASSIFICATION_NAME: [identifier for _, identifier in rows],
                cols.PORTFOLIO_WEIGHT: [1.0 / len(identifiers)] * len(rows),
                _VALUE_COLUMN: [index / 10_000 for index in range(len(rows))],
            }
        )
        original_heatmap = charts.sns.heatmap
        original_drawing = charts.ImageDraw.Draw
        drawings: list[MagicMock] = []

        def capture_drawing(image):
            drawing = MagicMock(wraps=original_drawing(image))
            drawings.append(drawing)
            return drawing

        with (
            patch.object(charts.sns, "heatmap", wraps=original_heatmap) as render,
            patch.object(charts.ImageDraw, "Draw", side_effect=capture_drawing),
        ):
            png = charts.heatmap(frame, _VALUE_COLUMN, ("Title", "Subtitle"))

        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertFalse(render.call_args.kwargs["annot"])
        self.assertEqual(len(drawings), 1)
        self.assertEqual(drawings[0].text.call_count, len(rows))


if __name__ == "__main__":
    unittest.main()
