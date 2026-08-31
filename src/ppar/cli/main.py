"""Expose the intentionally small ppar command surface."""

from __future__ import annotations

import argparse
import sys

from ppar import __version__
from ppar.cli.setup import setup
from ppar.errors import PparError


def main(argv: list[str] | None = None) -> int:
    """Run setup, help, or version commands.

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
    if args.command != "setup":
        parser.error(f"unknown command: {args.command}")
    try:
        directory = setup(args.directory, axys_apx=args.axys_apx)
        print(f"Directory: {directory}")
        if args.axys_apx:
            print("Data source: axys_apx")
        print()
        print(f"The next step is to read {directory / 'README.md'}.")
        print(
            "It contains instructions on how to run the demo and create reports "
            "using your own data."
        )
        print()
        return 0
    except (PparError, ValueError, OSError) as error:
        print(f"ppar: {error}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    """Return the complete command parser."""
    parser = argparse.ArgumentParser(
        prog="ppar",
        description=(
            "Portfolio performance attribution, contribution, and ex-post risk "
            "analytics."
        ),
        epilog=(
            "command form:\n"
            "  ppar setup DIRECTORY\n"
            "\n"
            "DIRECTORY is the local directory that setup creates and populates with\n"
            "demonstration inputs and an editable ppar_demo.py script.\n\n"
            "examples (choose one):\n"
            "  ppar setup ./my_ppar\n"
            "  ppar setup ./my_ppar --axys-apx"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
        add_help=False,
    )
    _add_help_argument(parser)
    parser.add_argument("--version", action="store_true", help="Show the ppar version.")
    commands = parser.add_subparsers(dest="command", title="commands")
    setup_parser = commands.add_parser(
        "setup",
        description="Create and populate a directory for running portfolio analytics.",
        epilog=(
            "examples (choose one):\n"
            "  ppar setup ./my_ppar\n"
            "  ppar setup ./my_ppar --axys-apx"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Create and populate a directory for running portfolio analytics.",
        allow_abbrev=False,
        add_help=False,
    )
    _add_help_argument(setup_parser)
    setup_parser.add_argument(
        "directory",
        metavar="DIRECTORY",
        help=(
            "Local directory to create and populate with demonstration inputs, "
            "an editable ppar_demo.py script, and an output folder."
        ),
    )
    setup_parser.add_argument(
        "--axys-apx",
        dest="axys_apx",
        action="store_true",
        help="Use Axys/APX export files instead of vendor-neutral CSV files.",
    )
    return parser


def _add_help_argument(parser: argparse.ArgumentParser) -> None:
    """Add the consistently styled help option to a command parser."""
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message.",
    )
