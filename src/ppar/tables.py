"""Render lightweight HTML tables without third-party table dependencies."""

# Python Imports
from dataclasses import dataclass
import datetime as dt
import html
import math
from typing import Literal, Sequence, SupportsFloat, SupportsIndex, cast

# Third-Party Imports
import polars as pl

# Project Imports
import ppar.schema as cols
import ppar.utilities as util

_ColumnFormat = Literal["text", "number", "currency", "date"]
_ColumnAlign = Literal["left", "center", "right"]

_DEFAULT_TABLE_CLASS = "ppar_table"
_MISSING_VALUE = "<NA>"


@dataclass(frozen=True)
class ColumnSpec:
    """Describe how one DataFrame column should appear in an HTML table.

    Attributes:
        name: Source DataFrame column name.
        label: Optional display label. If omitted, ``name`` is used.
        format: Value formatter to apply to the column.
        align: Cell alignment for the column.
    """

    name: str
    label: str | None = None
    format: _ColumnFormat = "text"
    align: _ColumnAlign = "right"


@dataclass(frozen=True)
class SpannerSpec:
    """Describe a grouped header spanning one or more adjacent columns.

    Attributes:
        label: Display label for the spanner.
        columns: Ordered column names covered by the spanner.
    """

    label: str
    columns: Sequence[str]


