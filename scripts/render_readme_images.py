"""Regenerate or byte-check every marketing image referenced by README.md."""

from __future__ import annotations

import argparse
import io
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image, ImageChops

from ppar import Analytics
from ppar.attribution import Attribution, Chart, View
from ppar.frequency import Frequency
import ppar.utilities as util


_ROOT = Path(__file__).resolve().parents[1]
_IMAGE_DIRECTORY = _ROOT / "docs" / "images"
_INPUT = _ROOT / "src" / "ppar" / "templates" / "generic" / "input"
_RAW_PREFIX = "https://raw.githubusercontent.com/JohnDReynolds/ppar/main/docs/images/"
_CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chrome",
)
_CHART_FILES = {
    Chart.OVERALL_ATTRIBUTION: "OverallAttributionByEconomicSector.png",
    Chart.OVERALL_CONTRIBUTION: "OverallContributionByEconomicSector.png",
    Chart.SUBPERIOD_ATTRIBUTION: "SubPeriodAttributionEffectsByEconomicSector.png",
    Chart.SUBPERIOD_RETURN: "SubPeriodReturns.png",
    Chart.HEATMAP_ACTIVE_CONTRIBUTION: "ActiveContributionsByEconomicSector.png",
    Chart.HEATMAP_ATTRIBUTION: "TotalAttributionEffectsByEconomicSector.png",
    Chart.CUMULATIVE_ATTRIBUTION: "CumulativeAttributionEffectsByEconomicSector.png",
    Chart.CUMULATIVE_RETURN: "CumulativeReturns.png",
}
_TABLE_SIZES = {
    "OverallAttributionBySecurity": (2600, 4200),
    "CumulativeAttributionByEconomicSector": (2600, 1800),
    "OverallAttributionByEconomicSector": (2600, 1600),
    "RiskStatistics": (1800, 2600),
}


def _parse_args() -> argparse.Namespace:
    """Parse the optional non-writing drift-check mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def _analytics_outputs() -> tuple[Analytics, Attribution]:
    """Build the canonical packaged demonstration analytics."""
    analytics = Analytics(
        _INPUT / "performance" / "Mega-Cap Alpha Portfolio.csv",
        _INPUT / "performance" / "Mega-Cap Benchmark.csv",
        portfolio_classification_name="Security",
        benchmark_classification_name="Security",
        frequency=Frequency.QUARTERLY,
        holidays=_INPUT / "holidays.csv",
    )
    sector = analytics.attribution(
        "Economic Sector",
        _INPUT / "classifications" / "Economic Sector.csv",
        (
            _INPUT / "mappings" / "Security--to--Economic Sector.csv",
            _INPUT / "mappings" / "Security--to--Economic Sector.csv",
        ),
    )
    return analytics, sector


def _readme_inventory() -> tuple[str, ...]:
    """Return the unique canonical image names referenced by README.md."""
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    names = tuple(re.findall(re.escape(_RAW_PREFIX) + r'([^"\s]+)', readme))
    if len(names) != len(set(names)):
        raise RuntimeError("Each README image must be referenced exactly once.")
    return names


def _render(directory: Path) -> None:
    """Render the complete image inventory into an empty directory."""
    directory.mkdir(parents=True, exist_ok=True)
    analytics, sector = _analytics_outputs()
    for chart, file_name in _CHART_FILES.items():
        (directory / file_name).write_bytes(sector.to_chart(chart))

    html_by_name = {
        "OverallAttributionBySecurity": analytics.attribution(
            "Security", _INPUT / "classifications" / "Security.csv"
        ).to_html(View.OVERALL_ATTRIBUTION),
        "CumulativeAttributionByEconomicSector": sector.to_html(
            View.CUMULATIVE_ATTRIBUTION
        ),
        "OverallAttributionByEconomicSector": sector.to_html(View.OVERALL_ATTRIBUTION),
        "RiskStatistics": analytics.risk_statistics().to_html(),
    }
    chrome = _find_chrome()
    for name, html in html_by_name.items():
        html_path = directory / f"{name}.html"
        png_path = directory / f".{name}.png"
        html_path.write_text(html, encoding=util.ENCODING)
        _render_png(
            chrome,
            html_path,
            png_path,
            _TABLE_SIZES[name],
            directory / f".{name}_profile",
        )
        _crop_and_save_jpg(png_path, directory / f"{name}.jpg")
        html_path.unlink()
        png_path.unlink()
        shutil.rmtree(directory / f".{name}_profile", ignore_errors=True)


def _find_chrome() -> str:
    """Return an available Chrome or Chromium executable."""
    for candidate in _CHROME_CANDIDATES:
        if Path(candidate).is_file() or shutil.which(candidate):
            return candidate
    raise RuntimeError("Chrome or Chromium is required to render README table images.")


def _render_png(
    chrome_path: str,
    html_path: Path,
    png_path: Path,
    window_size: tuple[int, int],
    user_data_dir: Path,
) -> None:
    """Render HTML with one retry using a fresh browser profile."""
    for attempt in range(2):
        profile = (
            user_data_dir
            if attempt == 0
            else user_data_dir.with_name(f"{user_data_dir.name}_retry")
        )
        command = [
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--hide-scrollbars",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=1000",
            "--force-device-scale-factor=2",
            f"--user-data-dir={profile}",
            f"--screenshot={png_path}",
            f"--window-size={window_size[0]},{window_size[1]}",
            html_path.resolve().as_uri(),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            if png_path.is_file() and png_path.stat().st_size:
                return
            if attempt == 1:
                raise
            shutil.rmtree(profile, ignore_errors=True)


def _crop_and_save_jpg(source: Path, destination: Path) -> None:
    """Crop a browser screenshot to nonwhite content and save deterministic JPEG."""
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        white = Image.new("RGB", image.size, "white")
        bounds = ImageChops.difference(image, white).getbbox()
        if bounds is None:
            raise RuntimeError(f"Rendered image is blank: {source}")
        left, top, right, bottom = bounds
        padding = 24
        cropped = image.crop(
            (
                max(0, left - padding),
                max(0, top - padding),
                min(image.width, right + padding),
                min(image.height, bottom + padding),
            )
        )
        with io.BytesIO() as output:
            cropped.save(output, format="JPEG", quality=92, subsampling=0, optimize=False)
            destination.write_bytes(output.getvalue())


def _validate_inventory(directory: Path) -> None:
    """Require exact agreement between README references and generated files."""
    expected = set(_readme_inventory())
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if expected != actual:
        raise RuntimeError(
            f"README image inventory differs: missing={sorted(expected - actual)}, "
            f"unreferenced={sorted(actual - expected)}"
        )


def main() -> int:
    """Regenerate tracked images or compare a temporary render byte-for-byte."""
    args = _parse_args()
    with tempfile.TemporaryDirectory(prefix="ppar_readme_images_") as temporary:
        rendered = Path(temporary) / "images"
        _render(rendered)
        _validate_inventory(rendered)
        if args.check:
            _validate_inventory(_IMAGE_DIRECTORY)
            changed = [
                name
                for name in _readme_inventory()
                if (rendered / name).read_bytes()
                != (_IMAGE_DIRECTORY / name).read_bytes()
            ]
            if changed:
                raise RuntimeError("README images have drifted: " + ", ".join(changed))
        else:
            for source in rendered.iterdir():
                shutil.copyfile(source, _IMAGE_DIRECTORY / source.name)
    print("README images are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
