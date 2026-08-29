"""Execute one complete Analytics workspace and publish its artifacts atomically."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping

import polars as pl

from ppar.attribution import Attribution, Chart, View
from ppar.axys_apx import AxysData
from ppar.config import Settings, settings
from ppar.core import Analytics
from ppar.errors import PparError
from ppar.frequency import Frequency
import ppar.schema as cols
import ppar.utilities as util


@dataclass(frozen=True)
class RunResult:
    """Describe a successfully published workspace run.

    Attributes:
        workspace: Absolute workspace directory.
        output_directory: Fixed published output directory.
        artifacts: Immutable, deterministic artifact paths.
    """

    workspace: Path
    output_directory: Path
    artifacts: tuple[Path, ...]


def run(workspace: util.PathLike = ".") -> RunResult:
    """Run Analytics for a workspace and atomically publish ``output``.

    Args:
        workspace: Directory containing the canonical ``ppar.yaml``.

    Returns:
        Published artifact inventory.

    Raises:
        PparError: If configuration, source loading, calculation, or publication
            fails. A prior published output remains intact on failure.
    """
    resolved = settings(workspace)
    analytics, security, primary = _build_outputs(resolved)
    staging = Path(tempfile.mkdtemp(prefix=".ppar-output-", dir=resolved.workspace))
    try:
        _write_outputs(
            analytics,
            security,
            primary,
            resolved.frequency,
            staging,
        )
        output_directory = resolved.workspace / "output"
        _publish(staging, output_directory)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    artifacts = tuple(sorted(path for path in output_directory.iterdir() if path.is_file()))
    return RunResult(resolved.workspace, output_directory, artifacts)


def _build_outputs(resolved: Settings) -> tuple[Analytics, Attribution, Attribution]:
    """Build Analytics and its two standard attribution views."""
    if resolved.source == "axys_apx":
        return _build_axys(resolved)
    return _build_generic(resolved)


def _build_axys(resolved: Settings) -> tuple[Analytics, Attribution, Attribution]:
    """Build Analytics from Axys/APX exports."""
    assert resolved.portfolio is not None
    assert resolved.benchmark is not None
    source = AxysData(
        resolved.config_path,
        specification_values=resolved.values,
    )
    portfolios = source.get_portfolios(
        (resolved.portfolio, resolved.benchmark),
        from_date=resolved.from_date,
        thru_date=resolved.thru_date,
        classification_name=resolved.classification,
    )
    portfolio = portfolios[resolved.portfolio]
    benchmark = portfolios[resolved.benchmark]
    analytics = portfolio.to_analytics(
        benchmark,
        frequency=resolved.frequency,
        holidays=resolved.holidays,
        annual_minimum_acceptable_return=resolved.annual_minimum_acceptable_return,
        annual_risk_free_rate=resolved.annual_risk_free_rate,
        confidence_level=resolved.confidence_level,
        portfolio_value=(resolved.portfolio_value, resolved.currency_symbol),
    )
    security_classification = pl.concat(
        [
            source.get_classification_sources(
                "Security", portfolio
            ).classification_data_source,
            source.get_classification_sources(
                "Security", benchmark
            ).classification_data_source,
        ],
        how="vertical",
    ).unique(subset=[cols.IDENTIFIER], keep="any")
    return (
        analytics,
        analytics.attribution("Security", security_classification),
        analytics.attribution(),
    )


def _build_generic(resolved: Settings) -> tuple[Analytics, Attribution, Attribution]:
    """Build Analytics from vendor-neutral narrow CSV files."""
    portfolio_path = _file_path(resolved, "portfolio_performance")
    benchmark_path = _file_path(resolved, "benchmark_performance")
    security_path = _file_path(resolved, "security_classification")
    classification_path = _file_path(resolved, "classification")
    mapping_path = _file_path(resolved, "mapping")
    analytics = Analytics(
        portfolio_path,
        benchmark_path,
        portfolio_classification_name="Security",
        benchmark_classification_name="Security",
        from_date=resolved.from_date or dt.date.min,
        thru_date=resolved.thru_date or dt.date.max,
        frequency=resolved.frequency,
        holidays=resolved.holidays,
        annual_minimum_acceptable_return=resolved.annual_minimum_acceptable_return,
        annual_risk_free_rate=resolved.annual_risk_free_rate,
        confidence_level=resolved.confidence_level,
        portfolio_value=(resolved.portfolio_value, resolved.currency_symbol),
    )
    return (
        analytics,
        analytics.attribution("Security", security_path),
        analytics.attribution(
            resolved.classification,
            classification_path,
            (mapping_path, mapping_path),
        ),
    )


def _file_path(resolved: Settings, name: str) -> Path:
    """Return one required workspace-relative generic file path."""
    files = resolved.values.get("files")
    if not isinstance(files, Mapping):
        raise PparError("files must be a mapping.")
    definition = files.get(name)
    if isinstance(definition, Mapping):
        definition = definition.get("path")
    if not isinstance(definition, str) or not definition:
        raise PparError(f"files.{name}.path is required.")
    path = Path(definition).expanduser()
    return path if path.is_absolute() else resolved.workspace / path


def _write_outputs(
    analytics: Analytics,
    security: Attribution,
    primary: Attribution,
    frequency: Frequency,
    output: Path,
) -> None:
    """Write the standard deterministic Analytics artifact set."""
    _write_text(
        output / "security_overall_attribution.html",
        security.to_html(View.OVERALL_ATTRIBUTION),
    )
    for view in (View.CUMULATIVE_ATTRIBUTION, View.OVERALL_ATTRIBUTION):
        _write_text(
            output / f"classification_{view.name.lower()}.html",
            primary.to_html(view),
        )
    for chart in (
        Chart.OVERALL_CONTRIBUTION,
        Chart.OVERALL_ATTRIBUTION,
        Chart.SUBPERIOD_ATTRIBUTION,
        Chart.HEATMAP_ACTIVE_CONTRIBUTION,
        Chart.HEATMAP_ATTRIBUTION,
        Chart.CUMULATIVE_ATTRIBUTION,
        Chart.CUMULATIVE_RETURN,
    ):
        (output / f"classification_{chart.name.lower()}.png").write_bytes(
            primary.to_chart(chart)
        )
    if frequency is not Frequency.AS_OFTEN_AS_POSSIBLE:
        _write_text(output / "risk_statistics.html", analytics.risk_statistics().to_html())


def _write_text(path: Path, value: str) -> None:
    """Write one UTF-8 artifact."""
    path.write_text(value, encoding=util.ENCODING)


def _publish(staging: Path, output: Path) -> None:
    """Replace the complete published output while preserving rollback safety."""
    backup = output.with_name(".ppar-output-backup")
    if backup.exists():
        shutil.rmtree(backup)
    if output.exists():
        os.replace(output, backup)
    try:
        os.replace(staging, output)
    except Exception:
        if backup.exists():
            os.replace(backup, output)
        raise
    shutil.rmtree(backup, ignore_errors=True)
