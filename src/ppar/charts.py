"""Format attribution chart data as PNG images.

This module contains helper functions used by
:class:`ppar.attribution.Attribution` to render cumulative line charts,
heatmaps, horizontal bar charts, and vertical bar charts from Polars DataFrames.
Each public formatter returns PNG image bytes.
"""

# Overrides for pylance.  All of the plt and ax methods are "type partially unknown".
# pyright: reportUnknownMemberType=none

# Python Imports
from collections import Counter
import io
import logging
import math
import os
from pathlib import Path
import tempfile
import textwrap
from typing import cast, Iterable, Protocol, Sequence

# Third-Party Imports
_cache_root = Path(tempfile.gettempdir()) / "ppar_chart_cache"
_cache_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache_root / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_root / "cache"))
logging.getLogger("matplotlib").setLevel(logging.ERROR)
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

from matplotlib import ticker  # noqa: E402  # pylint: disable=wrong-import-position
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties, findfont
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import polars as pl
import seaborn as sns

# Project Imports
import ppar.schema as cols
import ppar.utilities as util

# Reasonable chart sizing constraints, just so they don't get too tiny or huge.
_DEFAULT_FIGSIZE = (14, 6)  # (width, height) in inches. # 16, 7
_MAXIMUM_FIGURE_HEIGHT = 10 * _DEFAULT_FIGSIZE[1]  # in inches
_MAXIMUM_FIGURE_WIDTH = 10 * _DEFAULT_FIGSIZE[0]  # in inches
_MAXIMUM_LABEL_LENGTH = 45  # characters
_MINIMUM_FIGURE_HEIGHT = 0.8 * _DEFAULT_FIGSIZE[1]  # in inches
_MINIMUM_FIGURE_WIDTH = 0.8 * _DEFAULT_FIGSIZE[0]  # in inches
_XTICK_ROTATION = 45  # Rotate the x-axis labels(dates) by 45 degrees for better readability
_LARGE_HEATMAP_CELL_THRESHOLD = 500

# Chart colors
# 0 = portfolio, 1 = benchmark, 2 = active
# 0 = allocation effect, 1 = selection effect, 2 = total effect
_COLORS = ("green", "blue", "orange")


class _HeatmapMesh(Protocol):
    """Describe the Matplotlib mesh methods used by raster annotations."""

    def update_scalarmappable(self) -> None:
        """Update mapped cell colors."""

    def get_array(self) -> np.ndarray:
        """Return the flattened-mask source values."""
        ...

    def get_facecolors(self) -> np.ndarray:
        """Return one RGBA color per heatmap cell."""
        ...


