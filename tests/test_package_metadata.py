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
_PRODUCT_DESCRIPTION = (
    "Portfolio performance attribution, contribution, and ex-post risk analytics."
)
_ACTIVE_DOCUMENTATION = (
    "README.md",
    "docs/configuration.md",
    "docs/methodology.md",
    "docs/python_api.md",
    "docs/maintenance.md",
)


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

    def test_product_description_is_consistent(self) -> None:
        """Packaging, README, and the package docstring use one description."""
        self.assertEqual(_pyproject()["project"]["description"], _PRODUCT_DESCRIPTION)
        self.assertEqual(ppar.__doc__, _PRODUCT_DESCRIPTION)
        readme_lines = (_ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(readme_lines[2], _PRODUCT_DESCRIPTION)

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
        generic_readme = templates.joinpath("generic", "README.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            generic_readme.startswith("# ppar vendor-neutral demonstration\n")
        )
        self.assertNotIn("Generic", generic_readme)
        axys_readme = templates.joinpath("axys_apx", "README.md").read_text(
            encoding="utf-8"
        )
        for expected in (
            "## Use your own Axys/APX exports",
            "`portperf.csv`",
            "`secperf.csv`",
            "`secmast.csv`",
            "`AXYS_SOURCE_VALUES`",
            "ppar reconciles the security-level performance",
        ):
            self.assertIn(expected, axys_readme)

    def test_templates_keep_shared_workflow_in_sync(self) -> None:
        """Common demo settings and report publication remain equivalent."""
        generic = _template_named_nodes("generic")
        axys_apx = _template_named_nodes("axys_apx")
        shared_names = (
            "FROM_DATE",
            "THRU_DATE",
            "CLASSIFICATION",
            "FREQUENCY",
            "HOLIDAYS",
            "ANNUAL_MINIMUM_ACCEPTABLE_RETURN",
            "ANNUAL_RISK_FREE_RATE",
            "CONFIDENCE_LEVEL",
            "PORTFOLIO_VALUE",
            "SECURITY_VIEWS",
            "CLASSIFICATION_VIEWS",
            "CLASSIFICATION_CHARTS",
            "INCLUDE_RISK_STATISTICS",
            "main",
        )
        for name in shared_names:
            self.assertIn(name, generic)
            self.assertIn(name, axys_apx)
            self.assertEqual(
                ast.dump(generic[name], include_attributes=False),
                ast.dump(axys_apx[name], include_attributes=False),
                name,
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

    def test_obsolete_split_records_and_unused_fixture_are_absent(self) -> None:
        """The current checkout does not retain superseded pre-split evidence."""
        for relative in (
            "docs/repository_split_implementation_plan.md",
            "docs/repository_split_phase1_baseline.md",
            "docs/repository_split_phase1_baseline.json",
            "tests/data/performance/mag7_daily.csv",
            "ppar.egg-info",
        ):
            self.assertFalse((_ROOT / relative).exists(), relative)

    def test_exception_registry_is_absent(self) -> None:
        """Exceptions carry actionable messages rather than numeric codes."""
        text = (_ROOT / "src/ppar/errors.py").read_text(encoding="utf-8")
        self.assertNotIn("ERRORS", text)
        self.assertNotRegex(text, r"Error [0-9]{3}")

    def test_documentation_has_small_spine_and_marketing_images(self) -> None:
        """The active user path stays short while retaining README images."""
        for relative in _ACTIVE_DOCUMENTATION:
            self.assertTrue((_ROOT / relative).is_file(), relative)
        self.assertTrue(any((_ROOT / "docs/images").glob("*.*")))
        self.assertFalse((_ROOT / "PPAR.pdf").exists())
        self.assertFalse((_ROOT / "docs/archive").exists())
        self.assertFalse((_ROOT / "docs/audit").exists())

    def test_active_documentation_uses_current_terms(self) -> None:
        """Active guidance excludes retired product names."""
        active_text = "\n".join(
            (_ROOT / relative).read_text(encoding="utf-8")
            for relative in _ACTIVE_DOCUMENTATION
        )
        self.assertNotIn("Generic", active_text)
        self.assertNotIn("my_ppar_axys_apx", active_text)
        self.assertIn("vendor-neutral", active_text)

    def test_parallel_reference_directory_is_absent(self) -> None:
        """Generated demonstrations remain the source for input-file guidance."""
        self.assertFalse((_ROOT / "docs/reference").exists())


def _pyproject() -> dict[str, Any]:
    """Return parsed project metadata."""
    return tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _template_named_nodes(source: str) -> dict[str, ast.AST]:
    """Return named top-level assignments and functions from one demo template.

    Args:
        source: Template directory name beneath ``src/ppar/templates``.

    Returns:
        Top-level assignment and function nodes keyed by their declared names.
    """
    path = _ROOT / "src" / "ppar" / "templates" / source / "ppar_demo.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nodes: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            nodes[node.name] = node
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            nodes[node.targets[0].id] = node
    return nodes


if __name__ == "__main__":
    unittest.main()