@dataclass(frozen=True)
class HtmlTable:
    """Small HTML table renderer for formatted report tables.

    Attributes:
        df: Source Polars DataFrame.
        columns: Columns to display, in output order.
        title: Optional title displayed above the header rows.
        subtitle: Optional subtitle displayed below the title.
        spanners: Optional grouped column headers.
        group_column: Optional source column used to insert group heading rows.
        stub_column: Optional display column rendered as row-header cells.
        table_class: CSS class used for the table element.
        float_precision: Decimal places for ``number`` columns.
        currency_symbol: Prefix for ``currency`` columns.
        row_format_column: Optional column whose values select row-specific
            formatting overrides.
        row_formats: Optional mapping of row-format values to column formats.
    """

    df: pl.DataFrame
    columns: Sequence[ColumnSpec]
    title: str = ""
    subtitle: str = ""
    spanners: Sequence[SpannerSpec] = ()
    group_column: str | None = None
    stub_column: str | None = None
    table_class: str = _DEFAULT_TABLE_CLASS
    float_precision: int = 4
    currency_symbol: str = "$"
    row_format_column: str | None = None
    row_formats: dict[object, _ColumnFormat] | None = None

    def as_raw_html(self, make_page: bool = True) -> str:
        """Return the table as an HTML string.

        Args:
            make_page: If ``True``, wrap the table in a complete HTML document.

        Returns:
            HTML string containing the rendered table.
        """
        table_html = "\n".join(
            [
                '<div class="ppar_table_container">',
                _style_block(self.table_class),
                f'<table class="{html.escape(self.table_class)}">',
                self._thead_html(),
                self._tbody_html(),
                "</table>",
                "</div>",
            ]
        )
        if not make_page:
            return table_html
        return "\n".join(
            [
                "<!DOCTYPE html>",
                '<html lang="en">',
                "<head>",
                '<meta charset="utf-8"/>',
                "</head>",
                "<body>",
                table_html,
                "</body>",
                "</html>",
            ]
        )

    def _thead_html(self) -> str:
        """Return the table header HTML."""
        col_count = len(self.columns)
        lines = ["<thead>"]
        if self.title:
            lines.append(
                f'  <tr class="ppar_heading"><td colspan="{col_count}" '
                f'class="ppar_title">{_escape(self.title)}</td></tr>'
            )
        if self.subtitle:
            lines.append(
                f'  <tr class="ppar_heading"><td colspan="{col_count}" '
                f'class="ppar_subtitle">{_escape(self.subtitle)}</td></tr>'
            )
        if self.spanners:
            lines.extend(self._spanner_rows_html())
        lines.append('  <tr class="ppar_col_headings">')
        group_start_columns = self._group_start_columns()
        for column in self.columns:
            align_class = _align_class(column.align)
            date_class = " ppar_date_heading" if column.format == "date" else ""
            group_class = (
                " ppar_group_start" if column.name in group_start_columns else ""
            )
            label = column.name if column.label is None else column.label
            lines.append(
                f'    <th class="ppar_col_heading {align_class}{date_class}{group_class}" '
                f'scope="col">'
                f"{_escape(label)}</th>"
            )
        lines.append("  </tr>")
        lines.append("</thead>")
        return "\n".join(lines)

    def _spanner_rows_html(self) -> list[str]:
        """Return a single grouped-header row for configured spanners."""
        lookup: dict[str, SpannerSpec] = {
            column_name: spanner for spanner in self.spanners for column_name in spanner.columns
        }
        group_start_columns = self._group_start_columns()
        lines = ['  <tr class="ppar_spanner_row">']
        idx = 0
        while idx < len(self.columns):
            column_name = self.columns[idx].name
            spanner = lookup.get(column_name)
            if spanner is None or spanner.columns[0] != column_name:
                group_class = (
                    " ppar_group_start" if column_name in group_start_columns else ""
                )
                lines.append(f'    <th class="ppar_spanner_blank{group_class}"></th>')
                idx += 1
                continue
            colspan = len(spanner.columns)
            group_class = " ppar_group_start" if column_name in group_start_columns else ""
            lines.append(
                f'    <th class="ppar_spanner{group_class}" colspan="{colspan}">'
                f"{_escape(spanner.label)}</th>"
            )
            idx += colspan
        lines.append("  </tr>")
        return lines

    def _tbody_html(self) -> str:
        """Return the table body HTML."""
        lines = ['<tbody class="ppar_table_body">']
        current_group: object = object()
        data_row_index = 0
        group_start_columns = self._group_start_columns()
        for row in self.df.to_dicts():
            if self.group_column is not None and row.get(self.group_column) != current_group:
                current_group = row.get(self.group_column)
                lines.append(
                    f'  <tr class="ppar_group_heading_row"><th colspan="{len(self.columns)}" '
                    f'class="ppar_group_heading">{_format_text(current_group)}</th></tr>'
                )
            stripe = " ppar_striped" if data_row_index % 2 == 1 else ""
            row_class = f' class="{stripe.strip()}"' if stripe else ""
            lines.append(f"  <tr{row_class}>")
            for column in self.columns:
                tag = "th" if column.name == self.stub_column else "td"
                scope = ' scope="row"' if tag == "th" else ""
                align_class = _align_class(column.align)
                column_format = self._column_format(row, column)
                value = _format_value(
                    row.get(column.name),
                    column_format,
                    self.float_precision,
                    self.currency_symbol,
                )
                date_class = " ppar_date_value" if column_format == "date" else ""
                group_class = (
                    " ppar_group_start" if column.name in group_start_columns else ""
                )
                lines.append(
                    f'    <{tag}{scope} '
                    f'class="ppar_row {align_class}{date_class}{group_class}{stripe}">'
                    f"{value}</{tag}>"
                )
            lines.append("  </tr>")
            data_row_index += 1
        lines.append("</tbody>")
        return "\n".join(lines)

    def _column_format(self, row: dict[str, object], column: ColumnSpec) -> _ColumnFormat:
        """Return the effective format for a column in one row.

        Args:
            row: Data row whose optional override value selects formatting.
            column: Column specification providing the default format.

        Returns:
            Row-specific format override, when configured; otherwise, the
            column's default format.
        """
        if self.row_format_column is None or self.row_formats is None:
            return column.format
        if column.format != "number":
            return column.format
        return self.row_formats.get(row.get(self.row_format_column), column.format)

    def _group_start_columns(self) -> set[str]:
        """Return column names where a visual column-group boundary starts."""
        if not self.spanners:
            return set()
        first_columns = [
            spanner.columns[0]
            for spanner in self.spanners
            if spanner.columns and spanner.columns[0] in {column.name for column in self.columns}
        ]
        return set(first_columns[1:])


