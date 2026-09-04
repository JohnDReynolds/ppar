"""Tests for ppar identity, packaging, and repository independence."""

from __future__ import annotations

import ast
from importlib import metadata, resources
from pathlib import Path
import runpy
import tomllib
from typing import Any
import unittest
from unittest import mock

import ppar
import ppar.attribution
import ppar.axys_apx
import ppar.errors
import ppar.frequency
import ppar.risk
import ppar.schema
import ppar.utilities


_ROOT = Path(__file__).resolve().parents[1]
_PRODUCT_DESCRIPTION = (
    "Portfolio performance attribution, contribution, and ex-post risk analytics."
)
class TestPackageMetadata(unittest.TestCase):
    """The extracted product has one coherent public and packaged identity."""

    def test_project_identity_is_ppar(self) -> None:
        """Distribution metadata names only the independent Analytics product."""
        project = _pyproject()["project"]
        self.assertEqual(project["name"], "ppar")
        self.assertEqual(project["version"], "0.4.0")
        self.assertEqual(project["requires-python"], ">=3.11.9,<3.15")
        self.assertEqual(project["scripts"], {"ppar": "ppar.cli:main"})
        self.assertEqual(
            project["urls"]["Repository"],
            "https://github.com/JohnDReynolds/ppar",
        )
        self.assertEqual(ppar.__version__, project["version"])
        self.assertEqual(ppar.__version__, metadata.version("ppar"))
        self.assertIn(
            "ppar supports Python 3.11.9 through Python 3.14.",
            (_ROOT / "README.md").read_text(encoding="utf-8"),
        )

    def test_uninstalled_source_uses_unknown_version_fallback(self) -> None:
        """Source execution cannot drift to a stale hardcoded release version."""
        with mock.patch(
            "importlib.metadata.version",
            side_effect=metadata.PackageNotFoundError,
        ):
            namespace = runpy.run_path(str(_ROOT / "src/ppar/__init__.py"))

        self.assertEqual(namespace["__version__"], "0+unknown")

    def test_product_description_is_consistent(self) -> None:
        """Packaging, README, and the package docstring use one description."""
        self.assertEqual(_pyproject()["project"]["description"], _PRODUCT_DESCRIPTION)
        self.assertEqual(ppar.__doc__, _PRODUCT_DESCRIPTION)
        readme_lines = (_ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(readme_lines[2], _PRODUCT_DESCRIPTION)

    def test_evaluation_terms_and_licensing_contact_are_visible(self) -> None:
        """Users see the evaluation limit and a direct contact before installation."""
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")
        license_text = (_ROOT / "LICENSE").read_text(encoding="utf-8")

        install_position = readme.index("python -m pip install ppar")
        self.assertLess(readme.index("45-day, single-user"), install_position)
        self.assertLess(readme.index("jjjkreynolds@gmail.com"), install_position)
        self.assertIn("solely for internal evaluation for 45 days", license_text)
        self.assertIn("John D Reynolds at\njjjkreynolds@gmail.com", license_text)
        self.assertNotRegex(license_text, r"\bPPAR\b")

    def test_documentation_has_one_concise_introductory_analytics_example(self) -> None:
        """The root owns the complete introductory example without API-page duplication."""
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")
        python_section = readme.split("## Python\n", maxsplit=1)[1].split(
            "## Documentation\n", maxsplit=1
        )[0]
        self.assertEqual(python_section.count("```python"), 1)
        example = python_section.split("```python\n", maxsplit=1)[1].split(
            "```", maxsplit=1
        )[0]
        compile(example, "README.md Python example", "exec")
        self.assertIn(".tail(1)", example)
        self.assertIn(
            '.select("Portfolio_Return", "Benchmark_Return", "Active_Return")',
            example,
        )

        api_guide = (_ROOT / "docs/python_api.md").read_text(encoding="utf-8")
        self.assertNotIn("analytics = Analytics(", api_guide)
        self.assertIn("Attribution.to_html(view)", api_guide)
        self.assertIn("Attribution.to_chart(chart)", api_guide)

    def test_reports_guide_orients_every_supported_report(self) -> None:
        """One guide owns report selection, interpretation, formats, and upgrades."""
        guide = (_ROOT / "docs/reports.md").read_text(encoding="utf-8")
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")
        api_guide = (_ROOT / "docs/python_api.md").read_text(encoding="utf-8")

        for report_type in (*ppar.attribution.View, *ppar.attribution.Chart):
            with self.subTest(report_type=report_type.name):
                self.assertIn(f"`{report_type.name}`", guide)

        risk_statistics = (
            "Return Range",
            "Mean Return",
            "Annualized Mean Return",
            "Standard Deviation",
            "Annualized Standard Deviation",
            "Downside Probability",
            "Expected Downside Value",
            "Downside Deviation",
            "Annualized Downside Deviation",
            "Value At Risk",
            "Correlation",
            "R-Squared",
            "Tracking Error",
            "Annualized Tracking Error",
            "Sharpe Ratio",
            "Annualized Sharpe Ratio",
            "Sortino Ratio",
            "Annualized Sortino Ratio",
            "Information Ratio",
            "M-Squared",
            "Treynor Ratio",
            "Beta",
            "Alpha",
            "Annualized Alpha",
            "Jensen's Alpha",
            "Annualized Jensen's Alpha",
        )
        for statistic in risk_statistics:
            with self.subTest(statistic=statistic):
                self.assertIn(statistic, guide)

        for required in (
            "Portfolio_Contribution_Simple",
            "Allocation_Effect_Simple",
            "Names ending in `_Smoothed`",
            "Names beginning with `Cumulative_`",
            "numeric missing-value representation",
            "attribution.write_csv",
            "does not change when ppar is upgraded",
        ):
            self.assertIn(required, guide)

        csv_example = guide.split("```python\n", maxsplit=1)[1].split(
            "```", maxsplit=1
        )[0]
        compile(csv_example, "reports guide CSV example", "exec")

        self.assertIn("[Reports and results](docs/reports.md)", readme)
        self.assertIn("[Contributor maintenance](docs/maintenance.md)", readme)
        self.assertIn("[Reports and results](reports.md)", api_guide)
        self.assertIn("Receive `Attribution`", api_guide)
        self.assertNotIn("perfattr", api_guide)

    def test_public_result_docstrings_explain_normal_acquisition(self) -> None:
        """Interactive help distinguishes entry points from returned result types."""
        self.assertIn("returned by Analytics", ppar.attribution.Attribution.__doc__ or "")
        self.assertIn("returned by AxysData", ppar.axys_apx.AxysPortfolio.__doc__ or "")
        self.assertIn(
            "returned by AxysData",
            ppar.axys_apx.AxysClassificationSources.__doc__ or "",
        )

    def test_runtime_dependencies_are_complete_and_independent(self) -> None:
        """The base install contains both workflows without product extras."""
        project = _pyproject()["project"]
        dependencies = project["dependencies"]
        self.assertEqual(
            {dependency.split(">=")[0] for dependency in dependencies},
            {
                "matplotlib",
                "numpy",
                "pandas",
                "perfattr",
                "pillow",
                "polars",
                "seaborn",
            },
        )
        self.assertNotIn("perfaud", " ".join(dependencies).lower())
        self.assertIn("perfattr>=0.3.0a1,<0.4", dependencies)
        constraints = (_ROOT / "constraints/ci.txt").read_text(encoding="utf-8")
        self.assertIn("perfattr==0.3.0a1", constraints.splitlines())
        self.assertEqual(set(project["optional-dependencies"]), {"dev"})

    def test_root_exports_are_exact(self) -> None:
        """The root exposes only the primary facade and version."""
        self.assertEqual(ppar.__all__, ["Analytics", "__version__"])
        self.assertTrue(callable(ppar.Analytics))

    def test_supported_module_exports_are_explicit(self) -> None:
        """Documented lower-level modules expose only their supported objects."""
        expected_exports = {
            ppar.attribution: ["Attribution", "Chart", "View"],
            ppar.axys_apx: [
                "AxysClassificationSources",
                "AxysData",
                "AxysPortfolio",
            ],
            ppar.errors: ["PparError"],
            ppar.frequency: ["Frequency"],
            ppar.risk: ["RiskStatistics"],
        }
        for module, expected in expected_exports.items():
            with self.subTest(module=module.__name__):
                self.assertEqual(module.__all__, expected)
        self.assertTrue(ppar.schema.__all__)
        self.assertTrue(
            all(
                isinstance(getattr(ppar.schema, name), str)
                for name in ppar.schema.__all__
            )
        )
        self.assertEqual(ppar.utilities.__all__, [])

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
        for expected in (
            "Reports are written to `output/`.",
            "## Performance files",
            "`weight` | Holding weight as a decimal; `0.25` means 25%.",
            "`return` | Holding return as a decimal; `0.05` means 5%.",
            "weights must sum to 1.0",
            "at least one common selected period",
            "select periods by `thru_date`, including both boundaries",
            "## Classifications and mappings",
            "`Security.csv` | Performance identifier | Display name",
            "Mapping file | Performance identifier | Classification identifier",
            "Common setup errors include",
        ):
            self.assertIn(expected, generic_readme)
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
        self.assertTrue(
            axys_readme.endswith(
                "classification, calculation assumptions, and reports you want to "
                "produce.\n"
            )
        )
        self.assertNotIn("perfattr", axys_readme)

    def test_templates_keep_shared_workflow_in_sync(self) -> None:
        """Common demo settings and direct report writing remain equivalent."""
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