def cumulative_lines(
    df: pl.DataFrame,
    column_names: Iterable[str],
    title_lines: Sequence[str],
    y_axis_label: str,
) -> bytes:
    """Return a cumulative line chart as PNG bytes.

    Args:
        df: Cumulative attribution view data containing
            ``cols.THRU_DATE`` and the requested cumulative value columns.
        column_names: Names of the cumulative columns to plot. The colors are
            assigned by column order.
        title_lines: Main title and subtitle to display above the chart.
        y_axis_label: Label to display on the y-axis.

    Returns:
        PNG image bytes for the rendered Matplotlib chart.
    """
    # Create figure
    fig = plt.figure(figsize=_figsize(_DEFAULT_FIGSIZE))

    # Add axes at position (6% from left, 13% from bottom, 92% wide, 79% tall)
    # ax = fig.add_axes((0.06, 0.13, 0.92, 0.79))
    ax = fig.add_axes((0.06, 0.15, 0.92, 0.75))

    # Set the title lines
    plt.suptitle(f"{title_lines[0]}\n{title_lines[1]}")

    # Set the dates
    dates = df[cols.THRU_DATE]

    # Plot the lines
    for idx, column_name in enumerate(column_names):
        ax.plot(
            dates,
            df[column_name],
            label=cols.short_column_name(column_name),
            color=_COLORS[idx],
        )

    # Set the y-axis labels.
    ax.set_ylabel(y_axis_label)

    # Add horizontal grid line at y == 0
    ax.axhline(0, color="gray", linestyle="--", linewidth=1)

    # Set x-axis labels.
    # This will set the maximum qty of x-ticks to 23.  Once it hits 24, then it will only show a
    # label for every-other date, at 36 every third date, etc.
    use_dates = dates if len(dates) <= 12 else dates[:: len(dates) // 12]
    ax.set_xticks(use_dates)

    # Rotate x-axis labels for better readability
    ax.set_xticklabels(use_dates, rotation=_XTICK_ROTATION, ha="right")

    # Show the legend.
    ax.legend()

    # Return the png.
    return _to_png(fig)


def _figsize(figsize: Sequence[float]) -> tuple[float, float]:
    """Constrain a requested figure size to the supported chart bounds.

    Args:
        figsize: Requested ``(width, height)`` in inches.

    Returns:
        Figure size clipped to the configured minimum and maximum width and
        height.
    """
    return (
        max(min(figsize[0], _MAXIMUM_FIGURE_WIDTH), _MINIMUM_FIGURE_WIDTH),
        max(min(figsize[1], _MAXIMUM_FIGURE_HEIGHT), _MINIMUM_FIGURE_HEIGHT),
    )


def heatmap(
    df: pl.DataFrame,
    column_name: str,
    title_lines: Sequence[str],
    columns_to_sort: str | Sequence[str] | None = None,
    sort_descendings: bool | Sequence[bool] = False,
) -> bytes:
    """Return a heatmap chart as PNG bytes.

    Args:
        df: Subperiod attribution data containing thru dates,
            classification identifiers, classification names, portfolio weights,
            and the requested value column.
        column_name: Name of the metric column to display in the heatmap cells.
        title_lines: Main title and subtitle to display above the chart.
        columns_to_sort: Column name, or sequence of column names, used to
            choose the heatmap row ordering. Only the first value is used when
            a sequence is supplied.
        sort_descendings: Sort direction, or sequence of sort directions,
            corresponding to ``columns_to_sort``. Only the first value is used
            when a sequence is supplied.

    Returns:
        PNG image bytes for the rendered heatmap.
    """
    # If it is a "portfolio-only" heatmap, then get rid of the cells where the portfolio weight is
    # zero.  They are there because the benchmark weight is not 0.0.
    if column_name in (cols.PORTFOLIO_CONTRIB_SIMPLE, cols.PORTFOLIO_RETURN):
        df = df.filter(pl.col(cols.PORTFOLIO_WEIGHT) != 0)

    # Keep each classification on one stable row even if its display name changes or
    # becomes a duplicate later in the reporting period.
    df = _prepare_heatmap_rows(df, column_name)

    # Sorting can only be done on one column name, so if they have passed sequences, then just use
    # the first one.
    column_name_to_sort = (
        None
        if columns_to_sort is None
        else columns_to_sort if isinstance(columns_to_sort, str) else columns_to_sort[0]
    )
    sort_descending = (
        sort_descendings if isinstance(sort_descendings, bool) else sort_descendings[0]
    )

    # The default sort should be on column_name descending.
    if column_name_to_sort is None or not column_name_to_sort.strip():
        column_name_to_sort = column_name
        sort_descending = True

    # The only 2 columns that the heatmap can be sorted on are: cols.Classification_Name and
    # column_name.  Sort on cols.CLASSIFICATION_NAME here, and on column_name below.
    if column_name_to_sort != column_name:
        df = df.sort("classification_label", descending=False)

    # Set the figure width and height
    fig_width = len(set(df["date_label"])) * 0.7
    fig_height = len(set(df["classification_label"])) * 0.4

    # Create the figure
    fig = plt.figure(figsize=_figsize((fig_width, fig_height)))

    # Set the overall figure title.
    plt.suptitle(f"{title_lines[0]}\n{title_lines[1]}")

    heatmap_data = df.pivot(
        on="date_label",
        index="classification_label",
        values=column_name,
        sort_columns=True,
    ).fill_null(0.0)
    date_columns = [
        name for name in heatmap_data.columns if name != "classification_label"
    ]
    if column_name_to_sort == column_name:
        heatmap_data = (
            heatmap_data.with_columns(
                pl.sum_horizontal(date_columns).alias("_row_total")
            )
            .sort("_row_total", descending=sort_descending)
            .drop("_row_total")
        )

    # Create the cmap: 0 = green, 120 = red, 100=saturation, 50=lightness
    cmap = sns.diverging_palette(0, 120, s=100, l=50, as_cmap=True)

    # Thousands of independent Matplotlib text artists dominate long-history
    # rendering. Large heatmaps use the same complete annotations through a
    # batched raster path after the axes have been drawn.
    heatmap_values = heatmap_data.select(date_columns).to_numpy()
    use_large_heatmap_path = heatmap_values.size > _LARGE_HEATMAP_CELL_THRESHOLD

    # Create the heatmap.
    ax = sns.heatmap(
        heatmap_values,
        cmap=cmap,
        center=0,
        annot=not use_large_heatmap_path,
        fmt=".4f",
        linewidths=0.5,
        cbar=False,
        xticklabels=date_columns,
        yticklabels=heatmap_data["classification_label"].to_list(),
    )

    # Cell annotations are entirely inside the axes and do not affect its required
    # margins. Excluding them from tight-layout measurement preserves every rendered
    # value while avoiding thousands of redundant text-bound calculations on long
    # histories.
    for annotation in ax.texts:
        annotation.set_in_layout(False)

    # Remove the axes labels.
    ax.set_xlabel("")
    ax.set_ylabel("")

    # Set the yticklabels to always be horizontal with rotation=0
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)

    # Rotate x-axis labels for better readability
    plt.xticks(rotation=_XTICK_ROTATION, ha="right")

    # tight_layout() is a "best pratice" that does some automatic spacing between subplots
    # rect=[left, bottom, right, top], where (0, 0, 1, 1) means the entire figure.
    # The bottom_margin will allow room for the rotated dates at the bottom.
    # The top_margin will allow room for the suptitle lines.
    bottom_margin = 0.005
    top_margin = 1 - (0.0005 * fig_height)
    fig.tight_layout(rect=(0, bottom_margin, 1, top_margin))

    # Return the png. Ordinary heatmaps retain Matplotlib's standard text
    # artists; only unusually large matrices use the equivalent raster path.
    if use_large_heatmap_path:
        mesh = cast(_HeatmapMesh, ax.collections[0])
        return _large_heatmap_to_png(fig, ax, mesh, heatmap_values, ".4f")
    return _to_png(fig)


