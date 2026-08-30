"""Create self-contained portfolio analytics demonstration directories."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path
import shlex
import shutil
from typing import Final

from ppar.errors import PparError
import ppar.utilities as util

_TEMPLATE_NAMES: Final = {False: "generic", True: "axys_apx"}
_DEMO_PATH_PLACEHOLDER: Final = "__PPAR_DEMO_PATH__"


def setup(directory: util.PathLike, *, axys_apx: bool = False) -> Path:
    """Create one starter demonstration directory.

    Args:
        directory: Explicit destination directory.
        axys_apx: Select the Axys/APX template instead of the Generic default.

    Returns:
        Absolute created directory path.

    Raises:
        PparError: If the destination is not empty or the packaged template is
            incomplete.
    """
    destination = Path(directory).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise PparError(f"Directory is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    template_name = _TEMPLATE_NAMES[axys_apx]
    template = files("ppar").joinpath("templates", template_name)
    with as_file(template) as template_path:
        shutil.copytree(template_path, destination, dirs_exist_ok=True)
    demo_path = destination / "ppar_demo.py"
    if not demo_path.is_file():
        raise PparError("The packaged template does not contain ppar_demo.py.")
    _personalize_readme(destination / "README.md", demo_path)
    (destination / "output").mkdir()
    return destination


def _personalize_readme(readme_path: Path, demo_path: Path) -> None:
    """Replace the template token with one copy-and-paste demonstration path.

    Args:
        readme_path: Copied template README to personalize.
        demo_path: Absolute path to the copied demonstration script.

    Raises:
        PparError: If the README is missing or does not contain exactly one
            demonstration-path placeholder.
    """
    if not readme_path.is_file():
        raise PparError("The packaged template does not contain README.md.")
    contents = readme_path.read_text(encoding=util.ENCODING)
    if contents.count(_DEMO_PATH_PLACEHOLDER) != 1:
        raise PparError(
            "The packaged README must contain exactly one demo-path placeholder."
        )
    personalized = contents.replace(
        _DEMO_PATH_PLACEHOLDER,
        shlex.quote(str(demo_path)),
    )
    readme_path.write_text(personalized, encoding=util.ENCODING)