def attribution_html(
    df: pl.DataFrame,
    view_name: str,
    title_lines: Sequence[str],
    classification_label: str | None = None,
) -> str:
    """Return attribution view data as a lightweight HTML document.

    Args:
        df: Attribution view DataFrame.
        view_name: Display name of the attribution view.
        title_lines: Main title and subtitle.
        classification_label: Label to display over classification columns.

    Returns:
        HTML document string for the attribution view.
    """
    return attribution_table(
        df,
        view_name,
        title_lines,
        classification_label,
    ).as_raw_html(make_page=True)


def attribution_table(
    df: pl.DataFrame,
    view_name: str,
    title_lines: Sequence[str],
    classification_label: str | None = None,
) -> HtmlTable:
    """Return attribution view data as a lightweight HTML table object.

    Args:
        df: Attribution view DataFrame.
        view_name: Display name of the attribution view.
        title_lines: Main title and subtitle.
        classification_label: Label to display over classification columns.

    Returns:
        HtmlTable object for the attribution view.
    """
    classification_label = util.normalize_optional_string(
        classification_label,
        "classification_label",
    )
    columns, spanners = _attribution_layout(view_name, classification_label)
    return HtmlTable(
        df=df,
        columns=columns,
        title=title_lines[0],
        subtitle=title_lines[1],
        spanners=spanners,
        stub_column=cols.CLASSIFICATION_NAME if cols.CLASSIFICATION_NAME in df.columns else None,
    )


def riskstatistics_html(
    df: pl.DataFrame,
    title: str,
    subtitle: str,
    currency_symbol: str,
) -> str:
    """Return risk-statistics data as a lightweight HTML document.

    Args:
        df: Risk-statistics DataFrame.
        title: Main table title.
        subtitle: Table subtitle.
        currency_symbol: Currency symbol used for value-at-risk rows.

    Returns:
        HTML document string for the risk-statistics table.
    """
    return riskstatistics_table(df, title, subtitle, currency_symbol).as_raw_html(make_page=True)


def riskstatistics_table(
    df: pl.DataFrame,
    title: str,
    subtitle: str,
    currency_symbol: str,
) -> HtmlTable:
    """Return risk-statistics data as a lightweight HTML table object.

    Args:
        df: Risk-statistics DataFrame.
        title: Main table title.
        subtitle: Table subtitle.
        currency_symbol: Currency symbol used for value-at-risk rows.

    Returns:
        HtmlTable object for the risk-statistics table.
    """
    row_formats: dict[object, _ColumnFormat] = {
        row["column"]: "currency" for row in df.to_dicts() if "Value At Risk" in row["column"]
    }
    return HtmlTable(
        df=df,
        columns=(
            ColumnSpec("column", "", align="left"),
            ColumnSpec("Portfolio", "Portfolio", format="number"),
            ColumnSpec("Benchmark", "Benchmark", format="number"),
            ColumnSpec("Difference", "Difference", format="number"),
        ),
        title=title,
        subtitle=subtitle,
        group_column="Category",
        stub_column="column",
        currency_symbol=currency_symbol,
        row_format_column="column",
        row_formats=row_formats,
    )