def _large_heatmap_to_png(
    fig: Figure,
    ax: Axes,
    mesh: _HeatmapMesh,
    values: np.ndarray,
    fmt: str,
) -> bytes:
    """Serialize a large heatmap with complete batched cell annotations.

    Args:
        fig: Completed Matplotlib heatmap figure.
        ax: Heatmap axes used to transform cell centers into pixels.
        mesh: Colored heatmap cells whose luminance controls text color.
        values: Two-dimensional values to format into the cells.
        fmt: Python numeric format specification for each value.

    Returns:
        PNG image bytes containing every heatmap cell and annotation.
    """
    canvas = FigureCanvasAgg(fig)
    canvas.draw()  # type: ignore[no-untyped-call]
    image = Image.fromarray(
        np.asarray(canvas.buffer_rgba()).copy()  # type: ignore[no-untyped-call]
    )
    drawing = ImageDraw.Draw(image)
    font_properties = FontProperties()
    font = ImageFont.truetype(
        findfont(font_properties),
        round(font_properties.get_size_in_points() * fig.dpi / 72),
    )

    mesh.update_scalarmappable()
    mesh_values = mesh.get_array().flat
    face_colors = mesh.get_facecolors()
    for flat_index, (row, column) in enumerate(np.ndindex(values.shape)):
        if np.ma.is_masked(mesh_values[flat_index]):
            continue
        display_x, display_y = ax.transData.transform((column + 0.5, row + 0.5))
        text_color = (
            (38, 38, 38)
            if _relative_luminance(face_colors[flat_index]) > 0.408
            else "white"
        )
        drawing.text(
            (display_x, image.height - display_y),
            format(float(values[row, column]), fmt),
            font=font,
            fill=text_color,
            anchor="mm",
        )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", dpi=(fig.dpi, fig.dpi))
    png = buffer.getvalue()
    plt.close(fig)
    return png


