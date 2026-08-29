"""Run ppar's unchanged large-site, selected-workload, and history scale gates."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

import polars as pl
from polars.testing import assert_frame_equal

from ppar.attribution import View
from ppar.axys_apx import AxysData
from ppar.frequency import Frequency


_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE = _ROOT / "src" / "ppar" / "templates" / "axys_apx"
_ALLOWED_SCALES = (*range(10, 101, 10), 500)
_SELECTED_SCALE = 10
_HISTORY_SCALE = 5
_HISTORY_BLOCK_YEARS = 5
_SAMPLES = 3
_TIMEOUT_GRACE_SECONDS = 5.0
_SCALING_WARNING_MULTIPLIER = 1.05
_SCALING_FAILURE_MULTIPLIER = 1.10
_LARGE_SITE_WARNING_RATIO = 1.05
_LARGE_SITE_FAILURE_RATIO = 1.10


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse the scale multiplier, including the required 500x release gate."""
    parser = argparse.ArgumentParser(description="Run ppar scale checks.")
    parser.add_argument("--scale", type=int, choices=_ALLOWED_SCALES, default=10)
    return parser.parse_args(argv)


def _run(command: Sequence[str | Path], *, timeout_seconds: float = 60.0) -> float:
    """Run one timed command and return elapsed seconds."""
    started = time.perf_counter()
    try:
        subprocess.run(
            [str(part) for part in command],
            cwd=_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "No child-process output.").strip()
        normalized = " ".join(str(part) for part in command)
        raise RuntimeError(f"Command failed: {normalized}\n{detail}") from error
    return time.perf_counter() - started


def _run_median_elapsed(
    command: Sequence[str | Path], *, timeout_seconds: float = 60.0
) -> float:
    """Return the median of three command timings."""
    return statistics.median(
        _run(command, timeout_seconds=timeout_seconds) for _ in range(_SAMPLES)
    )


def _analytics_scaling_result(
    baseline_elapsed: float, scaled_elapsed: float
) -> tuple[str, float]:
    """Apply the established 1.05x warning and 1.10x failure boundaries."""
    if baseline_elapsed <= 0:
        raise ValueError("Analytics baseline time must be greater than zero.")
    ratio = scaled_elapsed / baseline_elapsed
    if ratio > _LARGE_SITE_FAILURE_RATIO:
        raise RuntimeError(
            "Analytics large-site scaling exceeded the 1.10x failure threshold: "
            f"baseline={baseline_elapsed:.2f}s, scaled={scaled_elapsed:.2f}s, "
            f"ratio={ratio:.2f}x."
        )
    return ("WARN" if ratio > _LARGE_SITE_WARNING_RATIO else "PASS", ratio)


def _sublinear_scaling_result(
    scenario: str,
    factor: int,
    baseline_elapsed: float,
    scaled_elapsed: float,
) -> tuple[str, float, float, float]:
    """Apply the established selected-workload and history boundaries."""
    if baseline_elapsed <= 0:
        raise ValueError(f"{scenario} baseline time must be greater than zero.")
    expected_ratio = 1.0 + factor / 10.0
    warning_ratio = expected_ratio * _SCALING_WARNING_MULTIPLIER
    failure_ratio = expected_ratio * _SCALING_FAILURE_MULTIPLIER
    ratio = scaled_elapsed / baseline_elapsed
    if ratio > failure_ratio:
        raise RuntimeError(
            f"{scenario} exceeded the {failure_ratio:.2f}x time-ratio error cap: "
            f"baseline={baseline_elapsed:.2f}s, scaled={scaled_elapsed:.2f}s, "
            f"ratio={ratio:.2f}x."
        )
    return (
        "WARN" if ratio > warning_ratio else "PASS",
        ratio,
        warning_ratio,
        failure_ratio,
    )


def _scaled_timeout(baseline_elapsed: float, failure_ratio: float) -> float:
    """Return process-kill time beyond, but separate from, a performance cap."""
    return baseline_elapsed * failure_ratio + _TIMEOUT_GRACE_SECONDS


