"""Run the complete ppar release-candidate gate."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


_ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str]) -> None:
    """Run one release check and stop on failure."""
    print(f"==> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=_ROOT, check=True)


def main() -> int:
    """Compose the routine product gate with the unchanged 500x scale gate."""
    _run([sys.executable, "scripts/check_project.py"])
    _run([sys.executable, "scripts/check_scale.py", "--scale", "500"])
    print("ppar release-candidate gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