def _relative_luminance(color: np.ndarray) -> float:
    """Return the relative luminance of one RGBA heatmap color."""
    rgb = np.where(
        color[:3] <= 0.03928,
        color[:3] / 12.92,
        ((color[:3] + 0.055) / 1.055) ** 2.4,
    )
    return float(rgb @ np.array([0.2126, 0.7152, 0.0722]))


def _prepare_heatmap_rows(df: pl.DataFrame, column_name: str) -> pl.DataFrame:
    """Return uniquely keyed heatmap rows with stable display labels.

    Args:
        df: Subperiod attribution rows containing dates, classification
            identifiers, and classification names.
        column_name: Metric column to retain for the heatmap cells.

    Returns:
        Date labels, stable classification labels, and metric values ready for
        an aggregation-free pivot.

    Raises:
        ValueError: If a date contains more than one value for a classification
            identifier or stable display labels cannot be made unique.
    """
    source_keys = df.select(cols.THRU_DATE, cols.CLASSIFICATION_IDENTIFIER)
    if source_keys.is_duplicated().any():
        raise ValueError(
            "Heatmap data must contain one value per date and classification identifier."
        )

    labels_by_identifier = _stable_heatmap_labels(df)
    if len(labels_by_identifier) != len(set(labels_by_identifier.values())):
        raise ValueError("Heatmap classification labels could not be made unique.")

    return (
        df.with_columns(
            pl.col(cols.THRU_DATE)
            .dt.strftime(util.DATE_FORMAT_STRING)
            .alias("date_label"),
            pl.Series(
                "classification_label",
                [
                    labels_by_identifier[str(identifier)]
                    for identifier in df[cols.CLASSIFICATION_IDENTIFIER]
                ],
            ),
        )
        .select("date_label", "classification_label", column_name)
    )


def _stable_heatmap_labels(df: pl.DataFrame) -> dict[str, str]:
    """Return one word-wrapped display label per classification identifier.

    The latest chronological name represents an identifier for the complete
    chart. Any identifier whose name collides with another identifier anywhere
    in the chart is prefixed so an early or late collision cannot merge rows.

    Args:
        df: Heatmap source data containing dates, classification identifiers,
            and classification names.

    Returns:
        Word-wrapped labels keyed by classification identifier.
    """
    latest_names: dict[str, str] = {}
    identifiers_by_name: dict[str, set[str]] = {}
    ordered = df.sort(cols.THRU_DATE)
    for identifier_value, name_value in ordered.select(
        cols.CLASSIFICATION_IDENTIFIER, cols.CLASSIFICATION_NAME
    ).iter_rows():
        identifier = str(identifier_value)
        name = str(name_value)
        latest_names[identifier] = name
        identifiers_by_name.setdefault(name, set()).add(identifier)

    duplicate_name_identifiers = {
        identifier
        for identifiers in identifiers_by_name.values()
        if len(identifiers) > 1
        for identifier in identifiers
    }
    labels = {
        identifier: (
            f"{identifier}: {name}"
            if identifier in duplicate_name_identifiers
            else name
        )
        for identifier, name in latest_names.items()
    }

    # A generated "identifier: name" label could itself equal another display
    # name. Prefix every member of such a collision before the caller proves
    # that all final labels are unique.
    label_counts = Counter(labels.values())
    duplicate_labels = {label for label, count in label_counts.items() if count > 1}
    return {
        identifier: textwrap.fill(
            f"{identifier}: {label}" if label in duplicate_labels else label,
            width=_MAXIMUM_LABEL_LENGTH,
        )
        for identifier, label in labels.items()
    }


