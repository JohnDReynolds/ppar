"""Tests for the simplified project and release gates."""

from __future__ import annotations

import inspect
from pathlib import Path
import unittest

from scripts import check_project, check_release_candidate


_ROOT = Path(__file__).resolve().parents[1]


class TestCheckProjectScript(unittest.TestCase):
    """The executable gates retain each independent-product check."""

    def test_product_gate_uses_direct_wheel_only(self) -> None:
        """The build path creates a wheel and explicitly rejects an sdist."""
        source = inspect.getsource(check_project._build_and_check_wheel)
        self.assertIn('shutil.rmtree(_ROOT / "build"', source)
        self.assertIn('shutil.rmtree(_ROOT / "src" / "ppar.egg-info"', source)
        self.assertIn('"--wheel"', source)
        self.assertIn('"--no-isolation"', source)
        self.assertNotIn('"--sdist"', source)
        self.assertIn("*.tar.gz", source)
        self.assertIn("py3-none-any.whl", source)

    def test_product_gate_runs_all_routine_checks(self) -> None:
        """Tests, typing, lint, docs, images, wheel, and workflows stay present."""
        source = inspect.getsource(check_project.main)
        for marker in (
            "pytest",
            "mypy",
            "pyright",
            "pylint",
            "_check_documentation",
            "render_readme_images.py",
            "_build_and_check_wheel",
            "_installed_wheel_smoke",
        ):
            self.assertIn(marker, source)

    def test_release_candidate_keeps_500x(self) -> None:
        """The release gate composes the routine gate and unchanged scale gate."""
        source = inspect.getsource(check_release_candidate.main)
        self.assertIn("check_project.py", source)
        self.assertIn("check_scale.py", source)
        self.assertIn('"500"', source)

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
        self.assertIn("scripts/check_project.py", compatibility)
        self.assertNotIn("scripts/check_release_candidate.py", compatibility)

        self.assertIn("workflow_call:", release_candidate)
        self.assertIn("workflow_dispatch:", release_candidate)
        self.assertIn('python-version: "3.12.1"', release_candidate)
        self.assertIn("scripts/check_release_candidate.py", release_candidate)

    def test_publish_requires_release_candidate_and_discovers_wheel(self) -> None:
        """Publishing follows the full gate without embedding a release version."""
        publish = (
            _ROOT / ".github" / "workflows" / "publish.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("uses: ./.github/workflows/release-candidate.yml", publish)
        self.assertIn("needs: release-candidate", publish)
        self.assertIn("mapfile -t wheels", publish)
        self.assertIn("*-py3-none-any.whl", publish)
        self.assertNotIn("ppar-0.2.0", publish)


if __name__ == "__main__":
    unittest.main()
