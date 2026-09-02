"""Tests for the simplified project and release gates."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from scripts import check_project, check_release_candidate


_ROOT = Path(__file__).resolve().parents[1]


class TestCheckProjectScript(unittest.TestCase):
    """The executable gates retain each independent-product check."""

    def test_product_gate_uses_direct_wheel_command(self) -> None:
        """The explicit build contract requests one nonisolated wheel."""
        command = check_project._wheel_build_command(Path("dist"))

        self.assertEqual(
            command[1:],
            (
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                Path("dist"),
            ),
        )

    def test_wheel_build_uses_an_isolated_source_copy(self) -> None:
        """Building a wheel neither creates nor removes generated checkout paths."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wheel = root / "dist" / "ppar-0.2.1-py3-none-any.whl"
            with (
                mock.patch.object(check_project, "_run") as run,
                mock.patch.object(
                    check_project,
                    "_inspect_wheel",
                    return_value=wheel,
                ),
                mock.patch("shutil.rmtree") as remove,
            ):
                result = check_project._build_and_check_wheel(
                    root / "dist",
                    root / "wheel-source",
                )

            source = root / "wheel-source"
            self.assertEqual(result, wheel)
            self.assertTrue((source / "pyproject.toml").is_file())
            self.assertTrue((source / "src" / "ppar" / "__init__.py").is_file())
            self.assertEqual(run.call_args_list[0].kwargs["cwd"], source)
            remove.assert_not_called()

    def test_product_gate_runs_all_routine_checks(self) -> None:
        """The command contract includes tests, typing, and both lint levels."""
        commands = check_project._routine_commands("python")

        self.assertEqual(commands[0], ("python", "-m", "pytest", "-q"))
        self.assertIn(("python", "-m", "mypy", "src/ppar", "scripts"), commands)
        self.assertTrue(any("pyright" in command for command in commands))
        self.assertTrue(any("--errors-only" in command for command in commands))
        self.assertTrue(
            any("--enable=unused-import,unused-variable" in command for command in commands)
        )

    def test_wheel_inspection_accepts_current_resources_and_rejects_sdist(self) -> None:
        """Wheel inspection enforces artifacts rather than implementation text."""
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            wheel = directory / "ppar-0.2.1-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                for name in check_project._REQUIRED_WHEEL_RESOURCES:
                    archive.writestr(name, "fixture")

            self.assertEqual(check_project._inspect_wheel(directory), wheel)

            (directory / "ppar-0.2.1.tar.gz").touch()
            with self.assertRaisesRegex(RuntimeError, "must not create an sdist"):
                check_project._inspect_wheel(directory)

    def test_documentation_policy_accepts_the_current_spine(self) -> None:
        """The executable documentation policy is the single behavior contract."""
        check_project._check_documentation()

    def test_release_candidate_keeps_500x(self) -> None:
        """The release gate composes the routine gate and required scale check."""
        self.assertEqual(
            check_release_candidate._release_commands("python"),
            (
                ("python", "scripts/check_project.py"),
                ("python", "scripts/check_scale.py", "--scale", "500"),
            ),
        )

        output = Path("validated-wheel")
        self.assertEqual(
            check_release_candidate._release_commands("python", output),
            (
                (
                    "python",
                    "scripts/check_project.py",
                    "--wheel-output",
                    "validated-wheel",
                ),
                ("python", "scripts/check_scale.py", "--scale", "500"),
            ),
        )

    def test_github_workflows_separate_compatibility_and_release_checks(self) -> None:
        """Routine compatibility and full release validation have distinct triggers."""
        workflows = _ROOT / ".github" / "workflows"
        compatibility = workflows.joinpath("compatibility.yml").read_text(
            encoding="utf-8"
        )
        release_candidate = workflows.joinpath("release-candidate.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn('name: ppar compatibility', compatibility)
        self.assertIn('"3.11.9"', compatibility)
        self.assertIn('"3.12.1"', compatibility)
        self.assertIn('"3.13"', compatibility)
        self.assertIn('"3.14"', compatibility)
        self.assertIn("MPLBACKEND: Agg", compatibility)
        self.assertIn("scripts/check_project.py", compatibility)
        self.assertNotIn("scripts/check_release_candidate.py", compatibility)

        self.assertIn("workflow_call:", release_candidate)
        self.assertIn("workflow_dispatch:", release_candidate)
        self.assertIn('python-version: "3.12.1"', release_candidate)
        self.assertIn("scripts/check_release_candidate.py", release_candidate)
        self.assertIn("--wheel-output", release_candidate)
        self.assertIn("actions/upload-artifact@v4", release_candidate)

    def test_publish_requires_release_candidate_and_discovers_wheel(self) -> None:
        """Publishing follows the full gate without embedding a release version."""
        publish = (
            _ROOT / ".github" / "workflows" / "publish.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("uses: ./.github/workflows/release-candidate.yml", publish)
        self.assertIn("needs: release-candidate", publish)
        self.assertIn("actions/download-artifact@v5", publish)
        self.assertIn("name: ppar-universal-wheel", publish)
        self.assertNotIn("python -m build", publish)
        self.assertNotIn("ppar-0.2.1", publish)


if __name__ == "__main__":
    unittest.main()
