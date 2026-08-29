"""Publish a complete directory of generated reports atomically.

The context manager in this module lets applications write a full report bundle
to a temporary sibling directory. Only a successful context replaces the public
output directory, so a failed calculation leaves the last successful bundle
untouched.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile

import ppar.utilities as util


@contextmanager
def atomic_output_directory(output_directory: util.PathLike) -> Iterator[Path]:
    """Yield a staging directory and atomically publish it on success.

    Args:
        output_directory: Directory that should contain the completed report
            bundle. Its parent is created when necessary.

    Yields:
        Empty temporary directory in which the caller should write every file
        in the new report bundle.

    Raises:
        OSError: If the staging directory cannot be created or the completed
            bundle cannot be published. If publication fails, the prior output
            is restored whenever it existed.

    Notes:
        Files must not be retained in the staging directory after the context
        exits because the staging path is renamed to ``output_directory``.
    """
    output = Path(output_directory).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}-staging-", dir=output.parent)
    )
    try:
        yield staging
        _publish(staging, output)
    except Exception:
        _remove(staging)
        raise


def _publish(staging: Path, output: Path) -> None:
    """Replace ``output`` with ``staging`` while preserving rollback safety."""
    backup = Path(tempfile.mkdtemp(prefix=f".{output.name}-backup-", dir=output.parent))
    backup.rmdir()
    if output.exists():
        os.replace(output, backup)
    try:
        os.replace(staging, output)
    except Exception:
        if backup.exists():
            os.replace(backup, output)
        raise
    _remove(backup)


def _remove(path: Path) -> None:
    """Remove a temporary file or directory when it still exists."""
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink(missing_ok=True)
