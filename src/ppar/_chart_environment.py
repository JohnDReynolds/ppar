"""Configure reusable cache state required by static chart rendering."""

from __future__ import annotations

from collections.abc import MutableMapping
import os
from pathlib import Path
import sys
import tempfile


def _native_matplotlib_directories(
    environment: MutableMapping[str, str],
    home: Path,
    platform_name: str,
) -> tuple[Path, Path]:
    """Return the configuration and cache directories Matplotlib would select."""
    if platform_name.startswith(("linux", "freebsd")):
        configuration_root = environment.get("XDG_CONFIG_HOME")
        cache_root = environment.get("XDG_CACHE_HOME")
        configuration = (
            Path(configuration_root) if configuration_root else home / ".config"
        )
        cache = Path(cache_root) if cache_root else home / ".cache"
        return configuration / "matplotlib", cache / "matplotlib"
    native = home / ".matplotlib"
    return native, native


def _temporary_matplotlib_directory(temporary_directory: Path) -> Path:
    """Return a stable per-user fallback below the operating-system temporary root."""
    user_suffix = f"-{os.getuid()}" if hasattr(os, "getuid") else ""
    return temporary_directory / f"ppar_chart_cache{user_suffix}" / "matplotlib"


def _prepare_writable_directory(directory: Path) -> None:
    """Create a directory and prove that the current process can write to it."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=directory,
        prefix=".ppar-cache-write-test-",
    ):
        pass


def _configure_matplotlib_cache(
    environment: MutableMapping[str, str],
    *,
    home: Path,
    platform_name: str,
    temporary_directory: Path,
) -> Path:
    """Preserve native cache behavior or select a reusable writable fallback.

    Args:
        environment: Process environment to inspect and conditionally update.
        home: Current user's home directory.
        platform_name: Python platform identifier such as ``"darwin"``.
        temporary_directory: Stable writable fallback root.

    Returns:
        The explicit, native, or fallback Matplotlib configuration directory.

    Notes:
        An explicit ``MPLCONFIGDIR`` is authoritative even when ppar cannot write
        to it. If neither the native directory nor the fallback can be prepared,
        the environment remains unchanged so Matplotlib can apply its own policy.
    """
    explicit_directory = environment.get("MPLCONFIGDIR")
    if explicit_directory:
        return Path(explicit_directory)

    native_configuration, native_cache = _native_matplotlib_directories(
        environment,
        home,
        platform_name,
    )
    try:
        for directory in dict.fromkeys((native_configuration, native_cache)):
            _prepare_writable_directory(directory)
    except OSError:
        fallback_directory = _temporary_matplotlib_directory(temporary_directory)
        try:
            _prepare_writable_directory(fallback_directory)
        except OSError:
            return native_configuration
        environment["MPLCONFIGDIR"] = str(fallback_directory)
        return fallback_directory
    return native_configuration


def configure_current_process() -> Path:
    """Configure Matplotlib caching before importing Matplotlib."""
    return _configure_matplotlib_cache(
        os.environ,
        home=Path.home(),
        platform_name=sys.platform,
        temporary_directory=Path(tempfile.gettempdir()),
    )
