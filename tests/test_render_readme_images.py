"""Tests for deterministic README image generation."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import render_readme_images


class TestRenderReadmeImages(unittest.TestCase):
    """The renderer is bounded and its README inventory is exact."""

    def test_readme_inventory_matches_tracked_images(self) -> None:
        """Every marketing image is retained and referenced exactly once."""
        expected = set(render_readme_images._readme_inventory())
        actual = {
            path.name
            for path in (Path("docs") / "images").iterdir()
            if path.is_file()
        }
        self.assertEqual(expected, actual)
        self.assertEqual(len(expected), 12)

    def test_images_carry_current_source_fingerprint(self) -> None:
        """Every retained image proves which code, inputs, and dependencies made it."""
        render_readme_images._validate_images(Path("docs") / "images")

    def test_fingerprint_inputs_cover_only_the_rendering_boundary(self) -> None:
        """Image provenance includes rendering inputs and excludes unrelated sources."""
        inputs = {
            path.relative_to(render_readme_images._ROOT).as_posix()
            for path in render_readme_images._fingerprint_files()
        }
        top_level_modules = {
            path.relative_to(render_readme_images._ROOT).as_posix()
            for path in (render_readme_images._ROOT / "src" / "ppar").glob("*.py")
        }
        generic_inputs = {
            path.relative_to(render_readme_images._ROOT).as_posix()
            for path in render_readme_images._INPUT.rglob("*.csv")
        }

        self.assertTrue(top_level_modules <= inputs)
        self.assertTrue(generic_inputs <= inputs)
        self.assertIn("scripts/render_readme_images.py", inputs)
        self.assertIn("constraints/ci.txt", inputs)
        self.assertIn("pyproject.toml", inputs)
        self.assertFalse(any("/axys_apx/" in path for path in inputs))
        self.assertFalse(any("/cli/" in path for path in inputs))
        self.assertFalse(any(path.endswith((".md", ".yaml", "py.typed")) for path in inputs))

    def test_check_mode_validates_without_rasterizing(self) -> None:
        """Portable checks validate provenance without invoking platform rasterizers."""
        arguments = mock.Mock(check=True)
        with (
            mock.patch.object(render_readme_images, "_parse_args", return_value=arguments),
            mock.patch.object(render_readme_images, "_render") as renderer,
        ):
            self.assertEqual(render_readme_images.main(), 0)
        renderer.assert_not_called()

    def test_render_png_retries_one_transient_browser_crash(self) -> None:
        """A first browser abort receives one fresh-profile retry."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html_path = root / "report.html"
            html_path.write_text("<html></html>", encoding="utf-8")
            with mock.patch(
                "scripts.render_readme_images.subprocess.run",
                side_effect=(subprocess.CalledProcessError(1, ["chrome"]), mock.DEFAULT),
            ) as runner:
                render_readme_images._render_png(
                    "chrome",
                    html_path,
                    root / "report.png",
                    (100, 100),
                    root / "profile",
                )
        self.assertEqual(runner.call_count, 2)
        self.assertIn(
            f"--user-data-dir={root / 'profile_retry'}",
            runner.call_args_list[1].args[0],
        )

    def test_render_png_raises_after_two_browser_crashes(self) -> None:
        """Persistent browser failure remains release-stopping."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            html_path = root / "report.html"
            html_path.write_text("<html></html>", encoding="utf-8")
            with mock.patch(
                "scripts.render_readme_images.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, ["chrome"]),
            ) as runner:
                with self.assertRaises(subprocess.CalledProcessError):
                    render_readme_images._render_png(
                        "chrome",
                        html_path,
                        root / "report.png",
                        (100, 100),
                        root / "profile",
                    )
        self.assertEqual(runner.call_count, 2)


if __name__ == "__main__":
    unittest.main()
