"""Load Axys classification sources for reconciled portfolios."""

from __future__ import annotations

# Python imports
from dataclasses import dataclass
from typing import cast

# Third-party imports
import polars as pl

# Project imports
from ppar.axys_apx.classification_sources import AxysClassificationSourceLoader
from ppar.axys_apx.portfolios import AxysPortfolio
from ppar.axys_apx.specification import AxysSpecification
import ppar.schema as cols


@dataclass(frozen=True)
class AxysClassificationSources:
    """Contain one classification and its optional mapping source.

    Attributes:
        classification_name: Display name for the requested Axys
            classification.
        classification_data_source: Normalized classification source.
        mapping_data_sources: Pair of identical mapping sources for analytics
            attribution calls, or ``None`` when the requested classification is
            already at security grain.
    """

    classification_name: str
    classification_data_source: pl.DataFrame
    mapping_data_sources: tuple[pl.DataFrame, pl.DataFrame] | None


class AxysSupportingSourceLoader:
    """Load one classification and its optional mapping source.

    Attributes:
        _specification: Parsed Axys source configuration.
        _loader: Source loader used to normalize configured source files.
    """

    def __init__(
        self,
        specification: AxysSpecification,
        loader: AxysClassificationSourceLoader,
    ) -> None:
        """Initialize a supporting-source loader.

        Args:
            specification: Parsed Axys configuration used to determine default
                source names.
            loader: Source loader used to normalize configured source files.
        """
        self._specification = specification
        self._loader = loader

    def load_classification_sources(
        self,
        classification_name: str,
        portfolio: AxysPortfolio,
    ) -> AxysClassificationSources:
        """Return one classification and its configured mapping source.

        Args:
            classification_name: Requested classification source name.
            portfolio: Reconciled portfolio whose security identifiers limit
                security-master sources.

        Returns:
            Classification source bundle ready for attribution calls.

        Raises:
            PparError: If the classification source is unknown, invalid, or
                references an invalid mapping source.
        """
        unique_security_ids = (
            portfolio.security_performance[cols.IDENTIFIER].unique().to_list()
        )
        classification = self._loader.load(
            "classification", classification_name, unique_security_ids
        )
        classification_source = self._specification.classifications.get(
            classification_name,
            {},
        )
        if self._specification.is_security_master(classification_name):
            mapping_data_sources = None
        else:
            mapping_name = classification_source.get("mapping", classification_name)
            mapping = self._loader.load("mapping", mapping_name, unique_security_ids)
            mapping_data_sources = (mapping, mapping)
        display_name = cast(
            str,
            classification_source.get(
                "display_name",
                classification_name,
            ),
        )
        return AxysClassificationSources(
            display_name,
            classification,
            mapping_data_sources,
        )