def overall_attribution(
    df: pl.DataFrame,
    title_lines: Sequence[str],
) -> bytes:
    """Return an overall attribution chart as PNG bytes.

    Args:
        df: Overall attribution view data containing classification names and
            smoothed attribution effect columns.
        title_lines: Main title and subtitle to display above the chart.

    Returns:
        PNG image bytes for the rendered overall attribution chart.
    """
    # Set the labels, data series names and data series values.
    labels = _word_wrap(df)
    series_names = [cols.short_column_name(col) for col in cols.ATTRIBUTION_COLUMNS_SMOOTHED]
    series_values = [df[col] for col in cols.ATTRIBUTION_COLUMNS_SMOOTHED]

    # Concatenate all series into a single Polars DataFrame column and find min/max.
    combined_series = pl.concat(series_values)
    overall_min = math.floor(cast(float, combined_series.min()) * 100) / 100
    overall_max = math.ceil(cast(float, combined_series.max()) * 100) / 100

    # Get the vertical chart measurements.
    bar_height, _, fig_height = _vertical_chart_measurements(len(labels))

    # _vertical_chart_measurements gives a bar_height for double bars, so make the bar_height
    # larger since this chart only has single bars.
    bar_height = bar_height * 1.75

    # Create the overall figure with 3 subplots and a shared y axis.
    fig, axes = plt.subplots(
        1, 3, figsize=_figsize((_DEFAULT_FIGSIZE[0], fig_height)), sharey=True
    )

    # Get y positions for set_yticks below.
    y_positions = range(len(labels))

    for ax, series_value, title in zip(axes, series_values, series_names):
        # Create the subplot.
        ax.set_title(title)
        colors = ["green" if val >= 0 else "red" for val in series_value]
        ax.barh(labels, series_value, height=bar_height, color=colors)

        # Set the y-axis.
        ax.set_yticks(y_positions)
        ax.set_yticklabels(labels)

        # Set y-limits to decrease the vertical space between the top boundary and the first bar,
        # and also decrease the vertical space between the last bar and the bottom boundary.  The
        # value of 0.5 seems to work best for varying numbers of classification items.
        ax.set_ylim(-0.5, len(labels) - 0.5)

        # Invert the y-axis so the first group will be at the top.
        ax.invert_yaxis()

        # Set the x-axis ticks min/max, and format them to 2 decimals.
        ax.set_xticks(np.linspace(overall_min, overall_max, num=7))
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))

        # Add vertical grid line at x == 0
        ax.axvline(0, color="gray", linestyle="--", linewidth=1)

    # Set the titles
    plt.suptitle(f"{title_lines[0]}\n{title_lines[1]}")

    # Automatically adjust the spacing between subplots.
    # The bottom_margin will allow for a little extra vertical space fot the x-axis labels.
    # The top_margin will allow room for the suptitle lines.
    bottom_margin = 0.01
    top_margin = 1 - (0.0007 * fig_height)
    fig.tight_layout(rect=(0, bottom_margin, 1, top_margin))

    # Return the png.
    return _to_png(fig)


def overall_contribution(
    df: pl.DataFrame,
    title_lines: Sequence[str],
    portfolio_name: str,
    benchmark_name: str,
) -> bytes:
    """Return an overall contribution comparison chart as PNG bytes.

    Args:
        df: Overall attribution view data containing classification names and
            portfolio/benchmark weight, return, and contribution columns.
        title_lines: Main title and subtitle to display above the chart.
        portfolio_name: Portfolio label to use in the chart legend.
        benchmark_name: Benchmark label to use in the chart legend.

    Returns:
        PNG image bytes for the rendered overall contribution chart.
    """
    # Get the series names.
    series_names = ("Weight", "Return", "Contribution")

    # Get the series values in 3 groups of 2:
    #   0 = Weight, 1 = Return, 2 = Contribution
    #     0 = Portfolio, 1 = Benchmark
    series_values = [
        ((df[col[0]], df[col[1]])) for col in cols.PORTFOLIO_BENCHMARK_CONTRIBUTION_COLUMN_PAIRS
    ]

    # Get the labels
    labels = _word_wrap(df)

    # Get the vertival chart measurements.
    bar_height, delta, fig_height = _vertical_chart_measurements(len(labels))

    # Create the overall figure with 3 subplots and a shared y axis.
    fig, axes = plt.subplots(
        1, 3, figsize=_figsize((_DEFAULT_FIGSIZE[0], fig_height)), sharey=True
    )

    # Set the overall figure title.
    plt.suptitle(f"{title_lines[0]}\n{title_lines[1]}")

    # Loop through to create the 3 sub-plots.
    for ax, values, name in zip(axes, series_values, series_names):
        # Set the sub-plot title to be the series name.
        ax.set_title(name)

        # Set the y-axis ticks to be at the group centers.
        ax.set_yticks(np.arange(len(labels)))
        ax.set_yticklabels(labels)

        # Set y-limits to decrease the vertical space between the top boundary and the first bar,
        # and also decrease the vertical space between the last bar and the bottom boundary.  The
        # value of 0.5 seems to work best for varying numbers of classification items.
        ax.set_ylim(-0.5, len(labels) - 0.5)

        # Invert the y-axis so the first group will be at the top.
        ax.invert_yaxis()

        # # Set x-axis ticks to 2 decimals.
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))

        # Add vertical grid line at x == 0
        ax.axvline(0, color="gray", linestyle="--", linewidth=1)

        # Plot the bars.
        for i in range(len(labels)):
            # Plot the green portfolio bar at y = i - delta
            ax.barh(i - delta, values[0][i], height=bar_height, color="green")
            # Plot the blue benchmark bar at y = i + delta
            ax.barh(i + delta, values[1][i], height=bar_height, color="blue")

    # tight_layout() is a "best pratice" that does some automatic spacing between subplots
    # rect=[left, bottom, right, top], where (0, 0, 1, 1) means the entire figure.
    # The bottom_margin will allow room for the legend.
    # The top_margin will allow room for the suptitle lines.
    bottom_margin = 0.07 * _MINIMUM_FIGURE_HEIGHT / fig_height
    top_margin = 1 - (0.0007 * fig_height)
    fig.tight_layout(rect=(0, bottom_margin, 1, top_margin))

    # Create a legend for the portfolio and benchmark.
    portfolio_patch = mpatches.Patch(color="green", label=portfolio_name)
    benchmark_patch = mpatches.Patch(color="blue", label=benchmark_name)
    fig.legend(
        handles=[portfolio_patch, benchmark_patch],
        loc="lower center",
        ncol=2,  # This makes them horizontal instead of vertical.
        fontsize=12,
    )

    # Return the png.
    return _to_png(fig)


