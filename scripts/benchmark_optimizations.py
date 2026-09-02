"""Measure informational baselines for ppar's retained optimization roadmap.

The benchmark separates fixture preparation from timed work, reports every sample
and its median, and verifies deterministic outputs between repeated measurements.
It establishes observations only: no result is a release threshold or test gate.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import os
from pathlib import Path
import runpy
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from typing import cast, TypeVar

import polars as pl
from polars.testing import assert_frame_equal

from ppar import Analytics
from ppar.attribution import Attribution, Chart, View
from ppar.axys_apx import AxysData, AxysPortfolio
from ppar.frequency import Frequency
import ppar.schema as cols

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import check_scale


_ROOT = Path(__file__).resolve().parents[1]
_GENERIC_TEMPLATE = _ROOT / "src" / "ppar" / "templates" / "generic"
_AXYS_TEMPLATE = _ROOT / "src" / "ppar" / "templates" / "axys_apx"
_SCENARIOS = ("startup", "generic", "axys", "history", "monthly", "bulk")
_DEFAULT_SAMPLES = 3
_MONTHLY_SCALE = 20
_BULK_ACCOUNT_SCALE = 20
_Value = TypeVar("_Value")


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse informational benchmark options.

    Args:
        argv: Command-line arguments excluding the executable name.

    Returns:
        Parsed sample count and selected scenarios.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--samples",
        type=int,
        default=_DEFAULT_SAMPLES,
        help="Measured samples per repeatable scenario (default: 3).",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=_SCENARIOS,
        help="Scenario to run; repeat the option to select several (default: all).",
    )
    args = parser.parse_args(argv)
    if args.samples < 1:
        parser.error("--samples must be positive")
    args.scenario = tuple(dict.fromkeys(args.scenario or _SCENARIOS))
    return args


def _elapsed(call: Callable[[], _Value]) -> tuple[float, _Value]:
    """Return elapsed seconds and the callable result."""
    started = time.perf_counter()
    value = call()
    return time.perf_counter() - started, value


def _measured_values(
    call: Callable[[], _Value],
    sample_count: int,
    verify: Callable[[_Value, _Value], None],
) -> tuple[tuple[float, ...], _Value]:
    """Measure repeated calls and verify every result against the first.

    Args:
        call: Operation to measure.
        sample_count: Positive number of measured calls.
        verify: Result-equivalence assertion accepting expected and actual values.

    Returns:
        Individual elapsed samples and the final result.
    """
    if sample_count < 1:
        raise ValueError("Benchmark sample count must be positive.")
    first_elapsed, expected = _elapsed(call)
    samples = [first_elapsed]
    latest = expected
    for _ in range(1, sample_count):
        elapsed, latest = _elapsed(call)
        samples.append(elapsed)
        verify(expected, latest)
    return tuple(samples), latest


def _print_samples(label: str, samples: Sequence[float]) -> None:
    """Print raw samples and their median."""
    values = ", ".join(f"{sample:.3f}s" for sample in samples)
    print(f"  {label}: [{values}]; median={statistics.median(samples):.3f}s")


def _copy_workspace(template: Path, destination: Path) -> Path:
    """Copy a packaged demonstration into a disposable benchmark workspace."""
    shutil.copytree(template, destination)
    (destination / "output").mkdir()
    return destination


def _artifact_snapshot(output: Path) -> dict[str, bytes]:
    """Return complete report bytes keyed by deterministic filename."""
    return {
        path.name: path.read_bytes()
        for path in sorted(output.iterdir())
        if path.is_file()
    }


def _run_command(
    command: Sequence[str | Path],
    *,
    env: dict[str, str] | None = None,
) -> float:
    """Run one successful subprocess and return elapsed seconds."""
    started = time.perf_counter()
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "No child output.").strip()
        raise RuntimeError(f"Benchmark command failed: {detail}")
    return elapsed


def _demo_samples(
    workspace: Path,
    sample_count: int,
    *,
    env: dict[str, str] | None = None,
    warm: bool = True,
) -> tuple[tuple[float, ...], dict[str, bytes]]:
    """Measure a complete demo and require identical report bundles."""
    command = (sys.executable, workspace / "ppar_demo.py")
    if warm:
        _run_command(command, env=env)
    expected = _artifact_snapshot(workspace / "output") if warm else None
    samples: list[float] = []
    latest: dict[str, bytes] = {}
    for _ in range(sample_count):
        samples.append(_run_command(command, env=env))
        latest = _artifact_snapshot(workspace / "output")
        if expected is None:
            expected = latest
        elif latest != expected:
            raise RuntimeError("Repeated demonstration report bundles differ.")
    return tuple(samples), latest


def _demo_state(
    workspace: Path,
) -> tuple[
    Callable[[], tuple[Analytics, Attribution, Attribution]],
    tuple[View, ...],
    tuple[View, ...],
    tuple[Chart, ...],
]:
    """Return the executable demo builder and its selected report enums."""
    state = runpy.run_path(str(workspace / "ppar_demo.py"))
    builder = cast(
        Callable[[], tuple[Analytics, Attribution, Attribution]],
        state["_build_analytics"],
    )
    return (
        builder,
        cast(tuple[View, ...], state["SECURITY_VIEWS"]),
        cast(tuple[View, ...], state["CLASSIFICATION_VIEWS"]),
        cast(tuple[Chart, ...], state["CLASSIFICATION_CHARTS"]),
    )


def _analytics_signature(
    values: tuple[Analytics, Attribution, Attribution],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Return stable financial tables for construction-equivalence checks."""
    analytics, security, classification = values
    return (
        security.to_polars(View.OVERALL_ATTRIBUTION),
        classification.to_polars(View.OVERALL_ATTRIBUTION),
        analytics.risk_statistics().to_polars(),
    )