def _attribution_layout(
    view_name: str, classification_label: str | None
) -> tuple[tuple[ColumnSpec, ...], Sequence[SpannerSpec]]:
    """Return column and spanner specifications for an attribution view.

    Args:
        view_name: Display name identifying the attribution view layout.
        classification_label: Optional display label for classification columns.

    Returns:
        Tuple containing ordered table columns and grouped header spanners.

    Raises:
        ValueError: If ``view_name`` does not identify a supported attribution
            layout.
    """
    date_columns = (
        ColumnSpec(cols.FROM_DATE, "From", format="date", align="center"),
        ColumnSpec(cols.THRU_DATE, "Thru", format="date", align="center"),
    )
    time_period_spanner = SpannerSpec("Time Period", cols.DATE_COLUMNS)
    classification_columns = (
        ColumnSpec(cols.CLASSIFICATION_IDENTIFIER, "ID", align="left"),
        ColumnSpec(cols.CLASSIFICATION_NAME, "Name", align="left"),
    )
    entity_labels = {
        cols.PORTFOLIO_RETURN: "Portfolio",
        cols.BENCHMARK_RETURN: "Benchmark",
        cols.ACTIVE_RETURN: "Active",
        cols.PORTFOLIO_CONTRIB_SMOOTHED: "Portfolio",
        cols.BENCHMARK_CONTRIB_SMOOTHED: "Benchmark",
        cols.ACTIVE_CONTRIB_SMOOTHED: "Active",
        cols.PORTFOLIO_CONTRIB_SIMPLE: "Portfolio",
        cols.BENCHMARK_CONTRIB_SIMPLE: "Benchmark",
        cols.ACTIVE_CONTRIB_SIMPLE: "Active",
    }
    measure_labels = {
        cols.PORTFOLIO_RETURN: "Return",
        cols.BENCHMARK_RETURN: "Return",
        cols.ACTIVE_RETURN: "Return",
    }

    if view_name == "Cumulative Attribution":
        columns = date_columns + _number_columns(
            cols.VIEW_CUMULATIVE_ATTRIBUTION_COLUMNS, entity_labels
        )
        spanners: Sequence[SpannerSpec] = (
            time_period_spanner,
            SpannerSpec("Returns", cols.RETURN_COLUMNS),
            SpannerSpec("Cumulative Returns", cols.CUMULATIVE_RETURN_COLUMNS),
            SpannerSpec("Contributions", cols.CONTRIBUTION_COLUMNS_SMOOTHED),
            SpannerSpec("Cumulative Contributions", cols.CUMULATIVE_CONTRIBUTION_COLUMNS),
            SpannerSpec("Attribution Effects", cols.ATTRIBUTION_COLUMNS_SMOOTHED),
            SpannerSpec("Cumulative Attribution Effects", cols.CUMULATIVE_ATTRIBUTION_COLUMNS),
        )
        return columns, spanners

    if view_name == "Overall Attribution":
        columns = classification_columns + _number_columns(
            cols.VIEW_OVERALL_ATTRIBUTION_COLUMNS, measure_labels
        )
        spanners = (
            SpannerSpec(
                _display_classification_label(classification_label), cols.CLASSIFICATION_COLUMNS
            ),
            SpannerSpec("Portfolio", cols.PORTFOLIO_COLUMNS_SMOOTHED),
            SpannerSpec("Benchmark", cols.BENCHMARK_COLUMNS_SMOOTHED),
            SpannerSpec("Active", cols.ACTIVE_COLUMNS_SMOOTHED),
            SpannerSpec("Attribution", cols.ATTRIBUTION_COLUMNS_SMOOTHED),
        )
        return columns, spanners

    if view_name == "Sub-Period Attribution":
        columns = (
            date_columns
            + classification_columns
            + _number_columns(cols.VIEW_SUBPERIOD_ATTRIBUTION_COLUMNS, measure_labels)
        )
        spanners = (
            time_period_spanner,
            SpannerSpec(
                _display_classification_label(classification_label), cols.CLASSIFICATION_COLUMNS
            ),
            SpannerSpec("Portfolio", cols.PORTFOLIO_COLUMNS_SIMPLE),
            SpannerSpec("Benchmark", cols.BENCHMARK_COLUMNS_SIMPLE),
            SpannerSpec("Active", cols.ACTIVE_COLUMNS_SIMPLE),
            SpannerSpec("Attribution", cols.ATTRIBUTION_COLUMNS_SIMPLE),
        )
        return columns, spanners

    if view_name == "Sub-Period Summary":
        columns = date_columns + _number_columns(
            cols.VIEW_SUBPERIOD_SUMMARY_COLUMNS, entity_labels
        )
        spanners = (
            time_period_spanner,
            SpannerSpec("Returns", cols.RETURN_COLUMNS),
            SpannerSpec("Contributions", cols.CONTRIBUTION_COLUMNS_SIMPLE),
            SpannerSpec("Attribution Effects", cols.ATTRIBUTION_COLUMNS_SIMPLE),
        )
        return columns, spanners

    raise ValueError(f"Unknown attribution view: {view_name!r}")