def _to_png(fig: Figure) -> bytes:
    """Serialize a Matplotlib figure to PNG bytes and close the figure.

    Args:
        fig: Matplotlib figure to serialize.

    Returns:
        PNG image bytes for ``fig``.
    """
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    png = buf.getvalue()
    plt.close(fig)

    # gc.collect() seems to be necessary with large datasets and when generating multiple figures
    # in a loop.  ChatGPT says: "In a loop generating many figures, calling plt.close(fig) may not
    # immediately free memory."  Seems to be sporadic.  Cannot replicate the problem, so leave it
    # commented for now - JDR 2025-03-26.
    # import gc
    # gc.collect()

    # Return the png
    return png


def vertical_bars(
    df: pl.DataFrame,
    column_names: Sequence[str],
    title_lines: Sequence[str],
    y_axis_label: str,
) -> bytes:
    """Return a vertical grouped bar chart as PNG bytes.

    Args:
        df: Subperiod summary data containing ``cols.THRU_DATE`` and the
            requested metric columns.
        column_names: Metric columns to plot as grouped vertical bars. The
            colors are assigned by column order.
        title_lines: Main title and subtitle to display above the chart.
        y_axis_label: Label to display on the y-axis.

    Returns:
        PNG image bytes for the rendered vertical bar chart.
    """
    # Set the dates
    dates = df[cols.THRU_DATE]

    # Define the bar width
    bar_width = 0.2
    indices = np.arange(len(dates))

    # Adjust the figure width based on the quantity of dates
    fig_width = len(dates) * bar_width * len(column_names)

    # Create figure and axis
    fig, ax = plt.subplots(figsize=_figsize((fig_width, _DEFAULT_FIGSIZE[1])))

    # Set the overall figure title.
    plt.suptitle(f"{title_lines[0]}\n{title_lines[1]}")

    # Plot the bars
    for idx, column_name in enumerate(column_names):
        if idx == 0:
            location = indices - bar_width
        elif idx == 2:
            location = indices + bar_width
        else:  # idx == 1:
            location = indices + 0.0  # + 0.0 just for mypy
        ax.bar(location, df[column_name], width=bar_width, color=_COLORS[idx])

    # Set x-axis labels and formatting.
    # ha="right" will align the rotated dates so they are positioned at the x-axis tick.
    ax.set_xticks(indices)
    ax.set_xticklabels(dates, rotation=_XTICK_ROTATION, ha="right")

    # Set y-axis labels to 2 decimals, and add a horizontal grid line at y == 0
    ax.set_ylabel(y_axis_label)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.2f"))
    ax.axhline(0, color="gray", linestyle="--", linewidth=1)

    # Set x-limits to decrease the horizontal space between the left boundary and the first bar,
    # and also decrease the horizontal space between the last bar and the right boundary.  The
    # value of 0.5 seems to work best for varying numbers of classification items.
    ax.set_xlim(-0.5, len(dates) - 0.5)

    # tight_layout() is a "best pratice" that does some automatic spacing between subplots
    # rect=[left, bottom, right, top], where (0, 0, 1, 1) means the entire figure.
    # The bottom_margin will allow room for the legend at the bottom.
    bottom_margin = 0.06
    fig.tight_layout(rect=(0, bottom_margin, 1, 1))

    # Create a legend for the portfolio and benchmark.
    patches = [
        mpatches.Patch(color=_COLORS[idx], label=cols.short_column_name(column_name))
        for idx, column_name in enumerate(column_names)
    ]
    fig.legend(handles=patches, loc="lower center", ncol=len(patches), fontsize=12)

    # Return the png.
    return _to_png(fig)


