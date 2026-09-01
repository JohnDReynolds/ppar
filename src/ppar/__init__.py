"""Portfolio performance attribution, contribution, and ex-post risk analytics."""

from importlib.metadata import PackageNotFoundError, version

from ppar.core import Analytics

try:
    __version__ = version("ppar")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["Analytics", "__version__"]
