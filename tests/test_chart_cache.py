"""Regression tests for persistent Matplotlib cache configuration."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from ppar import _chart_environment as chart_environment


_ROOT = Path(__file__).resolve().parents[1]


def _cached_environment() -> dict[str, str]:
    """Return an environment that excludes font-cache construction from tests."""
    environment = os.environ.copy()
    environment["MPLCONFIGDIR"] = str(
        Path(tempfile.gettempdir()) / "ppar_chart_cache" / "matplotlib"
    )
    return environment


def _import_backend(environment: dict[str, str], *, programmatic: str | None = None) -> str:
    """Import the chart module in a new process and return its active backend."""
    if programmatic:
        imports = (
            "import matplotlib; "
            f"matplotlib.use({programmatic!r}); "
            "import ppar.charts; "
        )
    else:
        imports = "import ppar.charts; import matplotlib; "
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            imports + "print(matplotlib.get_backend())",
        ],
        cwd=_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip().lower()


class TestChartCache(unittest.TestCase):
    """Ordinary imports reuse persistent cache state without overriding users."""

    def test_default_cache_uses_the_platform_user_cache(self) -> None:
        """ppar does not place ordinary Matplotlib state in temporary storage."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            cases = (
                (
                    "macOS",
                    "darwin",
                    "posix",
                    {},
                    home / "Library" / "Caches" / "ppar" / "matplotlib",
                ),
                (
                    "Linux",
                    "linux",
                    "posix",
                    {},
                    home / ".cache" / "ppar" / "matplotlib",
                ),
                (
                    "Windows",
                    "win32",
                    "nt",
                    {"LOCALAPPDATA": str(root / "local")},
                    root / "local" / "ppar" / "Cache" / "matplotlib",
                ),
            )
            for name, platform_name, operating_system, environment, expected in cases:
                with self.subTest(platform=name):
                    actual = chart_environment.configure_matplotlib_cache(
                        environment,
                        home=home,
                        platform_name=platform_name,
                        operating_system=operating_system,
                        temporary_directory=root / "temporary",
                    )

                    self.assertEqual(actual, expected)
                    self.assertTrue(actual.is_dir())

    def test_xdg_cache_root_is_respected_when_present(self) -> None:
        """An explicit XDG cache root determines ppar's persistent location."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xdg_cache = root / "xdg"
            environment = {"XDG_CACHE_HOME": str(xdg_cache)}

            actual = chart_environment.configure_matplotlib_cache(
                environment,
                home=root / "home",
                platform_name="linux",
                operating_system="posix",
                temporary_directory=root / "temporary",
            )

            self.assertEqual(actual, xdg_cache / "ppar" / "matplotlib")
            self.assertTrue(actual.is_dir())

    def test_explicit_matplotlib_cache_remains_authoritative(self) -> None:
        """ppar never replaces a caller-supplied MPLCONFIGDIR."""
        with tempfile.TemporaryDirectory() as directory:
            explicit = Path(directory) / "caller-cache"
            environment = {
                "MPLCONFIGDIR": str(explicit),
                "XDG_CACHE_HOME": str(Path(directory) / "other-cache"),
            }

            actual = chart_environment.configure_matplotlib_cache(
                environment,
                home=Path(directory) / "home",
                platform_name="linux",
                operating_system="posix",
                temporary_directory=Path(directory) / "temporary",
            )

            self.assertEqual(actual, explicit)

    def test_unwritable_user_cache_falls_back_to_temporary_storage(self) -> None:
        """Restricted environments retain the former writable-cache safety net."""
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            unavailable_home = temporary / "not-a-directory"
            unavailable_home.write_text("occupied", encoding="utf-8")
            environment: dict[str, str] = {}

            actual = chart_environment.configure_matplotlib_cache(
                environment,
                home=unavailable_home,
                platform_name="darwin",
                operating_system="posix",
                temporary_directory=temporary,
            )

            expected = temporary / "ppar_chart_cache" / "matplotlib"
            self.assertEqual(actual, expected)
            self.assertEqual(environment["MPLCONFIGDIR"], str(expected))
            self.assertTrue(expected.is_dir())

    def test_existing_but_unwritable_user_cache_also_falls_back(self) -> None:
        """A successful exist-ok mkdir is not mistaken for write permission."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment: dict[str, str] = {}
            with mock.patch.object(
                chart_environment,
                "_prepare_writable_cache",
                side_effect=(PermissionError("read-only"), None),
            ) as prepare:
                actual = chart_environment.configure_matplotlib_cache(
                    environment,
                    home=root / "home",
                    platform_name="linux",
                    operating_system="posix",
                    temporary_directory=root / "temporary",
                )

            persistent = root / "home" / ".cache" / "ppar" / "matplotlib"
            fallback = root / "temporary" / "ppar_chart_cache" / "matplotlib"
            self.assertEqual(
                prepare.call_args_list,
                [mock.call(persistent), mock.call(fallback)],
            )
            self.assertEqual(actual, fallback)
            self.assertEqual(environment["MPLCONFIGDIR"], str(fallback))


class TestChartBackend(unittest.TestCase):
    """Static PNG rendering avoids GUI startup while respecting caller choices."""

    def test_ordinary_chart_import_uses_agg(self) -> None:
        """A caller without a backend selection receives the static Agg backend."""
        environment = _cached_environment()
        environment.pop("MPLBACKEND", None)

        backend = _import_backend(environment)

        self.assertEqual(backend, "agg")

    def test_explicit_environment_backend_remains_authoritative(self) -> None:
        """An explicit MPLBACKEND is not replaced by ppar's ordinary default."""
        environment = _cached_environment()
        environment["MPLBACKEND"] = "svg"

        backend = _import_backend(environment)

        self.assertEqual(backend, "svg")

    def test_programmatic_backend_selection_remains_authoritative(self) -> None:
        """A backend selected before chart import is not changed by ppar."""
        environment = _cached_environment()
        environment.pop("MPLBACKEND", None)

        backend = _import_backend(environment, programmatic="svg")

        self.assertEqual(backend, "svg")


if __name__ == "__main__":
    unittest.main()
