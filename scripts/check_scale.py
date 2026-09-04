"""Run ppar's large-site, selected-workload, and history scale checks."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Collection, Sequence
import datetime as dt
from pathlib import Path
import re
import runpy
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from typing import cast

import polars as pl
from polars.testing import assert_frame_equal
from perfattr.frequency import (
    _frequency_bucket,
    _frequency_bucket_effective_end,
)

from ppar import Analytics
from ppar.attribution import Attribution, View
from ppar.axys_apx import AxysData
from ppar.frequency import Frequency, load_holidays
import ppar.schema as cols


_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE = _ROOT / "src" / "ppar" / "templates" / "axys_apx"
_DEMO_GLOBALS = runpy.run_path(str(_TEMPLATE / "ppar_demo.py"))
_AXYS_SOURCE_VALUES = cast(
    dict[str, object],
    _DEMO_GLOBALS["AXYS_SOURCE_VALUES"],
)
_DEMO_FROM_DATE = cast(dt.date, _DEMO_GLOBALS["FROM_DATE"])
_ALLOWED_SCALES = (*range(10, 101, 10), 500)
_SELECTED_SCALE = 10
_HISTORY_SCALE = 5
_EXPECTED_HISTORY_SOURCE_PERIODS = 300
_EXPECTED_HISTORY_REPORTING_PERIODS = 99
_EXPECTED_HISTORY_REPORTING_END = dt.date(2046, 3, 30)
_DIAGNOSTIC_STARTUP_SAMPLES = 3
_TIMEOUT_GRACE_SECONDS = 5.0
_SCALING_WARNING_MULTIPLIER = 1.05
_SCALING_FAILURE_MULTIPLIER = 1.10


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse the scale multiplier, including the required 500x release gate."""
    parser = argparse.ArgumentParser(description="Run ppar scale checks.")
    parser.add_argument("--scale", type=int, choices=_ALLOWED_SCALES, default=10)
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Print observation-only timing components without changing gate policy.",
    )
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


def _run_elapsed_samples(
    command: Sequence[str | Path],
    *,
    sample_count: int = _DIAGNOSTIC_STARTUP_SAMPLES,
    timeout_seconds: float = 60.0,
) -> tuple[float, ...]:
    """Return command timings in execution order."""
    if sample_count < 1:
        raise ValueError("Timing sample count must be positive.")
    return tuple(
        _run(command, timeout_seconds=timeout_seconds) for _ in range(sample_count)
    )


def _sublinear_scaling_result(
    scenario: str,
    factor: int,
    baseline_elapsed: float,
    scaled_elapsed: float,
) -> tuple[str, float, float, float]:
    """Apply the established long-history warning and failure boundaries."""
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
            f"ratio={ratio:.3f}x."
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


def _monthly_history_periods(
    first_from_date: dt.date,
    count: int,
    holidays: Collection[dt.date],
) -> list[tuple[dt.date, dt.date]]:
    """Return consecutive monthly source periods with business-day endpoints.

    Args:
        first_from_date: Inclusive start of the first source period.
        count: Number of monthly source periods to create.
        holidays: Dates treated as nonbusiness days.

    Returns:
        Gapless inclusive periods ending at each month's effective business
        endpoint.

    Raises:
        ValueError: If ``count`` is not positive.
        RuntimeError: If the requested first date falls after its month's
            effective endpoint.
    """
    if count < 1:
        raise ValueError("History period count must be positive.")

    first_bucket = _frequency_bucket(first_from_date, Frequency.MONTHLY)
    from_date = first_from_date
    periods: list[tuple[dt.date, dt.date]] = []
    for offset in range(count):
        thru_date = _frequency_bucket_effective_end(
            first_bucket + offset,
            Frequency.MONTHLY,
            frozenset(holidays),
        )
        if thru_date < from_date:
            raise RuntimeError(
                "History start falls after the first monthly business endpoint."
            )
        periods.append((from_date, thru_date))
        from_date = thru_date + dt.timedelta(days=1)
    return periods


