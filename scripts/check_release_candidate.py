"""Run the complete ppar release-candidate gate."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import subprocess
import sys


_ROOT = Path(__file__).resolve().parents[1]


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse an optional directory for retaining the validated wheel."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-output", type=Path)
    return parser.parse_args(argv)


def _run(command: list[str]) -> None:
    """Run one release check and stop on failure."""
    print(f"==> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=_ROOT, check=True)


def _release_commands(
    python: str,
    wheel_output: Path | None = None,
) -> tuple[tuple[str, ...], ...]:
    """Return the routine and unchanged 500x release command contract."""
    product_gate: tuple[str, ...] = (python, "scripts/check_project.py")
    if wheel_output is not None:
        product_gate += ("--wheel-output", str(wheel_output))
    return (
        product_gate,
        (python, "scripts/check_scale.py", "--scale", "500"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Compose the routine product gate with the unchanged 500x scale gate."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    for command in _release_commands(sys.executable, args.wheel_output):
        _run(list(command))
    print("ppar release-candidate gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
