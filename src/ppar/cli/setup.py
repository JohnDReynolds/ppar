"""Create valid-by-construction Analytics workspaces."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
import shutil
from typing import Final

from ppar.config import settings
from ppar.errors import PparError
import ppar.utilities as util

_TEMPLATE_NAMES: Final = {False: "axys_apx", True: "generic"}


def setup(workspace: util.PathLike, *, generic: bool = False) -> Path:
    """Create and validate one starter workspace.

    Args:
        workspace: Explicit destination directory.
        generic: Select the vendor-neutral template instead of Axys/APX.

    Returns:
        Absolute created workspace path.

    Raises:
        PparError: If the destination is not empty or the copied template is
            invalid.
    """
    destination = Path(workspace).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise PparError(f"Workspace is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    template_name = _TEMPLATE_NAMES[generic]
    template = files("ppar").joinpath("templates", template_name)
    with as_file(template) as template_path:
        shutil.copytree(template_path, destination, dirs_exist_ok=True)
    settings(destination)
    (destination / "output").mkdir()
    return destination