def _expanded_history_frame(
    source: pl.DataFrame,
    scale: int,
    holidays: Collection[dt.date],
) -> pl.DataFrame:
    """Repeat source values across consecutive calendar-month periods.

    Args:
        source: Axys/APX performance rows containing source date strings or
            date values.
        scale: Number of complete source-history value cycles to produce.
        holidays: Dates treated as nonbusiness days.

    Returns:
        Expanded rows whose period keys are gapless and calendar-correct.

    Raises:
        ValueError: If ``scale`` is not positive.
        RuntimeError: If the source period keys do not already follow the
            configured monthly calendar.
    """
    if scale < 1:
        raise ValueError("History scale must be positive.")

    date_expressions = [
        (
            pl.col(column).str.to_date()
            if source.schema[column] == pl.String
            else pl.col(column).cast(pl.Date)
        ).alias(column)
        for column in ("From Date", "Thru Date")
    ]
    dated = source.with_columns(date_expressions)
    source_periods = list(
        dated.select("From Date", "Thru Date")
        .unique()
        .sort("Thru Date")
        .iter_rows()
    )
    generated_periods = _monthly_history_periods(
        source_periods[0][0],
        len(source_periods) * scale,
        holidays,
    )
    if generated_periods[: len(source_periods)] != source_periods:
        raise RuntimeError(
            "Source history does not follow the configured monthly calendar."
        )

    period_indices = pl.DataFrame(
        {
            "From Date": [period[0] for period in source_periods],
            "Thru Date": [period[1] for period in source_periods],
            "_history_period_index": range(len(source_periods)),
        }
    )
    indexed = dated.join(
        period_indices,
        on=["From Date", "Thru Date"],
        how="left",
        validate="m:1",
    )
    copies: list[pl.DataFrame] = []
    for copy_number in range(scale):
        offset = copy_number * len(source_periods)
        replacement_dates = pl.DataFrame(
            {
                "_history_period_index": range(len(source_periods)),
                "From Date": [
                    generated_periods[offset + index][0]
                    for index in range(len(source_periods))
                ],
                "Thru Date": [
                    generated_periods[offset + index][1]
                    for index in range(len(source_periods))
                ],
            }
        )
        copies.append(
            indexed.drop("From Date", "Thru Date")
            .join(
                replacement_dates,
                on="_history_period_index",
                how="left",
                validate="m:1",
            )
            .drop("_history_period_index")
            .select(dated.columns)
        )
    return pl.concat(copies, how="vertical")


def _set_demo_thru_date(demo_path: Path, thru_date: dt.date) -> None:
    """Replace and verify exactly one executable demo ``THRU_DATE`` assignment.

    Args:
        demo_path: Generated demonstration script to update.
        thru_date: Inclusive upper source-date bound for the workload.

    Raises:
        RuntimeError: If exactly one assignment cannot be found or the updated
            script does not expose the requested date.
    """
    pattern = re.compile(
        r"^(THRU_DATE(?:\s*:\s*[^=]+)?\s*=\s*)"
        r"dt\.date\(\s*\d{4}\s*,\s*\d{1,2}\s*,\s*\d{1,2}\s*\)\s*$",
        re.MULTILINE,
    )
    replacement = f"dt.date({thru_date.year}, {thru_date.month}, {thru_date.day})"
    updated, replacement_count = pattern.subn(
        lambda match: f"{match.group(1)}{replacement}",
        demo_path.read_text(encoding="utf-8"),
    )
    if replacement_count != 1:
        raise RuntimeError(
            "History preparation must replace exactly one THRU_DATE assignment; "
            f"found {replacement_count}."
        )
    demo_path.write_text(updated, encoding="utf-8")
    actual = runpy.run_path(str(demo_path)).get("THRU_DATE")
    if actual != thru_date:
        raise RuntimeError(
            f"History demo THRU_DATE is {actual!r}, not {thru_date!r}."
        )


def _copy_template(destination: Path) -> Path:
    """Copy the packaged Axys/APX workspace into a temporary directory."""
    shutil.copytree(_TEMPLATE, destination)
    (destination / "output").mkdir()
    return destination


def _prepare_large_site(
    destination: Path,
    scale: int,
) -> tuple[Path, int]:
    """Create an unselected-portfolio scale workload."""
    site = _copy_template(destination)
    for file_name in ("portperf.csv", "secperf.csv"):
        path = site / "input" / file_name
        _expanded_frame(path, scale).write_csv(path)
    return site, pl.read_csv(site / "input" / "secperf.csv").height


def _prepare_selected(
    destination: Path,
    scale: int,
) -> tuple[Path, int]:
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


def _prepare_history(
    destination: Path,
) -> tuple[Path, int, int]:
    """Create the fivefold, gapless calendar-month history workload."""
    site = _copy_template(destination)
    holidays = load_holidays(site / "input" / "holidays.csv")
    rows = 0
    periods = 0
    history_thru_date: dt.date | None = None
    for file_name in ("portperf.csv", "secperf.csv"):
        path = site / "input" / file_name
        expanded = _expanded_history_frame(
            pl.read_csv(path),
            _HISTORY_SCALE,
            holidays,
        )
        expanded.write_csv(path)
        rows += expanded.height
        if file_name == "portperf.csv":
            portfolio_periods = (
                expanded.filter(pl.col("Portfolio Code") == "MEGA_ALPHA")
                .select("From Date", "Thru Date")
                .unique()
                .sort("Thru Date")
            )
            periods = portfolio_periods.height
            history_thru_date = cast(
                dt.date,
                portfolio_periods["Thru Date"].item(-1),
            )
    if history_thru_date is None:
        raise RuntimeError("History preparation did not produce portfolio periods.")
    _set_demo_thru_date(site / "ppar_demo.py", history_thru_date)
    return site, rows, periods


