"""Configure persistent environment state required by static chart rendering."""

from __future__ import annotations

from collections.abc import MutableMapping
import os
from pathlib import Path
import sys
import tempfile


def user_cache_root(
    environment: MutableMapping[str, str],
    home: Path,
    platform_name: str,
    operating_system: str,
) -> Path:
    """Return ppar's persistent platform-appropriate user cache directory.

    Args:
        environment: Process environment used to honor an explicit XDG cache root.
        home: Current user's home directory.
        platform_name: Python platform identifier such as ``"darwin"``.
        operating_system: Python operating-system name such as ``"nt"``.

    Returns:
        Persistent per-user cache root for ppar.
    """
    xdg_cache = environment.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "ppar"
    if platform_name == "darwin":
        return home / "Library" / "Caches" / "ppar"
    if operating_system == "nt":
        local_app_data = environment.get("LOCALAPPDATA")
        windows_cache = (
            Path(local_app_data).expanduser()
            if local_app_data
            else home / "AppData" / "Local"
        )
        return windows_cache / "ppar" / "Cache"
    return home / ".cache" / "ppar"


def configure_matplotlib_cache(
    environment: MutableMapping[str, str],
    *,
    home: Path,
    platform_name: str,
    operating_system: str,
    temporary_directory: Path,
) -> Path:
    """Select a persistent writable Matplotlib cache without overriding callers.

    Args:
        environment: Process environment to inspect and update.
        home: Current user's home directory.
        platform_name: Python platform identifier such as ``"darwin"``.
        operating_system: Python operating-system name such as ``"nt"``.
        temporary_directory: Writable fallback root when the user cache is not
            available.

    Returns:
        Effective Matplotlib configuration directory.
    """
    if "MPLCONFIGDIR" in environment:
        return Path(environment["MPLCONFIGDIR"]).expanduser()

    cache = user_cache_root(environment, home, platform_name, operating_system)
    cache = cache / "matplotlib"
    try:
        _prepare_writable_cache(cache)
    except OSError:
        cache = temporary_directory / "ppar_chart_cache" / "matplotlib"
        _prepare_writable_cache(cache)
    environment["MPLCONFIGDIR"] = str(cache)
    return cache


def _prepare_writable_cache(cache: Path) -> None:
    """Create a cache and prove that the current process can write there."""
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=cache,
        prefix=".ppar-cache-write-test-",
    ):
        pass


def configure_static_backend(environment: MutableMapping[str, str]) -> str:
    """Select Agg unless the caller has explicitly chosen a backend.

    Args:
        environment: Process environment to inspect and update.

    Returns:
        Effective ``MPLBACKEND`` environment value.
    """
    environment.setdefault("MPLBACKEND", "Agg")
    return environment["MPLBACKEND"]


def configure_current_process() -> Path:
    """Configure static rendering and return the current process cache."""
    configure_static_backend(os.environ)
    return configure_matplotlib_cache(
        os.environ,
        home=Path.home(),
        platform_name=sys.platform,
        operating_system=os.name,
        temporary_directory=Path(tempfile.gettempdir()),
    )