def _display_classification_label(classification_label: str | None) -> str:
    """Return the display label for classification spanners."""
    return classification_label or ""


def _number_columns(
    column_names: Sequence[str], labels: dict[str, str] | None = None
) -> tuple[ColumnSpec, ...]:
    """Return numeric column specifications with display labels.

    Args:
        column_names: Source numeric columns to include.
        labels: Optional explicit display-label overrides.

    Returns:
        Ordered numeric column specifications.
    """
    return tuple(
        ColumnSpec(column_name, _column_label(column_name, labels), format="number")
        for column_name in column_names
    )


def _column_label(column_name: str, labels: dict[str, str] | None = None) -> str:
    """Return the display label used by attribution HTML tables.

    Args:
        column_name: Technical source column name.
        labels: Optional explicit display-label overrides.

    Returns:
        Override label when configured; otherwise, a shortened source name.
    """
    if labels is not None and column_name in labels:
        return labels[column_name]
    labels = {
        cols.PORTFOLIO_RETURN: "Portfolio",
        cols.BENCHMARK_RETURN: "Benchmark",
        cols.ACTIVE_RETURN: "Active",
        cols.CUMULATIVE_PORTFOLIO_RETURN: "Portfolio",
        cols.CUMULATIVE_BENCHMARK_RETURN: "Benchmark",
        cols.CUMULATIVE_ACTIVE_RETURN: "Active",
        cols.PORTFOLIO_CONTRIB_SMOOTHED: "Contrib",
        cols.BENCHMARK_CONTRIB_SMOOTHED: "Contrib",
        cols.ACTIVE_CONTRIB_SMOOTHED: "Contrib",
        cols.PORTFOLIO_CONTRIB_SIMPLE: "Contrib",
        cols.BENCHMARK_CONTRIB_SIMPLE: "Contrib",
        cols.ACTIVE_CONTRIB_SIMPLE: "Contrib",
        cols.CUMULATIVE_PORTFOLIO_CONTRIB: "Portfolio",
        cols.CUMULATIVE_BENCHMARK_CONTRIB: "Benchmark",
        cols.CUMULATIVE_ACTIVE_CONTRIB: "Active",
        cols.PORTFOLIO_WEIGHT: "Weight",
        cols.BENCHMARK_WEIGHT: "Weight",
        cols.ACTIVE_WEIGHT: "Weight",
        cols.ALLOCATION_EFFECT_SMOOTHED: "Allocation",
        cols.SELECTION_EFFECT_SMOOTHED: "Selection",
        cols.TOTAL_EFFECT_SMOOTHED: "Total",
        cols.ALLOCATION_EFFECT_SIMPLE: "Allocation",
        cols.SELECTION_EFFECT_SIMPLE: "Selection",
        cols.TOTAL_EFFECT_SIMPLE: "Total",
        cols.CUMULATIVE_ALLOCATION_EFFECT: "Allocation",
        cols.CUMULATIVE_SELECTION_EFFECT: "Selection",
        cols.CUMULATIVE_TOTAL_EFFECT: "Total",
    }
    return labels.get(column_name, cols.short_column_name(column_name))


def _align_class(align: _ColumnAlign) -> str:
    """Return the CSS alignment class for a column alignment."""
    return f"ppar_{align}"


def _escape(value: object) -> str:
    """Return an HTML-escaped string value."""
    return html.escape(str(value), quote=True)


def _format_text(value: object) -> str:
    """Format a value as escaped text, preserving the missing-value marker."""
    if value is None:
        return _MISSING_VALUE
    if isinstance(value, float) and math.isnan(value):
        return _MISSING_VALUE
    return _escape(value)