def _verify_frames(
    expected: tuple[pl.DataFrame, ...],
    actual: tuple[pl.DataFrame, ...],
) -> None:
    """Require established numerical equality across tuples of Polars frames."""
    if len(expected) != len(actual):
        raise RuntimeError("Benchmark result frame counts differ.")
    for expected_frame, actual_frame in zip(expected, actual):
        assert_frame_equal(
            expected_frame,
            actual_frame,
            check_exact=False,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )


def _benchmark_components(workspace: Path, sample_count: int) -> None:
    """Measure calculation, HTML, and PNG stages for one demo workspace."""
    builder, security_views, classification_views, classification_charts = (
        _demo_state(workspace)
    )
    if sample_count < 1:
        raise ValueError("Benchmark sample count must be positive.")
    first_elapsed, latest = _elapsed(builder)
    build_samples = [first_elapsed]
    expected_signature = _analytics_signature(latest)
    for _ in range(1, sample_count):
        elapsed, latest = _elapsed(builder)
        build_samples.append(elapsed)
        signature = _analytics_signature(latest)
        _verify_frames(expected_signature, signature)
    analytics, security, classification = latest

    fresh_analytics = [builder()[0] for _ in range(sample_count)]
    risk_samples: list[float] = []
    expected_risk: pl.DataFrame | None = None
    for value in fresh_analytics:
        elapsed, risk = _elapsed(value.risk_statistics)
        risk_samples.append(elapsed)
        actual_risk = risk.to_polars()
        if expected_risk is None:
            expected_risk = actual_risk
        else:
            _verify_frames((expected_risk,), (actual_risk,))

    risk_statistics = analytics.risk_statistics()

    def html_bundle() -> tuple[str, ...]:
        return (
            *(security.to_html(view) for view in security_views),
            *(classification.to_html(view) for view in classification_views),
            risk_statistics.to_html(),
        )

    html_samples, _ = _measured_values(
        html_bundle,
        sample_count,
        lambda expected, actual: _verify_equal(expected, actual, "HTML outputs"),
    )

    def png_bundle() -> tuple[bytes, ...]:
        return tuple(classification.to_chart(chart) for chart in classification_charts)

    png_bundle()  # Exclude imports, backend initialization, and cache warmup.
    png_samples, _ = _measured_values(
        png_bundle,
        sample_count,
        lambda expected, actual: _verify_equal(expected, actual, "PNG outputs"),
    )

    _print_samples("analytics and attribution construction", build_samples)
    _print_samples("risk-statistics construction", risk_samples)
    _print_samples("HTML serialization", html_samples)
    _print_samples("warm PNG rendering", png_samples)


def _verify_equal(expected: object, actual: object, label: str) -> None:
    """Require ordinary value equality with a contextual benchmark error."""
    if actual != expected:
        raise RuntimeError(f"Repeated {label} differ.")


def _benchmark_demo(
    label: str,
    workspace: Path,
    sample_count: int,
    *,
    include_cold_cache: bool = False,
) -> None:
    """Measure one complete demo and its internal calculation/report stages."""
    print(f"{label}:")
    warm_samples, _ = _demo_samples(workspace, sample_count)
    _print_samples("warm complete process", warm_samples)
    _benchmark_components(workspace, sample_count)
    if include_cold_cache:
        cache_root = workspace.parent / "isolated-chart-cache"
        cache_root.mkdir()
        env = os.environ.copy()
        env["MPLCONFIGDIR"] = str(cache_root / "matplotlib")
        env["XDG_CACHE_HOME"] = str(cache_root / "xdg")
        cold_samples, expected = _demo_samples(
            workspace,
            1,
            env=env,
            warm=False,
        )
        warm_cache_samples, actual = _demo_samples(
            workspace,
            sample_count,
            env=env,
        )
        _verify_equal(expected, actual, "cold- and warm-cache report bundles")
        _print_samples("isolated cold-cache process", cold_samples)
        _print_samples("same isolated cache, subsequent processes", warm_cache_samples)


def _expanded_monthly_frame(path: Path, scale: int) -> pl.DataFrame:
    """Return many unique holdings while retaining every period total."""
    source = pl.read_csv(path, try_parse_dates=True)
    copies = [
        source.with_columns(
            (pl.col(cols.IDENTIFIER) + f"_BENCH_{index:02d}").alias(cols.IDENTIFIER),
            (pl.col(cols.WEIGHT) / scale).alias(cols.WEIGHT),
        )
        for index in range(scale)
    ]
    return pl.concat(copies, how="vertical")


