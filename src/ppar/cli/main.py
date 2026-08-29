"""Expose the intentionally small ppar command surface."""

from __future__ import annotations

import argparse
import sys

from ppar import __version__
from ppar.cli.setup import setup
from ppar.errors import PparError
from ppar.workspace import run


def main(argv: list[str] | None = None) -> int:
    """Run setup, run, help, or version commands.

    Args:
        argv: Arguments excluding the executable name.

    Returns:
        Zero for success and one for an expected product error. Argparse uses
        exit status two for command syntax errors.
    """
    parser = _parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"ppar {__version__}")
        return 0
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "setup":
            workspace = setup(args.workspace, generic=args.generic)
            source = "generic" if args.generic else "axys_apx"
            print(f"Workspace: {workspace}")
            print(f"Source: {source}")
            print(f"Configuration: {workspace / 'ppar.yaml'}")
            print(f"Next: ppar run {workspace}")
            return 0
        result = run(args.workspace)
        print(f"Workspace: {result.workspace}")
        print(f"Output: {result.output_directory}")
        for artifact in result.artifacts:
            print(f"Artifact: {artifact}")
        return 0
    except (PparError, ValueError, OSError) as error:
        print(f"ppar: {error}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    """Return the complete command parser."""
    parser = argparse.ArgumentParser(prog="ppar", allow_abbrev=False)
    parser.add_argument("--version", action="store_true")
    commands = parser.add_subparsers(dest="command")
    setup_parser = commands.add_parser("setup", allow_abbrev=False)
    setup_parser.add_argument("workspace")
    setup_parser.add_argument("--generic", action="store_true")
    run_parser = commands.add_parser("run", allow_abbrev=False)
    run_parser.add_argument("workspace", nargs="?", default=".")
    return parser
