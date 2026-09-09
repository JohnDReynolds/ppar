"""Regression tests for reusable Matplotlib cache configuration."""

from __future__ import annotations

# The cache selector is intentionally package-internal and tested at that boundary.
# pylint: disable=protected-access

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from ppar import _chart_environment as chart_environment


_ROOT = Path(__file__).resolve().parents[1]


class TestChartEnvironment(unittest.TestCase):
    """Chart imports preserve native state and reuse a restricted fallback."""

    def test_explicit_cache_remains_authoritative(self) -> None:
        """A caller-provided MPLCONFIGDIR is returned without being touched."""
        with tempfile.TemporaryDirectory() as directory:
            explicit = Path(directory) / "caller-cache"
            environment = {"MPLCONFIGDIR": str(explicit)}
            with mock.patch.object(
                chart_environment,
                "_prepare_writable_directory",
            ) as prepare:
                actual = chart_environment._configure_matplotlib_cache(
                    environment,
                    home=Path(directory) / "home",
                    platform_name="linux",
                    temporary_directory=Path(directory) / "temporary",
                )

        self.assertEqual(actual, explicit)
        prepare.assert_not_called()
        self.assertFalse(explicit.exists())

    def test_writable_native_cache_does_not_set_environment(self) -> None:
        """Ordinary writable Matplotlib behavior remains native."""
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            environment: dict[str, str] = {}

            actual = chart_environment._configure_matplotlib_cache(
                environment,
                home=home,
                platform_name="darwin",
                temporary_directory=Path(directory) / "temporary",
            )

            self.assertEqual(actual, home / ".matplotlib")
            self.assertTrue(actual.is_dir())
            self.assertNotIn("MPLCONFIGDIR", environment)

    def test_linux_native_cache_honors_xdg_configuration_root(self) -> None:
        """Native Linux configuration and cache directories follow XDG behavior."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {
                "XDG_CONFIG_HOME": str(root / "configuration"),
                "XDG_CACHE_HOME": str(root / "cache"),
            }

            actual = chart_environment._configure_matplotlib_cache(
                environment,
                home=root / "home",
                platform_name="linux",
                temporary_directory=root / "temporary",
            )

            self.assertEqual(actual, root / "configuration" / "matplotlib")
            self.assertTrue((root / "cache" / "matplotlib").is_dir())
            self.assertNotIn("MPLCONFIGDIR", environment)

    def test_unwritable_linux_cache_selects_fallback(self) -> None:
        """A writable XDG configuration cannot hide an unavailable font cache."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unavailable_cache = root / "not-a-directory"
            unavailable_cache.write_text("occupied", encoding="utf-8")
            environment = {
                "XDG_CONFIG_HOME": str(root / "configuration"),
                "XDG_CACHE_HOME": str(unavailable_cache),
            }

            actual = chart_environment._configure_matplotlib_cache(
                environment,
                home=root / "home",
                platform_name="linux",
                temporary_directory=root / "temporary",
            )

            expected = chart_environment._temporary_matplotlib_directory(
                root / "temporary"
            )
            self.assertEqual(actual, expected)
            self.assertEqual(environment["MPLCONFIGDIR"], str(expected))

    def test_unwritable_native_cache_selects_stable_fallback(self) -> None:
        """A restricted native location selects one reusable temporary path."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unavailable_home = root / "not-a-directory"
            unavailable_home.write_text("occupied", encoding="utf-8")
            environment: dict[str, str] = {}

            actual = chart_environment._configure_matplotlib_cache(
                environment,
                home=unavailable_home,
                platform_name="darwin",
                temporary_directory=root / "temporary",
            )

            expected = chart_environment._temporary_matplotlib_directory(
                root / "temporary"
            )
            self.assertEqual(actual, expected)
            self.assertEqual(environment["MPLCONFIGDIR"], str(expected))
            self.assertTrue(expected.is_dir())

    def test_unusable_fallback_leaves_matplotlib_policy_unchanged(self) -> None:
        """Two unavailable locations do not hide Matplotlib's own fallback."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment: dict[str, str] = {}
            with mock.patch.object(
                chart_environment,
                "_prepare_writable_directory",
                side_effect=(PermissionError("native"), PermissionError("fallback")),
            ):
                actual = chart_environment._configure_matplotlib_cache(
                    environment,
                    home=root / "home",
                    platform_name="darwin",
                    temporary_directory=root / "temporary",
                )

        self.assertEqual(actual, root / "home" / ".matplotlib")
        self.assertNotIn("MPLCONFIGDIR", environment)

    def test_separate_processes_choose_the_same_fallback(self) -> None:
        """The restricted fallback remains stable across fresh Python processes."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unavailable_home = root / "not-a-directory"
            unavailable_home.write_text("occupied", encoding="utf-8")
            temporary = root / "temporary"
            temporary.mkdir()
            environment = os.environ.copy()
            environment.pop("MPLCONFIGDIR", None)
            environment["HOME"] = str(unavailable_home)
            environment["TMPDIR"] = str(temporary)
            command = [
                sys.executable,
                "-c",
                "import os; "
                "from ppar._chart_environment import configure_current_process; "
                "configure_current_process(); print(os.environ['MPLCONFIGDIR'])",
            ]

            first = subprocess.run(
                command,
                cwd=_ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            second = subprocess.run(
                command,
                cwd=_ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            self.assertEqual(first, second)
            self.assertTrue(Path(first).is_dir())

    def test_table_only_import_does_not_import_matplotlib(self) -> None:
        """Importing ppar without rendering a chart leaves Matplotlib unloaded."""
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import ppar; print('matplotlib' in sys.modules)",
            ],
            cwd=_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