def _monthly_result(
    portfolio: pl.DataFrame,
    benchmark: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Construct already-monthly analytics and return stable public tables."""
    analytics = Analytics(
        portfolio,
        benchmark,
        portfolio_classification_name="Security",
        benchmark_classification_name="Security",
        frequency=Frequency.MONTHLY,
        holidays=_GENERIC_TEMPLATE / "input" / "holidays.csv",
    )
    return (
        analytics.attribution().to_polars(View.OVERALL_ATTRIBUTION),
        analytics.risk_statistics().to_polars(),
    )


def _benchmark_monthly(sample_count: int) -> None:
    """Measure the exact-period consolidation candidate workload."""
    performance = _GENERIC_TEMPLATE / "input" / "performance"
    portfolio = _expanded_monthly_frame(
        performance / "Mega-Cap Alpha Portfolio.csv",
        _MONTHLY_SCALE,
    )
    benchmark = _expanded_monthly_frame(
        performance / "Mega-Cap Benchmark.csv",
        _MONTHLY_SCALE,
    )
    samples, _ = _measured_values(
        lambda: _monthly_result(portfolio, benchmark),
        sample_count,
        _verify_frames,
    )
    print(f"Already-monthly exact-period workload ({portfolio.height:,} rows/source):")
    _print_samples("analytics, attribution, and risk", samples)


def _portfolio_snapshot(
    portfolios: dict[str, AxysPortfolio],
) -> dict[str, tuple[str, pl.DataFrame]]:
    """Return exact public portfolio values for bulk equivalence checks."""
    return {
        code: (portfolio.portfolio_name, portfolio.security_performance)
        for code, portfolio in portfolios.items()
    }


def _verify_portfolios(
    expected: dict[str, tuple[str, pl.DataFrame]],
    actual: dict[str, tuple[str, pl.DataFrame]],
) -> None:
    """Require equal bulk account keys, names, and reconciled performance."""
    if expected.keys() != actual.keys():
        raise RuntimeError("Bulk Axys/APX portfolio-code results differ.")
    for code in expected:
        expected_name, expected_frame = expected[code]
        actual_name, actual_frame = actual[code]
        _verify_equal(expected_name, actual_name, f"portfolio name for {code}")
        assert_frame_equal(expected_frame, actual_frame, check_exact=True)


def _benchmark_bulk(workspace: Path, sample_count: int) -> None:
    """Measure loading many Axys/APX accounts from shared source frames."""
    codes = tuple(
        pl.read_csv(workspace / "input" / "portperf.csv", schema_overrides={
            "Portfolio Code": pl.String,
        })["Portfolio Code"].unique().sort().to_list()
    )

    def load() -> dict[str, tuple[str, pl.DataFrame]]:
        source = AxysData(workspace, check_scale._AXYS_SOURCE_VALUES)
        return _portfolio_snapshot(source.get_portfolios(codes))

    samples, _ = _measured_values(load, sample_count, _verify_portfolios)
    security_rows = pl.read_csv(workspace / "input" / "secperf.csv").height
    print(f"Bulk Axys/APX loading ({len(codes)} accounts, {security_rows:,} rows):")
    _print_samples("source loading and reconciliation", samples)


def _benchmark_startup(sample_count: int) -> None:
    """Measure interpreter startup separately from every product scenario."""
    samples = tuple(
        _run_command((sys.executable, "-c", "pass"))
        for _ in range(sample_count)
    )
    print("Python startup:")
    _print_samples("empty child process", samples)


def main(argv: Sequence[str] | None = None) -> int:
    """Run selected informational optimization benchmarks."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    scenarios = set(cast(tuple[str, ...], args.scenario))
    with tempfile.TemporaryDirectory(prefix="ppar_optimization_benchmark_") as directory:
        workspace = Path(directory)
        if "startup" in scenarios:
            _benchmark_startup(args.samples)
        if "generic" in scenarios:
            generic = _copy_workspace(_GENERIC_TEMPLATE, workspace / "generic")
            _benchmark_demo(
                "Standard generic 11-report bundle",
                generic,
                args.samples,
                include_cold_cache=True,
            )
        if "axys" in scenarios:
            axys = _copy_workspace(_AXYS_TEMPLATE, workspace / "axys")
            _benchmark_demo("Standard Axys/APX 11-report bundle", axys, args.samples)
        if "history" in scenarios:
            history, _, periods = check_scale._prepare_history(workspace / "history")
            print(f"Genuine long-history bundle ({periods} monthly source periods):")
            history_samples, _ = _demo_samples(history, args.samples)
            _print_samples("warm complete process", history_samples)
        if "monthly" in scenarios:
            _benchmark_monthly(args.samples)
        if "bulk" in scenarios:
            bulk, _ = check_scale._prepare_large_site(
                workspace / "bulk",
                _BULK_ACCOUNT_SCALE,
            )
            _benchmark_bulk(bulk, args.samples)
    print("Informational optimization benchmarks completed; no gates were applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
