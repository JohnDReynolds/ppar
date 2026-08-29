"""Expose Axys/APX Analytics adapters without eager optional imports."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ppar.axys_apx.data import AxysData
    from ppar.axys_apx.portfolios import AxysPortfolio
    from ppar.axys_apx.specification import AxysSpecification
    from ppar.axys_apx.supporting_sources import AxysClassificationSources

_EXPORT_MODULES = {
    "AxysClassificationSources": "ppar.axys_apx.supporting_sources",
    "AxysData": "ppar.axys_apx.data",
    "AxysPortfolio": "ppar.axys_apx.portfolios",
    "AxysSpecification": "ppar.axys_apx.specification",
}

__all__ = [
    "AxysClassificationSources",
    "AxysData",
    "AxysPortfolio",
    "AxysSpecification",
]


def __getattr__(name: str) -> Any:
    """Return one lazily imported Axys/APX adapter.

    Args:
        name: Package attribute requested by an importer.

    Returns:
        Requested public adapter.

    Raises:
        AttributeError: If ``name`` is not a public adapter.
    """
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
