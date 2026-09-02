"""Focused regressions for attribution chart preparation."""

from __future__ import annotations

import datetime as dt
import math
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch
import unittest

import matplotlib
import numpy as np
import polars as pl

from ppar import Analytics
from ppar.attribution import Chart
from ppar import charts
import ppar.schema as cols


_VALUE_COLUMN = cols.TOTAL_EFFECT_SIMPLE
_ROOT = Path(__file__).resolve().parents[1]


def _import_backend(
    *,
    environment_backend: str | None = None,
    programmatic: str | None = None,
) -> str:
    """Import chart rendering in a child process and return its backend."""
    environment = os.environ.copy()
    environment["MPLCONFIGDIR"] = matplotlib.get_configdir()
    if environment_backend is None:
        environment.pop("MPLBACKEND", None)
    else:
        environment["MPLBACKEND"] = environment_backend
    before_import = (
        f"import matplotlib; matplotlib.use({programmatic!r}); "
        if programmatic is not None
        else ""
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            before_import
            + "import ppar.charts; import matplotlib; print(matplotlib.get_backend())",
        ],
        cwd=_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip().lower()


class TestChartBackend(unittest.TestCase):
    """Static rendering defaults to Agg without overriding caller choices."""

    def test_ordinary_chart_import_uses_agg(self) -> None:
        """A caller without a backend selection receives the static backend."""
        self.assertEqual(_import_backend(), "agg")

    def test_explicit_backend_choices_remain_authoritative(self) -> None:
        """Environment and programmatic backend selections remain unchanged."""
        with self.subTest(selection="environment"):
            self.assertEqual(_import_backend(environment_backend="svg"), "svg")
        with self.subTest(selection="programmatic"):
            self.assertEqual(_import_backend(programmatic="svg"), "svg")


class TestChartAccessibility(unittest.TestCase):
    """Chart palettes use explicit, consistently interpretable colors."""

    def test_series_and_sign_colors_use_color_vision_friendly_palette(self) -> None:
        """The Okabe-Ito series and sign colors remain explicit and distinct."""
        # pylint: disable=protected-access
        self.assertEqual(charts._COLORS, ("#0072B2", "#E69F00", "#009E73"))
        self.assertEqual(charts._POSITIVE_COLOR, "#0072B2")
        self.assertEqual(charts._NEGATIVE_COLOR, "#D55E00")
        self.assertEqual(len(set((*charts._COLORS, charts._NEGATIVE_COLOR))), 4)
        # pylint: enable=protected-access

    def test_heatmap_uses_red_for_negative_and_green_for_positive(self) -> None:
        """The annotated heatmap follows the familiar financial sign convention."""
        axis = MagicMock()
        axis.get_yticklabels.return_value = []
        with patch.object(charts.sns, "heatmap", return_value=axis) as render:
            charts.heatmap(
                _heatmap_frame(["Alpha", "Beta", "Alpha", "Beta"]),
                _VALUE_COLUMN,
                ("Portfolio vs Benchmark", "Attribution"),
            )

        cmap = render.call_args.kwargs["cmap"]
        negative = cmap(0.0)
        positive = cmap(1.0)
        self.assertGreater(negative[0], negative[1])
        self.assertGreater(positive[1], positive[0])


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


def _rendered_metric_rows(
    df: pl.DataFrame,
    column_name: str,
) -> dict[str, list[float]]:
    """Capture the labeled matrix passed to Seaborn by the heatmap renderer."""
    axis = MagicMock()
    axis.get_yticklabels.return_value = []
    with patch.object(charts.sns, "heatmap", return_value=axis) as render:
        png = charts.heatmap(
            df,
            column_name,
            ("Portfolio vs Benchmark", "Attribution"),
            columns_to_sort=cols.CLASSIFICATION_NAME,
        )

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    matrix = np.asarray(render.call_args.args[0])
    labels = render.call_args.kwargs["yticklabels"]
    return dict(zip(labels, matrix.tolist(), strict=True))


