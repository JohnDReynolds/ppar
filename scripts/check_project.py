"""Run the complete routine ppar product gate."""

from __future__ import annotations

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
    "docs/configuration.md",
    "docs/methodology.md",
    "docs/python_api.md",
    "docs/maintenance.md",
)


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


def _check_documentation() -> None:
    """Check the small documentation spine and executable demonstration references."""
    for relative in _ACTIVE_DOCUMENTATION:
        if not (_ROOT / relative).is_file():
            raise RuntimeError(f"Missing active documentation: {relative}")
    configuration = (_ROOT / "docs/configuration.md").read_text(encoding="utf-8")
    for value in (
        "ppar_demo.py",
        "AxysData.from_values()",
        "CLASSIFICATION_VIEWS",
        "portperf.csv",
        "secperf.csv",
        "secmast.csv",
    ):
        if value not in configuration:
            raise RuntimeError(f"Demonstration documentation omits {value}.")
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    for command in (
        "ppar setup ./my_ppar",
        "ppar setup ./my_ppar --axys-apx",
        "python ./my_ppar/ppar_demo.py",
    ):
        if command not in readme:
            raise RuntimeError(f"README omits executable command: {command}")

    methodology = (_ROOT / "docs/methodology.md").read_text(encoding="utf-8")
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

    active_text = "\n".join(
        (_ROOT / relative).read_text(encoding="utf-8")
        for relative in _ACTIVE_DOCUMENTATION
    )
    for retired_term in ("Generic", "my_ppar_axys_apx"):
        if retired_term in active_text:
            raise RuntimeError(
                f"Active documentation contains retired terminology: {retired_term}"
            )

    if (_ROOT / "docs/reference").exists():
        raise RuntimeError("The removed parallel reference directory is still present.")

    markdown_link = re.compile(r"]\(([^)]+)\)")
    for relative in _ACTIVE_DOCUMENTATION:
        source = _ROOT / relative
        for match in markdown_link.finditer(source.read_text(encoding="utf-8")):
            target = match.group(1).split("#", maxsplit=1)[0]
            if not target or "://" in target:
                continue
            if not (source.parent / target).is_file():
                raise RuntimeError(f"Broken local link in {relative}: {target}")


def _build_and_check_wheel(directory: Path) -> Path:
    """Build, inspect, and Twine-check exactly one direct universal wheel."""
    shutil.rmtree(_ROOT / "build", ignore_errors=True)
    shutil.rmtree(_ROOT / "src" / "ppar.egg-info", ignore_errors=True)
    _run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            directory,
        ]
    )
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
        or name.startswith("ppar/analytics/")
        or name.startswith("ppar/audit/")
    ]
    if forbidden:
        raise RuntimeError(f"Wheel contains forbidden files: {forbidden}")
    required_resources = {
        "ppar/py.typed",
        "ppar/templates/axys_apx/ppar_demo.py",
        "ppar/templates/axys_apx/README.md",
        "ppar/templates/axys_apx/input/portperf.csv",
        "ppar/templates/generic/ppar_demo.py",
        "ppar/templates/generic/README.md",
        "ppar/templates/generic/input/performance/Mega-Cap Alpha Portfolio.csv",
    }
    if not required_resources.issubset(names):
        raise RuntimeError(
            f"Wheel is missing resources: {sorted(required_resources - names)}"
        )
    _run([sys.executable, "-m", "twine", "check", wheel])
    return wheel


def _installed_wheel_smoke(wheel: Path, directory: Path) -> None:
    """Run both installed workflows outside the checkout with no perfaud available."""
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


def main() -> int:
    """Run tests, static checks, drift checks, and installed-wheel acceptance."""
    _run([sys.executable, "-m", "pytest", "-q"])
    _run([sys.executable, "-m", "mypy", "src/ppar", "scripts"])
    _run(
        [
            sys.executable,
            "-m",
            "pyright",
            "--pythonpath",
            sys.executable,
            "src/ppar",
            "tests",
        ]
    )
    _run(
        [
            sys.executable,
            "-m",
            "pylint",
            "--errors-only",
            "src/ppar",
            "scripts",
            "tests",
        ]
    )
    _check_documentation()
    _run([sys.executable, "scripts/render_readme_images.py", "--check"])
    with tempfile.TemporaryDirectory(prefix="ppar_product_gate_") as directory:
        temporary = Path(directory)
        wheel = _build_and_check_wheel(temporary / "dist")
        _installed_wheel_smoke(wheel, temporary)
    print("ppar product gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