def _format_value(
    value: object,
    column_format: _ColumnFormat,
    float_precision: int,
    currency_symbol: str,
) -> str:
    """Format one cell value according to its column format.

    Args:
        value: Raw DataFrame cell value.
        column_format: Rendering category selected for the column.
        float_precision: Decimal places to render for numeric values.
        currency_symbol: Prefix to render for currency values.

    Returns:
        HTML-safe formatted cell contents.
    """
    if value is None:
        return _MISSING_VALUE
    if isinstance(value, float) and math.isnan(value):
        return _MISSING_VALUE
    if column_format == "number":
        return _format_number(_as_float(value), float_precision)
    if column_format == "currency":
        return f"{_escape(currency_symbol)}{_format_number(_as_float(value), 0)}"
    if column_format == "date" and isinstance(value, dt.date):
        return _escape(value.isoformat())
    return _escape(value)


def _as_float(value: object) -> float:
    """Return a numeric value as float for numeric table formatting."""
    return float(cast(str | bytes | SupportsFloat | SupportsIndex, value))


def _format_number(value: float, precision: int) -> str:
    """Format a number using tabular-table conventions.

    Args:
        value: Numeric value to format.
        precision: Decimal places to display.

    Returns:
        Thousands-separated numeric text using an HTML minus sign for negative
        values.
    """
    formatted = f"{value:,.{precision}f}"
    return formatted.replace("-", "&minus;", 1) if formatted.startswith("-") else formatted


def _style_block(table_class: str) -> str:
    """Return CSS used by the lightweight HTML renderer.

    Args:
        table_class: CSS class assigned to the table element.

    Returns:
        Style element containing the report-table CSS rules.
    """
    table_selector = f".{html.escape(table_class)}"
    return f"""<style>
.ppar_table_container {{
  padding: 10px 0;
  overflow-x: auto;
  width: auto;
}}
{table_selector} {{
  border-collapse: collapse;
  color: #333333;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  font-size: 16px;
  line-height: normal;
  margin-left: auto;
  margin-right: auto;
  width: auto;
  border-top: 2px solid #A8A8A8;
  border-bottom: 2px solid #A8A8A8;
}}
{table_selector} th,
{table_selector} td {{
  padding: 8px 5px;
  border-top: 1px solid #D3D3D3;
  vertical-align: middle;
}}
{table_selector} .ppar_title {{
  text-align: center;
  font-size: 125%;
  border-top: 0;
}}
{table_selector} .ppar_subtitle {{
  text-align: center;
  font-size: 90%;
  border-top: 0;
  border-bottom: 2px solid #D3D3D3;
}}
{table_selector} .ppar_col_heading,
{table_selector} .ppar_spanner {{
  font-size: 100%;
  font-weight: normal;
  border-bottom: 2px solid #D3D3D3;
}}
{table_selector} .ppar_spanner_blank {{
  border-bottom: 2px solid #D3D3D3;
}}
{table_selector} .ppar_group_heading {{
  text-align: left;
  font-size: 112.5%;
  font-weight: normal;
  padding-top: 14px;
  padding-bottom: 7px;
  border-top: 2px solid #A8A8A8;
  border-bottom: 1px solid #D3D3D3;
  background-color: #FAFAFA;
}}
{table_selector} .ppar_row {{
  font-weight: normal;
}}
{table_selector} .ppar_date_heading {{
  white-space: nowrap;
}}
{table_selector} .ppar_date_value {{
  white-space: nowrap;
}}
{table_selector} .ppar_group_start {{
  border-left: 2px solid #C7C7C7;
}}
{table_selector} .ppar_striped {{
  background-color: #F4F4F4;
}}
{table_selector} .ppar_left {{
  text-align: left;
}}
{table_selector} .ppar_center {{
  text-align: center;
}}
{table_selector} .ppar_right {{
  text-align: right;
  font-variant-numeric: tabular-nums;
}}
</style>"""
