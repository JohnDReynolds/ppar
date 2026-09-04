"""Load Axys classification sources for reconciled portfolios."""

from __future__ import annotations

# Python imports
from dataclasses import dataclass
# Third-party imports
import polars as pl

# Project imports
from ppar._perfattr_adapter import normalize_classification_source
from ppar.axys_apx.classification_sources import AxysClassificationSourceLoader
from ppar.axys_apx.portfolios import AxysPortfolio
from ppar.axys_apx.specification import _AxysSpecification
import ppar.schema as cols
from ppar.errors import PparError


@dataclass(frozen=True)
class AxysClassificationSources:
    """Contain one classification and its optional mapping source.

    Attributes:
        classification_name: Display name for the requested Axys
            classification.
        classification_data_source: Normalized classification source.
        mapping_data_sources: Mapping sources aligned to portfolio and benchmark
            performance for analytics attribution calls, or ``None`` when the
            requested classification is already at security grain. A source loaded
            for one portfolio repeats its mapping on both sides.
    """

    classification_name: str
    classification_data_source: pl.DataFrame
    mapping_data_sources: tuple[pl.DataFrame, pl.DataFrame] | None


def combine_classification_sources(
    portfolio_sources: AxysClassificationSources,
    benchmark_sources: AxysClassificationSources,
) -> AxysClassificationSources:
    """Combine portfolio and benchmark sources for one attribution calculation.

    Args:
        portfolio_sources: Classification and mapping sources restricted to the
            portfolio's security identifiers.
        benchmark_sources: Classification and mapping sources restricted to the
            benchmark's security identifiers.

    Returns:
        One classification source containing the union of portfolio and benchmark
        classification items and mappings kept in portfolio/benchmark order.

    Raises:
        PparError: If the sources represent different classifications or only one
            source contains mappings.
    """
    if portfolio_sources.classification_name != benchmark_sources.classification_name:
        raise PparError(
            f"portfolio={portfolio_sources.classification_name!r}, "
            f"benchmark={benchmark_sources.classification_name!r}",
        )

    normalized_classification = normalize_classification_source(
        pl.concat(
            [
                portfolio_sources.classification_data_source,
                benchmark_sources.classification_data_source,
            ],
            how="vertical",
        ),
        source_description="Combined Axys classification data",
    )
    classification_data_source = pl.DataFrame(
        {
            cols.IDENTIFIER: normalized_classification[
                "classification_identifier"
            ].to_numpy(),
            cols.NAME: normalized_classification[
                "classification_name"
            ].to_numpy(),
        }
    )
    mapping_data_sources = _combine_mapping_sources(
        portfolio_sources,
        benchmark_sources,
    )
    return AxysClassificationSources(
        portfolio_sources.classification_name,
        classification_data_source,
        mapping_data_sources,
    )


def _combine_mapping_sources(
    portfolio_sources: AxysClassificationSources,
    benchmark_sources: AxysClassificationSources,
) -> tuple[pl.DataFrame, pl.DataFrame] | None:
    """Return mapping sources aligned to portfolio and benchmark performance."""
    if (
        portfolio_sources.mapping_data_sources is None
        and benchmark_sources.mapping_data_sources is None
    ):
        return None
    if (
        portfolio_sources.mapping_data_sources is None
        or benchmark_sources.mapping_data_sources is None
    ):
        raise PparError(
            "Portfolio and benchmark mapping sources must both be present or "
            "both be omitted.",
        )
    return (
        portfolio_sources.mapping_data_sources[0],
        benchmark_sources.mapping_data_sources[0],
    )


class AxysSupportingSourceLoader:
    """Load one classification and its optional mapping source.

    Attributes:
        _specification: Parsed Axys source configuration.
        _loader: Source loader used to normalize configured source files.
    """

    def __init__(
        self,
        specification: _AxysSpecification,
        loader: AxysClassificationSourceLoader,
    ) -> None:
        """Initialize a supporting-source loader.

        Args:
            specification: Validated focused Axys/APX source configuration.
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
        if classification_name == "Security":
            mapping_data_sources = None
        else:
            mapping = self._loader.load(
                "mapping",
                classification_name,
                unique_security_ids,
            )
            mapping_data_sources = (mapping, mapping)
        return AxysClassificationSources(
            classification_name,
            classification,
            mapping_data_sources,
        )