def _vertical_chart_measurements(qty_of_y_ticks: int) -> tuple[float, float, float]:
    """Return sizing values for horizontal bar charts.

    Args:
        qty_of_y_ticks: Number of y-axis groups or labels that the chart must
            display.

    Returns:
        Bar height, vertical offset from each group center, and figure height
        in inches.
    """
    # Set the overall figure height (in inches) based on qty_of_y_ticks.
    # The height_factor of 0.4 seems to work the best.  If you decrease it, then the labels
    # can start overlapping, especially when they are word-wrapped to 3 lines.  If you increase it,
    # then you have too much extra space.
    height_factor = 0.4
    fig_height = max(
        _MINIMUM_FIGURE_HEIGHT, min(qty_of_y_ticks * height_factor, _MAXIMUM_FIGURE_HEIGHT)
    )

    # Use a grouped bar approach.  Let the “group index” be on the y-axis.  For each group i,
    # draw two bars:
    #   Portfolio bar at y = i - delta
    #   Benchmark bar at y = i + delta
    # The tick label for group i will be at y = i.
    bar_height = 0.3
    delta = (bar_height / 2) + 0.01  # vertical offset of each bar from the group center

    return bar_height, delta, fig_height


def _word_wrap(df: pl.DataFrame) -> list[str]:
    """Return word-wrapped classification labels for chart axes.

    Duplicate classification names are prefixed with their classification identifiers
    so chart labels remain unique. Labels are wrapped to the configured maximum
    label length.

    Args:
        df: DataFrame containing ``cols.CLASSIFICATION_IDENTIFIER`` and
            ``cols.CLASSIFICATION_NAME``. If ``cols.THRU_DATE`` is present,
            duplicate detection is based on the first thru-date group.

    Returns:
        Word-wrapped classification labels in DataFrame row order.
    """
    # Get the columns.
    thru_dates = df[cols.THRU_DATE] if cols.THRU_DATE in df else pl.Series()
    identifiers = df[cols.CLASSIFICATION_IDENTIFIER]
    names = df[cols.CLASSIFICATION_NAME]

    # Get all duplicate names.
    if 0 < len(thru_dates):
        # If you have thru_dates, then there will be multiple sets of the same classification
        # names, one set for each date.  So only look for duplicates in the first thru_dates.
        names_to_check = df.filter(df[cols.THRU_DATE] == thru_dates[0])[
            cols.CLASSIFICATION_NAME
        ]
    else:
        # There are no thru_dates, so there will only be one set of names.
        names_to_check = names
    duplicate_names = names_to_check.filter(names_to_check.is_duplicated())

    # Make sure that you are retuning back a unique list.  This is necessary for the charts
    # because the axis labels need to be unique.  Also, visually for the user, if there are
    # non-unique axis labels, what are they to make of that?  So prepend the identifier for
    # the duplicates, and then wordwrap at _MAXIMUM_LABEL_LENGTH.
    return [
        textwrap.fill(
            (f"{identifiers[idx]}: {name}" if name in duplicate_names else name),
            width=_MAXIMUM_LABEL_LENGTH,
        )
        for idx, name in enumerate(names)
    ]
