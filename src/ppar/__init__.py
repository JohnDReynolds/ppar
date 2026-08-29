"""Portfolio performance Analytics for generic and Axys/APX data."""

from importlib.metadata import PackageNotFoundError, version

from ppar.core import Analytics

try:
    __version__ = version("ppar")
except PackageNotFoundError:
    __version__ = "0.2.0"

__all__ = ["Analytics", "__version__"]
