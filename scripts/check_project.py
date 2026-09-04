"""Run the complete routine ppar product gate."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile


_ROOT = Path(__file__).resolve().parents[1]
_ACTIVE_DOCUMENTATION = (
    "README.md",
    "docs/methodology.md",
    "docs/reports.md",
    "docs/python_api.md",
    "docs/maintenance.md",
)
_REQUIRED_WHEEL_RESOURCES = {
    "ppar/py.typed",
    "ppar/templates/axys_apx/ppar_demo.py",
    "ppar/templates/axys_apx/README.md",
    "ppar/templates/axys_apx/input/portperf.csv",
    "ppar/templates/generic/ppar_demo.py",
    "ppar/templates/generic/README.md",
    "ppar/templates/generic/input/performance/Mega-Cap Alpha Portfolio.csv",
}
_WHEEL_SOURCE_FILES = ("LICENSE", "README.md", "pyproject.toml")


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse an optional directory for retaining the validated wheel."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wheel-output",
        type=Path,
        help="Retain the validated wheel in this otherwise empty directory.",
    )
    return parser.parse_args(argv)


def _run(
    command: list[str | Path],
    *,
    cwd: Path = _ROOT,
    env: dict[str, str] | None = None,
) -> None:
    """Run one gate command and stop on failure."""
    normalized = [str(part) for part in command]
    print(f"==> {' '.join(normalized)}", flush=True)
    subprocess.run(normalized, cwd=cwd, check=True, env=env)


def _venv_command(environment: Path, name: str) -> Path:
    """Return an executable path inside a temporary virtual environment."""
    scripts = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return environment / scripts / f"{name}{suffix}"


def _routine_commands(python: str | Path) -> tuple[tuple[str | Path, ...], ...]:
    """Return the explicit routine test and static-analysis command contract."""
    return (
        (python, "-m", "pytest", "-q"),
        (python, "-m", "mypy", "src/ppar", "scripts"),
        (
            python,
            "-m",
            "pyright",
            "--pythonpath",
            python,
            "src/ppar",
            "tests",
        ),
        (python, "-m", "pylint", "--errors-only", "src/ppar", "scripts", "tests"),
        (
            python,
            "-m",
            "pylint",
            "--disable=all",
            "--enable=unused-import,unused-variable",
            "src/ppar",
            "scripts",
        ),
    )


def _wheel_build_command(directory: Path) -> tuple[str | Path, ...]:
    """Return the direct universal-wheel build command."""
    return (
        sys.executable,
        "-m",
        "build",
        "--wheel",
        "--no-isolation",
        "--outdir",
        directory,
    )


def _check_documentation(root: Path = _ROOT) -> None:
    """Check the small documentation spine and executable demonstration references."""
    for relative in _ACTIVE_DOCUMENTATION:
        if not (root / relative).is_file():
            raise RuntimeError(f"Missing active documentation: {relative}")
    demonstration_documentation = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in (
            "src/ppar/templates/generic/ppar_demo.py",
            "src/ppar/templates/generic/README.md",
            "src/ppar/templates/axys_apx/ppar_demo.py",
            "src/ppar/templates/axys_apx/README.md",
        )
    )
    for value in (
        "ppar_demo.py",
        "AxysData(",
        "CLASSIFICATION_VIEWS",
        "portperf.csv",
        "secperf.csv",
        "secmast.csv",
    ):
        if value not in demonstration_documentation:
            raise RuntimeError(f"Demonstration documentation omits {value}.")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for command in (
        "ppar setup ./my_ppar",
        "ppar setup ./my_ppar --axys-apx",
        "python ./my_ppar/ppar_demo.py",
    ):
        if command not in readme:
            raise RuntimeError(f"README omits executable command: {command}")

    methodology = (root / "docs/methodology.md").read_text(encoding="utf-8")
    for statement in (
        "portfolio-weighted selection effect",
        "selection and interaction",
        "does not report a separate interaction column",
    ):
        if statement not in methodology:
            raise RuntimeError(
                f"Methodology omits the two-effect attribution contract: {statement}"
            )
    if "allocation, selection, and interaction effects" in methodology:
        raise RuntimeError("Methodology still describes a separate interaction effect.")

    markdown_link = re.compile(r"]\(([^)]+)\)")
    for relative in _ACTIVE_DOCUMENTATION:
        source = root / relative
        for match in markdown_link.finditer(source.read_text(encoding="utf-8")):
            target = match.group(1).split("#", maxsplit=1)[0]
            if not target or "://" in target:
                continue
            if not (source.parent / target).is_file():
                raise RuntimeError(f"Broken local link in {relative}: {target}")


def _stage_wheel_source(directory: Path) -> Path:
    """Copy only wheel build inputs into an isolated source directory."""
    directory.mkdir(parents=True)
    for name in _WHEEL_SOURCE_FILES:
        shutil.copy2(_ROOT / name, directory / name)
    shutil.copytree(_ROOT / "src", directory / "src")
    return directory


def _build_and_check_wheel(directory: Path, source_directory: Path) -> Path:
    """Build, inspect, and Twine-check one wheel without changing the checkout."""
    if directory.exists() and any(directory.iterdir()):
        raise RuntimeError(f"Wheel output directory is not empty: {directory}")
    source = _stage_wheel_source(source_directory)
    _run(list(_wheel_build_command(directory)), cwd=source)
    wheel = _inspect_wheel(directory)
    _run([sys.executable, "-m", "twine", "check", wheel])
    return wheel


def _inspect_wheel(directory: Path) -> Path:
    """Validate and return exactly one universal ppar wheel in ``directory``."""
    wheels = list(directory.glob("*.whl"))
    if len(wheels) != 1 or not wheels[0].name.endswith("-py3-none-any.whl"):
        raise RuntimeError(f"Expected one universal wheel, found: {wheels}")
    if list(directory.glob("*.tar.gz")):
        raise RuntimeError("The direct-wheel gate must not create an sdist.")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    if not any(name.startswith("ppar/") for name in names):
        raise RuntimeError("Wheel does not contain the ppar package.")
    forbidden = [
        name
        for name in names
        if name.startswith(("perfaud/", "tests/", "scripts/"))
        or "/__pycache__/" in name
    ]
    if forbidden:
        raise RuntimeError(f"Wheel contains forbidden files: {forbidden}")
    if not _REQUIRED_WHEEL_RESOURCES.issubset(names):
        raise RuntimeError(
            "Wheel is missing resources: "
            f"{sorted(_REQUIRED_WHEEL_RESOURCES - names)}"
        )
    return wheel


def _installed_package_workflow_smoke(wheel: Path, directory: Path) -> None:
    """Run the installed package against the verified development dependencies."""
    expected_version = wheel.name.split("-", maxsplit=2)[1]
    environment = directory / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = _venv_command(environment, "python")
    pip = _venv_command(environment, "pip")
    _run([pip, "install", "--no-deps", wheel], cwd=directory)
    smoke = directory / "smoke"
    smoke.mkdir()
    dependency_paths = [
        path
        for path in sys.path
        if "site-packages" in path and Path(path).is_dir()
    ]
    if not dependency_paths:
        raise RuntimeError("Could not locate the product-gate dependency environment.")
    smoke_env = os.environ.copy()
    smoke_env["PYTHONPATH"] = os.pathsep.join(dependency_paths)
    code = (
        "from pathlib import Path; import importlib.util, ppar; "
        "origin=Path(ppar.__file__).resolve(); "
        "assert 'site-packages' in str(origin), origin; "
        "assert importlib.util.find_spec('perfaud') is None; "
        "assert ppar.__all__ == ['Analytics', '__version__']; "
        f"assert ppar.__version__ == {expected_version!r}, ppar.__version__; "
        "print(origin)"
    )
    _run([python, "-c", code], cwd=smoke, env=smoke_env)
    _run([python, "-m", "pip", "check"], cwd=smoke, env=smoke_env)
    _run([python, "-m", "ppar.cli", "--version"], cwd=smoke, env=smoke_env)
    for name, axys_apx in (("generic", False), ("axys", True)):
        workspace = smoke / name
        setup_command: list[str | Path] = [
            python,
            "-m",
            "ppar.cli",
            "setup",
            workspace,
        ]
        if axys_apx:
            setup_command.append("--axys-apx")
        _run(setup_command, cwd=smoke, env=smoke_env)
        _run([python, workspace / "ppar_demo.py"], cwd=smoke, env=smoke_env)
        artifacts = [path for path in (workspace / "output").iterdir() if path.is_file()]
        if len(artifacts) != 11:
            raise RuntimeError(
                f"Installed {name} workflow wrote {len(artifacts)} artifacts, not 11."
            )


def main(argv: Sequence[str] | None = None) -> int:
    """Run tests, static checks, drift checks, and installed-wheel acceptance."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    for command in _routine_commands(sys.executable):
        _run(list(command))
    _check_documentation()
    _run([sys.executable, "scripts/render_readme_images.py", "--check"])
    with tempfile.TemporaryDirectory(prefix="ppar_product_gate_") as directory:
        temporary = Path(directory)
        wheel_output = (
            args.wheel_output.resolve()
            if args.wheel_output is not None
            else temporary / "dist"
        )
        wheel = _build_and_check_wheel(wheel_output, temporary / "wheel-source")
        _installed_package_workflow_smoke(wheel, temporary)
    print("ppar product gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