def _history_reporting_periods(site: Path) -> pl.DataFrame:
    """Calculate the quarterly periods reached by a generated history demo.

    Args:
        site: Prepared Axys/APX demonstration workspace.

    Returns:
        The calculated subperiod date pairs from the demo's classification
        attribution.

    Raises:
        RuntimeError: If the generated script does not expose its expected
            analytics builder.
    """
    demo_globals = runpy.run_path(str(site / "ppar_demo.py"))
    builder_value = demo_globals.get("_build_analytics")
    if not callable(builder_value):
        raise RuntimeError("History demo does not expose _build_analytics().")
    builder = cast(
        Callable[[], tuple[Analytics, Attribution, Attribution]],
        builder_value,
    )
    _, _, classification_attribution = builder()
    return classification_attribution.to_polars(View.SUBPERIOD_SUMMARY).select(
        cols.DATE_COLUMNS
    )


def _selected_tables(
    site: Path,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Calculate security, sector, and risk tables for a scale workspace."""
    source = AxysData(site, _AXYS_SOURCE_VALUES)
    security_portfolio = source.get_portfolio(
        "MEGA_ALPHA", from_date=_DEMO_FROM_DATE
    )
    security_benchmark = source.get_portfolio(
        "MEGA_BENCH", from_date=_DEMO_FROM_DATE
    )
    security_analytics = security_portfolio.to_analytics(
        security_benchmark,
        frequency=Frequency.QUARTERLY,
        holidays=site / "input" / "holidays.csv",
    )
    security = security_analytics.attribution_for(
        source.get_classification_sources_for_pair(
            "Security",
            security_portfolio,
            security_benchmark,
        ),
    ).to_polars(View.OVERALL_ATTRIBUTION)
    sector_portfolio = source.get_portfolio(
        "MEGA_ALPHA", from_date=_DEMO_FROM_DATE
    )
    sector_benchmark = source.get_portfolio(
        "MEGA_BENCH", from_date=_DEMO_FROM_DATE
    )
    sector_analytics = sector_portfolio.to_analytics(
        sector_benchmark,
        frequency=Frequency.QUARTERLY,
        holidays=site / "input" / "holidays.csv",
    )
    return (
        security,
        sector_analytics.attribution_for(
            source.get_classification_sources_for_pair(
                "Economic Sector",
                sector_portfolio,
                sector_benchmark,
            ),
        ).to_polars(View.OVERALL_ATTRIBUTION),
        sector_analytics.risk_statistics().to_polars(),
    )


def _artifact_outputs(directory: Path) -> dict[str, bytes]:
    """Return every generated report file keyed by name."""
    return {
        path.name: path.read_bytes()
        for path in sorted(directory.iterdir())
        if path.is_file()
    }


def _print_result(
    scenario: str,
    factor: int,
    baseline_rows: int,
    scaled_rows: int,
    baseline_elapsed: float,
    scaled_elapsed: float,
    measured_ratio: float,
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
        f"({measured_ratio:.3f}x); "
        f"warning=>{warning_ratio:.2f}x, failure=>{failure_ratio:.2f}x"
    )


def _print_samples(label: str, samples: Sequence[float]) -> None:
    """Print raw samples and their median for timing review."""
    values = ", ".join(f"{sample:.3f}s" for sample in samples)
    print(f"  {label} samples: [{values}]; median={statistics.median(samples):.3f}s")


def _check_large_site(
    workspace: Path,
    scale: int,
    *,
    diagnostics: bool = False,
) -> None:
    """Require one equivalent report run and observe its large-site timing."""
    preparation_started = time.perf_counter()
    baseline, baseline_rows = _prepare_large_site(workspace / "baseline", 1)
    scaled, scaled_rows = _prepare_large_site(workspace / "scaled", scale)
    preparation_elapsed = time.perf_counter() - preparation_started
    baseline_command: list[str | Path] = [sys.executable, baseline / "ppar_demo.py"]
    scaled_command: list[str | Path] = [sys.executable, scaled / "ppar_demo.py"]
    baseline_elapsed = _run(baseline_command)
    scaled_elapsed = _run(scaled_command)
    baseline_artifacts = _artifact_outputs(baseline / "output")
    scaled_artifacts = _artifact_outputs(scaled / "output")
    if baseline_artifacts != scaled_artifacts:
        raise RuntimeError(
            "Scaled Analytics report bundle differs from the 1x baseline."
        )
    measured_ratio = scaled_elapsed / baseline_elapsed
    print(f"PASS Analytics large-site equivalence {scale}x")
    print(
        f"  rows: {baseline_rows:,} -> {scaled_rows:,} "
        f"({scaled_rows / baseline_rows:.2f}x)"
    )
    print(
        f"  time (observation only): {baseline_elapsed:.2f}s -> "
        f"{scaled_elapsed:.2f}s ({measured_ratio:.3f}x); no performance threshold"
    )

    if diagnostics:
        startup_samples = _run_elapsed_samples((sys.executable, "-c", "pass"))
        calculation_started = time.perf_counter()
        _selected_tables(baseline)
        baseline_calculation = time.perf_counter() - calculation_started
        calculation_started = time.perf_counter()
        _selected_tables(scaled)
        scaled_calculation = time.perf_counter() - calculation_started
        print("  observation-only components (not threshold inputs):")
        print(f"    fixture preparation: {preparation_elapsed:.3f}s")
        _print_samples("  Python startup", startup_samples)
        print(
            "    calculation-only: "
            f"{baseline_calculation:.3f}s -> {scaled_calculation:.3f}s"
        )
        print(
            "    report rendering and file writing remain inside the end-to-end "
            "timings above."
        )


def _check_selected(workspace: Path) -> None:
    """Run the unchanged selected-security financial and performance gate."""
    baseline, baseline_rows = _prepare_large_site(
        workspace / "selected_baseline",
        1,
    )
    scaled, scaled_rows = _prepare_selected(
        workspace / "selected_scaled",
        _SELECTED_SCALE,
    )
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
    measured_ratio = scaled_elapsed / baseline_elapsed
    print(f"PASS Analytics selected-workload {_SELECTED_SCALE}x")
    print(
        f"  rows: {baseline_rows:,} -> {scaled_rows:,} "
        f"({scaled_rows / baseline_rows:.2f}x)"
    )
    print(
        f"  time (observation only): {baseline_elapsed:.2f}s -> "
        f"{scaled_elapsed:.2f}s ({measured_ratio:.3f}x); no performance threshold"
    )


def _check_history(workspace: Path) -> None:
    """Run the fivefold reporting-history gate through the public demo script."""
    baseline, baseline_security_rows = _prepare_large_site(
        workspace / "history_baseline", 1
    )
    scaled, scaled_rows, periods = _prepare_history(workspace / "history_scaled")
    if periods != _EXPECTED_HISTORY_SOURCE_PERIODS:
        raise RuntimeError(
            f"Expected {_EXPECTED_HISTORY_SOURCE_PERIODS} history periods, "
            f"found {periods}."
        )
    baseline_elapsed = _run([sys.executable, baseline / "ppar_demo.py"])
    _, _, warning, failure = _sublinear_scaling_result(
        "Analytics long-history", _HISTORY_SCALE, 1.0, 1.0
    )
    scaled_elapsed = _run(
        [sys.executable, scaled / "ppar_demo.py"],
        timeout_seconds=_scaled_timeout(baseline_elapsed, failure),
    )
    artifacts = list((scaled / "output").iterdir())
    if len(artifacts) != 11 or any(path.stat().st_size == 0 for path in artifacts):
        raise RuntimeError("Long-history Analytics artifacts are incomplete.")
    reporting_periods = _history_reporting_periods(scaled)
    if reporting_periods.height != _EXPECTED_HISTORY_REPORTING_PERIODS:
        raise RuntimeError(
            "Long-history Analytics did not reach the expected reporting horizon: "
            f"expected {_EXPECTED_HISTORY_REPORTING_PERIODS} periods, found "
            f"{reporting_periods.height}."
        )
    reporting_start = cast(dt.date, reporting_periods[cols.FROM_DATE].item(0))
    reporting_end = cast(dt.date, reporting_periods[cols.THRU_DATE].item(-1))
    if (
        reporting_start != _DEMO_FROM_DATE
        or reporting_end != _EXPECTED_HISTORY_REPORTING_END
    ):
        raise RuntimeError(
            "Long-history Analytics reporting bounds are incorrect: "
            f"{reporting_start} to {reporting_end}."
        )
    baseline_rows = baseline_security_rows + pl.read_csv(
        baseline / "input" / "portperf.csv"
    ).height
    status, measured_ratio, warning, failure = _sublinear_scaling_result(
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
        measured_ratio,
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
            _check_large_site(
                workspace,
                args.scale,
                diagnostics=args.diagnostics,
            )
            _check_selected(workspace)
            _check_history(workspace)
    except (RuntimeError, subprocess.SubprocessError) as error:
        print(f"Scale checks failed: {error}", file=sys.stderr)
        return 1
    print(f"ppar scale checks passed at {args.scale}x.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