def _expanded_frame(source_path: Path, scale: int) -> pl.DataFrame:
    """Copy rows across consistently suffixed portfolio identifiers."""
    source = pl.read_csv(source_path)
    if "Portfolio Code" not in source.columns:
        return source
    copies = [source]
    for copy_number in range(1, scale):
        suffix = f"_SCALE_{copy_number:03d}"
        copies.append(
            source.with_columns(
                (pl.col("Portfolio Code").cast(pl.String) + suffix).alias(
                    "Portfolio Code"
                )
            )
        )
    return pl.concat(copies, how="vertical")


def _expanded_selected_frames(
    performance: pl.DataFrame,
    security_master: pl.DataFrame,
    scale: int,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Scale selected securities while preserving weights and contributions."""
    performance_copies: list[pl.DataFrame] = []
    reference_copies: list[pl.DataFrame] = []
    for copy_number in range(scale):
        suffix = f"_LOAD_{copy_number:02d}"
        performance_copies.append(
            performance.with_columns(
                (pl.col("Security Symbol") + suffix).alias("Security Symbol"),
                (pl.col("Beginning Weight") / scale).alias("Beginning Weight"),
                (pl.col("Contribution") / scale).alias("Contribution"),
            )
        )
        reference_copies.append(
            security_master.with_columns(
                (pl.col("Security Symbol") + suffix).alias("Security Symbol"),
                (pl.col("Security Name") + suffix).alias("Security Name"),
            )
        )
    return (
        pl.concat(performance_copies, how="vertical"),
        pl.concat(reference_copies, how="vertical"),
    )


def _expanded_history_frame(source: pl.DataFrame, scale: int) -> pl.DataFrame:
    """Return chronologically shifted, nonoverlapping performance blocks."""
    dated = source.with_columns(
        pl.col("From Date").str.to_date(),
        pl.col("Thru Date").str.to_date(),
    )
    return pl.concat(
        [
            dated.with_columns(
                pl.col("From Date").dt.offset_by(
                    f"{copy_number * _HISTORY_BLOCK_YEARS}y"
                ),
                pl.col("Thru Date").dt.offset_by(
                    f"{copy_number * _HISTORY_BLOCK_YEARS}y"
                ),
            )
            for copy_number in range(scale)
        ],
        how="vertical",
    )


def _copy_template(destination: Path) -> Path:
    """Copy the packaged Axys/APX workspace into a temporary directory."""
    shutil.copytree(_TEMPLATE, destination)
    (destination / "output").mkdir()
    return destination


def _prepare_large_site(destination: Path, scale: int) -> tuple[Path, int]:
    """Create an unselected-portfolio scale workload."""
    site = _copy_template(destination)
    for file_name in ("portperf.csv", "secperf.csv"):
        path = site / "input" / file_name
        _expanded_frame(path, scale).write_csv(path)
    return site, pl.read_csv(site / "input" / "secperf.csv").height


def _prepare_selected(destination: Path, scale: int) -> tuple[Path, int]:
    """Create a selected-security scale workload."""
    site = _copy_template(destination)
    performance_path = site / "input" / "secperf.csv"
    security_master_path = site / "input" / "secmast.csv"
    performance, security_master = _expanded_selected_frames(
        pl.read_csv(performance_path),
        pl.read_csv(security_master_path),
        scale,
    )
    performance.write_csv(performance_path)
    security_master.write_csv(security_master_path)
    return site, performance.height


def _prepare_history(destination: Path) -> tuple[Path, int, int]:
    """Create the established fivefold, five-year-block history workload."""
    site = _copy_template(destination)
    config_path = site / "ppar.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "thru_date: 2026-05-29", "thru_date: 2046-05-29"
        ),
        encoding="utf-8",
    )
    rows = 0
    periods = 0
    for file_name in ("portperf.csv", "secperf.csv"):
        path = site / "input" / file_name
        expanded = _expanded_history_frame(pl.read_csv(path), _HISTORY_SCALE)
        expanded.write_csv(path)
        rows += expanded.height
        if file_name == "portperf.csv":
            periods = (
                expanded.filter(pl.col("Portfolio Code") == "MEGA_ALPHA")
                .select("From Date", "Thru Date")
                .unique()
                .height
            )
    return site, rows, periods


def _selected_tables(site: Path) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Calculate security, sector, and risk tables for a scale workspace."""
    source = AxysData(site / "ppar.yaml")
    security_portfolio = source.get_portfolio(
        "MEGA_ALPHA", classification_name="Security"
    )
    security_benchmark = source.get_portfolio(
        "MEGA_BENCH", classification_name="Security"
    )
    security_analytics = security_portfolio.to_analytics(
        security_benchmark,
        frequency=Frequency.QUARTERLY,
        holidays=site / "input" / "holidays.csv",
    )
    security = security_analytics.attribution().to_polars(View.OVERALL_ATTRIBUTION)
    sector_portfolio = source.get_portfolio(
        "MEGA_ALPHA", classification_name="Economic Sector"
    )
    sector_benchmark = source.get_portfolio(
        "MEGA_BENCH", classification_name="Economic Sector"
    )
    sector_analytics = sector_portfolio.to_analytics(
        sector_benchmark,
        frequency=Frequency.QUARTERLY,
        holidays=site / "input" / "holidays.csv",
    )
    return (
        security,
        sector_analytics.attribution().to_polars(View.OVERALL_ATTRIBUTION),
        sector_analytics.risk_statistics().to_polars(),
    )


def _html_outputs(directory: Path) -> dict[str, bytes]:
    """Return generated HTML files keyed by name."""
    return {path.name: path.read_bytes() for path in directory.glob("*.html")}


def _print_result(
    scenario: str,
    factor: int,
    baseline_rows: int,
    scaled_rows: int,
    baseline_elapsed: float,
    scaled_elapsed: float,
    status: str,
    warning_ratio: float,
    failure_ratio: float,
) -> None:
    """Print one compact scale result."""
    print(f"{status} {scenario} {factor}x")
    print(
        f"  rows: {baseline_rows:,} -> {scaled_rows:,} "
        f"({scaled_rows / baseline_rows:.2f}x)"
    )
    print(
        f"  time: {baseline_elapsed:.2f}s -> {scaled_elapsed:.2f}s "
        f"({scaled_elapsed / baseline_elapsed:.2f}x); "
        f"warning=>{warning_ratio:.2f}x, failure=>{failure_ratio:.2f}x"
    )


def _check_large_site(workspace: Path, scale: int) -> None:
    """Run the unchanged large-site gate and require identical visible tables."""
    baseline, baseline_rows = _prepare_large_site(workspace / "baseline", 1)
    scaled, scaled_rows = _prepare_large_site(workspace / "scaled", scale)
    baseline_command: list[str | Path] = [
        sys.executable,
        "-m",
        "ppar.cli",
        "run",
        baseline,
    ]
    scaled_command: list[str | Path] = [
        sys.executable,
        "-m",
        "ppar.cli",
        "run",
        scaled,
    ]
    baseline_elapsed = _run_median_elapsed(baseline_command)
    scaled_elapsed = _run_median_elapsed(
        scaled_command,
        timeout_seconds=_scaled_timeout(
            baseline_elapsed, _LARGE_SITE_FAILURE_RATIO
        ),
    )
    if _html_outputs(baseline / "output") != _html_outputs(scaled / "output"):
        raise RuntimeError("Scaled Analytics HTML differs from the 1x baseline.")
    status, _ = _analytics_scaling_result(baseline_elapsed, scaled_elapsed)
    _print_result(
        "Analytics large-site",
        scale,
        baseline_rows,
        scaled_rows,
        baseline_elapsed,
        scaled_elapsed,
        status,
        _LARGE_SITE_WARNING_RATIO,
        _LARGE_SITE_FAILURE_RATIO,
    )


def _check_selected(workspace: Path) -> None:
    """Run the unchanged selected-security financial and performance gate."""
    baseline, baseline_rows = _prepare_large_site(workspace / "selected_baseline", 1)
    scaled, scaled_rows = _prepare_selected(workspace / "selected_scaled", _SELECTED_SCALE)
    started = time.perf_counter()
    baseline_security, baseline_sector, baseline_risk = _selected_tables(baseline)
    baseline_elapsed = time.perf_counter() - started
    started = time.perf_counter()
    scaled_security, scaled_sector, scaled_risk = _selected_tables(scaled)
    scaled_elapsed = time.perf_counter() - started
    expected_security_rows = (
        baseline_security.filter(pl.col("Classification_Identifier").is_not_null()).height
        * _SELECTED_SCALE
    )
    actual_security_rows = scaled_security.filter(
        pl.col("Classification_Identifier").is_not_null()
    ).height
    if actual_security_rows != expected_security_rows:
        raise RuntimeError("Selected Analytics security row count changed.")
    assert_frame_equal(
        baseline_sector, scaled_sector, check_exact=False, rel_tol=1e-12, abs_tol=1e-12
    )
    for risk in (baseline_risk, scaled_risk):
        assert_frame_equal(
            risk,
            risk.with_columns(
                (pl.col("Portfolio") - pl.col("Benchmark")).alias("Difference")
            ),
            check_exact=True,
        )
    assert_frame_equal(
        baseline_risk.drop("Difference"),
        scaled_risk.drop("Difference"),
        check_exact=False,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    status, _, warning, failure = _sublinear_scaling_result(
        "Analytics selected-workload",
        _SELECTED_SCALE,
        baseline_elapsed,
        scaled_elapsed,
    )
    _print_result(
        "Analytics selected-workload",
        _SELECTED_SCALE,
        baseline_rows,
        scaled_rows,
        baseline_elapsed,
        scaled_elapsed,
        status,
        warning,
        failure,
    )


def _check_history(workspace: Path) -> None:
    """Run the unchanged fivefold history gate through the public command."""
    baseline, baseline_security_rows = _prepare_large_site(
        workspace / "history_baseline", 1
    )
    scaled, scaled_rows, periods = _prepare_history(workspace / "history_scaled")
    if periods != 60 * _HISTORY_SCALE:
        raise RuntimeError(f"Expected 300 history periods, found {periods}.")
    baseline_elapsed = _run(
        [sys.executable, "-m", "ppar.cli", "run", baseline]
    )
    _, _, warning, failure = _sublinear_scaling_result(
        "Analytics long-history", _HISTORY_SCALE, 1.0, 1.0
    )
    scaled_elapsed = _run(
        [sys.executable, "-m", "ppar.cli", "run", scaled],
        timeout_seconds=_scaled_timeout(baseline_elapsed, failure),
    )
    artifacts = list((scaled / "output").iterdir())
    if len(artifacts) != 11 or any(path.stat().st_size == 0 for path in artifacts):
        raise RuntimeError("Long-history Analytics artifacts are incomplete.")
    baseline_rows = baseline_security_rows + pl.read_csv(
        baseline / "input" / "portperf.csv"
    ).height
    status, _, warning, failure = _sublinear_scaling_result(
        "Analytics long-history",
        _HISTORY_SCALE,
        baseline_elapsed,
        scaled_elapsed,
    )
    _print_result(
        "Analytics long-history",
        _HISTORY_SCALE,
        baseline_rows,
        scaled_rows,
        baseline_elapsed,
        scaled_elapsed,
        status,
        warning,
        failure,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run all ppar scale scenarios."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        with tempfile.TemporaryDirectory(prefix="ppar_scale_") as directory:
            workspace = Path(directory)
            _check_large_site(workspace, args.scale)
            _check_selected(workspace)
            _check_history(workspace)
    except (RuntimeError, subprocess.SubprocessError) as error:
        print(f"Scale checks failed: {error}", file=sys.stderr)
        return 1
    print(f"ppar scale checks passed at {args.scale}x.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