def _rendered_rows(df: pl.DataFrame) -> dict[str, list[float]]:
    """Capture total-effect rows passed to Seaborn."""
    return _rendered_metric_rows(df, _VALUE_COLUMN)


def _zero_net_attribution():  # type annotation would obscure the public construction
    """Return mapped attribution with one zero-net group and defined contribution."""
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
    classification = pl.DataFrame(
        {"identifier": ["HEDGE", "CORE"], "name": ["Hedge", "Core"]}
    )
    mapping = pl.DataFrame(
        {
            "from": ["LONG", "SHORT", "CORE"],
            "to": ["HEDGE", "HEDGE", "CORE"],
        }
    )
    return Analytics(
        portfolio,
        benchmark,
        portfolio_classification_name="Security",
        benchmark_classification_name="Security",
    ).attribution("Strategy", classification, (mapping, mapping))


def _rendered_attribution_rows(chart: Chart) -> dict[str, list[float]]:
    """Capture one public mapped-attribution heatmap matrix."""
    axis = MagicMock()
    axis.get_yticklabels.return_value = []
    with patch.object(charts.sns, "heatmap", return_value=axis) as render:
        png = _zero_net_attribution().to_chart(
            chart,
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

    def test_zero_net_mapped_contribution_remains_visible(self) -> None:
        """Portfolio contribution is available even when mapped weight nets to zero."""
        rows = _rendered_attribution_rows(Chart.HEATMAP_PORTFOLIO_CONTRIBUTION)

        self.assertIn("Hedge", rows)
        self.assertTrue(math.isclose(rows["Hedge"][0], 0.05, abs_tol=1e-12))

    def test_zero_net_mapped_returns_remain_unavailable(self) -> None:
        """Undefined mapped portfolio and active returns stay masked, not zero."""
        for chart in (
            Chart.HEATMAP_PORTFOLIO_RETURN,
            Chart.HEATMAP_ACTIVE_RETURN,
        ):
            with self.subTest(chart=chart):
                rows = _rendered_attribution_rows(chart)

                self.assertIn("Hedge", rows)
                self.assertTrue(math.isnan(rows["Hedge"][0]))

    def test_missing_portfolio_holding_is_omitted_but_real_zero_is_retained(self) -> None:
        """Portfolio-only heatmaps omit absences without removing observed zeroes."""
        frame = pl.DataFrame(
            {
                cols.THRU_DATE: [dt.date(2024, 1, 31)] * 2,
                cols.CLASSIFICATION_IDENTIFIER: ["A", "B"],
                cols.CLASSIFICATION_NAME: ["Alpha", "Beta"],
                cols.PORTFOLIO_WEIGHT: [1.0, 0.0],
                cols.PORTFOLIO_CONTRIB_SIMPLE: [0.0, 0.0],
                cols.PORTFOLIO_RETURN: [0.0, 0.0],
            }
        )

        for column_name in (
            cols.PORTFOLIO_CONTRIB_SIMPLE,
            cols.PORTFOLIO_RETURN,
        ):
            with self.subTest(column_name=column_name):
                rows = _rendered_metric_rows(frame, column_name)

                self.assertEqual(rows, {"Alpha": [0.0]})

    def test_explicit_null_and_absent_pivot_cell_remain_distinct(self) -> None:
        """Undefined source values stay masked while absent groups receive zero."""
        frame = pl.DataFrame(
            {
                cols.THRU_DATE: [
                    dt.date(2024, 1, 31),
                    dt.date(2024, 2, 29),
                    dt.date(2024, 2, 29),
                ],
                cols.CLASSIFICATION_IDENTIFIER: ["A", "A", "B"],
                cols.CLASSIFICATION_NAME: ["Alpha", "Alpha", "Beta"],
                cols.PORTFOLIO_WEIGHT: [0.0, 0.5, 0.5],
                cols.ACTIVE_RETURN: [None, 0.01, 0.02],
            }
        )

        rows = _rendered_metric_rows(frame, cols.ACTIVE_RETURN)

        self.assertTrue(math.isnan(rows["Alpha"][0]))
        self.assertEqual(rows["Alpha"][1], 0.01)
        self.assertEqual(rows["Beta"], [0.0, 0.02])

    def test_ordinary_heatmap_does_not_annotate_undefined_cell(self) -> None:
        """The ordinary Matplotlib path skips an explicitly undefined value."""
        frame = _heatmap_frame(["Alpha", "Beta", "Alpha", "Beta"]).with_columns(
            pl.when(pl.int_range(pl.len()) == 0)
            .then(None)
            .otherwise(pl.col(_VALUE_COLUMN))
            .alias(_VALUE_COLUMN)
        )
        original_heatmap = charts.sns.heatmap
        rendered_axes = []

        def capture_heatmap(*args, **kwargs):
            axis = original_heatmap(*args, **kwargs)
            rendered_axes.append(axis)
            return axis

        with patch.object(charts.sns, "heatmap", side_effect=capture_heatmap) as render:
            charts.heatmap(frame, _VALUE_COLUMN, ("Title", "Subtitle"))

        annotations = np.asarray(render.call_args.kwargs["annot"])
        self.assertEqual(annotations.shape, (2, 2))
        self.assertEqual(np.count_nonzero(annotations == ""), 1)
        self.assertTrue(all(value.endswith("%") for value in annotations.flat if value))
        self.assertEqual(len(rendered_axes), 1)
        self.assertEqual(len(rendered_axes[0].texts), frame.height - 1)

    def test_heatmap_percentage_annotations_normalize_negative_zero(self) -> None:
        """Heatmap labels use percentages without displaying negative zero."""
        frame = _heatmap_frame(["Alpha", "Beta", "Alpha", "Beta"]).with_columns(
            pl.when(pl.int_range(pl.len()) == 0)
            .then(pl.lit(-0.000001))
            .otherwise(pl.col(_VALUE_COLUMN))
            .alias(_VALUE_COLUMN)
        )
        axis = MagicMock()
        axis.get_yticklabels.return_value = []

        with patch.object(charts.sns, "heatmap", return_value=axis) as render:
            charts.heatmap(frame, _VALUE_COLUMN, ("Title", "Subtitle"))

        annotations = np.asarray(render.call_args.kwargs["annot"])
        self.assertIn("0.00%", annotations)
        self.assertNotIn("-0.00%", annotations)

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
        """Large matrices annotate every defined cell without text artists."""
        dates = [dt.date(2024, 1, 1) + dt.timedelta(days=offset) for offset in range(51)]
        identifiers = [f"ID{index:02d}" for index in range(11)]
        rows = [(date, identifier) for date in dates for identifier in identifiers]
        frame = pl.DataFrame(
            {
                cols.THRU_DATE: [date for date, _ in rows],
                cols.CLASSIFICATION_IDENTIFIER: [identifier for _, identifier in rows],
                cols.CLASSIFICATION_NAME: [identifier for _, identifier in rows],
                cols.PORTFOLIO_WEIGHT: [1.0 / len(identifiers)] * len(rows),
                _VALUE_COLUMN: [
                    None if index == 17 else index / 10_000
                    for index in range(len(rows))
                ],
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
        self.assertEqual(np.isnan(np.asarray(render.call_args.args[0])).sum(), 1)
        self.assertEqual(len(drawings), 1)
        self.assertEqual(drawings[0].text.call_count, len(rows) - 1)
        rendered_text = [call.args[1] for call in drawings[0].text.call_args_list]
        self.assertTrue(all(value.endswith("%") for value in rendered_text))

    def test_percentage_tick_precision_distinguishes_small_intervals(self) -> None:
        """Adaptive chart labels preserve meaningful differences on tight axes."""
        tick_values = [0.000001, 0.00000104, 0.00000108]

        precision = charts._percentage_tick_precision(  # pylint: disable=protected-access
            tick_values
        )
        labels = [
            charts._format_percentage(  # pylint: disable=protected-access
                value,
                precision,
            )
            for value in tick_values
        ]

        self.assertGreater(precision, 2)
        self.assertEqual(len(set(labels)), len(labels))


if __name__ == "__main__":
    unittest.main()
