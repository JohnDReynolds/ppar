"""Tests for ppar identity, packaging, and repository independence."""

from __future__ import annotations

import ast
from importlib import metadata, resources
from pathlib import Path
import tomllib
from typing import Any
import unittest

import ppar


_ROOT = Path(__file__).resolve().parents[1]


class TestPackageMetadata(unittest.TestCase):
    """The extracted product has one coherent public and packaged identity."""

    def test_project_identity_is_ppar(self) -> None:
        """Distribution metadata names only the independent Analytics product."""
        project = _pyproject()["project"]
        self.assertEqual(project["name"], "ppar")
        self.assertEqual(project["version"], "0.2.0")
        self.assertEqual(project["scripts"], {"ppar": "ppar.cli:main"})
        self.assertEqual(
            project["urls"]["Repository"],
            "https://github.com/JohnDReynolds/ppar",
        )
        self.assertEqual(ppar.__version__, metadata.version("ppar"))

    def test_runtime_dependencies_are_complete_and_independent(self) -> None:
        """The base install contains both workflows without product extras."""
        project = _pyproject()["project"]
        dependencies = project["dependencies"]
        self.assertEqual(
            {dependency.split(">=")[0] for dependency in dependencies},
            {"matplotlib", "numpy", "polars", "pyyaml", "seaborn"},
        )
        self.assertNotIn("perfaud", " ".join(dependencies).lower())
        self.assertEqual(set(project["optional-dependencies"]), {"dev"})
        for removed in ("pandas", "pyarrow", "lxml", "openpyxl"):
            self.assertNotIn(removed, " ".join(dependencies).lower())

    def test_root_exports_are_exact(self) -> None:
        """The root exposes only the primary facade and version."""
        self.assertEqual(ppar.__all__, ["Analytics", "__version__"])
        self.assertTrue(callable(ppar.Analytics))

    def test_templates_contain_one_tutorial_runner(self) -> None:
        """Both installed templates contain one root-level Python demo."""
        templates = resources.files("ppar").joinpath("templates")
        self.assertEqual(
            sorted(item.name for item in templates.iterdir()),
            ["axys_apx", "generic"],
        )
        for source in ("axys_apx", "generic"):
            template = templates.joinpath(source)
            names = sorted(item.name for item in template.iterdir())
            self.assertEqual(names, ["README.md", "input", "ppar_demo.py"])
            self.assertEqual(
                [path.name for path in (_ROOT / "src/ppar/templates" / source).rglob("*.py")],
                ["ppar_demo.py"],
            )

    def test_source_never_imports_perfaud(self) -> None:
        """No runtime module depends on the neighboring Audit product."""
        offenders: list[str] = []
        for path in (_ROOT / "src/ppar").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = ""
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                elif isinstance(node, ast.Import):
                    module = ",".join(alias.name for alias in node.names)
                if module == "perfaud" or module.startswith("perfaud."):
                    offenders.append(str(path.relative_to(_ROOT)))
        self.assertEqual(offenders, [])

    def test_obsolete_namespaces_and_catch_all_modules_are_absent(self) -> None:
        """The extracted tree does not retain combined-product compatibility."""
        self.assertFalse((_ROOT / "ppar").exists())
        for relative in (
            "src/ppar/analytics",
            "src/ppar/audit",
            "src/ppar/common.py",
            "src/ppar/source_files.py",
            "src/ppar/output.py",
        ):
            self.assertFalse((_ROOT / relative).exists(), relative)

    def test_exception_registry_is_absent(self) -> None:
        """Exceptions carry actionable messages rather than numeric codes."""
        text = (_ROOT / "src/ppar/errors.py").read_text(encoding="utf-8")
        self.assertNotIn("ERRORS", text)
        self.assertNotRegex(text, r"Error [0-9]{3}")

    def test_documentation_has_small_spine_and_marketing_images(self) -> None:
        """The active user path stays short while retaining README images."""
        for relative in (
            "README.md",
            "docs/configuration.md",
            "docs/methodology.md",
            "docs/python_api.md",
            "docs/maintenance.md",
        ):
            self.assertTrue((_ROOT / relative).is_file(), relative)
        self.assertTrue(any((_ROOT / "docs/images").glob("*.*")))
        self.assertFalse((_ROOT / "PPAR.pdf").exists())
        self.assertFalse((_ROOT / "docs/archive").exists())
        self.assertFalse((_ROOT / "docs/audit").exists())


def _pyproject() -> dict[str, Any]:
    """Return parsed project metadata."""
    return tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
