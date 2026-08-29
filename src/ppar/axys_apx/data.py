"""Load Axys sources for use by the analytics facade.

This module provides the public ``AxysData`` facade for configured Axys/APX
portfolio and benchmark source loading.
"""

from __future__ import annotations

# Python imports
from collections.abc import Mapping, Sequence
from dataclasses import replace
import datetime as dt
from pathlib import Path
from typing import Any

# Project imports
from ppar.axys_apx.classification_sources import AxysClassificationSourceLoader
from ppar.axys_apx.date_ranges import AxysDateRange
from ppar.axys_apx.performance_sources import AxysPerformanceSourceLoader
from ppar.axys_apx.portfolios import AxysPortfolio, AxysPortfolioLoader
from ppar.axys_apx.specification import AxysSpecification
from ppar.axys_apx.supporting_sources import (
    AxysClassificationSources,
    AxysSupportingSourceLoader,
)
from ppar.errors import PparError
import ppar.utilities as util


class AxysData:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Configure Axys inputs and expose portfolio/classification loaders.

    ``AxysData`` remains the public construction facade. Specification parsing
    happens during initialization; portfolio reconciliation and supporting
    source loading happen on demand.

    Attributes:
        specifications_path: Path to the Axys YAML specification file.
        specifications: Parsed specification settings.
        portfolio_performance_path: Resolved portfolio-performance CSV path.
        security_performance_path: Resolved security-performance CSV path.
        _specification: Parsed Axys specification object.
        _classification_loader: Loader used to normalize classification and
            mapping sources.
        _supporting_source_loader: Loader used to resolve classification
            sources on demand.
    """

    def __init__(
        self,
        specifications_path: util.PathLike,
        portfolio_performance_path: util.PathLike | None = None,
        security_performance_path: util.PathLike | None = None,
        source_path_overrides: Mapping[str, util.PathLike] | None = None,
        specification_values: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize Axys source configuration.

        Args:
            specifications_path: YAML file describing Axys source paths,
                source-column mappings, classifications, and mappings.
            portfolio_performance_path: Optional portfolio-performance CSV
                path overriding the specification setting.
            security_performance_path: Optional security-performance CSV path
                overriding the specification setting.
            source_path_overrides: Optional classification source file paths
                keyed by source name. These override configured
                ``file_path`` values for explicit classification sources.
            specification_values: Already-loaded canonical configuration used
                to avoid rereading YAML during a workspace run.

        Raises:
            PparError: If a source path override references an unknown source.
        """
        self.specifications_path = Path(specifications_path)
        specification = AxysSpecification(
            specifications_path,
            self._error_message,
            specification_values,
        )
        self._initialize(
            Path(specifications_path),
            specification,
            portfolio_performance_path,
            security_performance_path,
            source_path_overrides,
        )

    @classmethod
    def from_values(
        cls,
        base_directory: util.PathLike,
        values: Mapping[str, object],
        *,
        portfolio_performance_path: util.PathLike | None = None,
        security_performance_path: util.PathLike | None = None,
        source_path_overrides: Mapping[str, util.PathLike] | None = None,
    ) -> AxysData:
        """Create an Axys/APX loader from Python values without YAML.

        Args:
            base_directory: Directory against which relative source paths are
                resolved.
            values: Source paths, source-column mappings, classifications, and
                mappings expressed as ordinary Python values.
            portfolio_performance_path: Optional portfolio-performance CSV
                path overriding ``values``.
            security_performance_path: Optional security-performance CSV path
                overriding ``values``.
            source_path_overrides: Optional classification source paths keyed
                by source name.

        Returns:
            Configured Axys/APX source loader.

        Raises:
            PparError: If the values or source overrides are invalid.

        Examples:
            ``AxysData.from_values(Path(__file__).parent, {"files": {...}})``
            resolves relative file paths beside the calling script.
        """
        instance = cls.__new__(cls)
        resolved_base = Path(base_directory).expanduser().resolve()
        instance.specifications_path = resolved_base
        specification = AxysSpecification.from_values(
            resolved_base,
            instance._error_message,
            values,
        )
        instance._initialize(
            resolved_base,
            specification,
            portfolio_performance_path,
            security_performance_path,
            source_path_overrides,
        )
        return instance

    def _initialize(
        self,
        specifications_path: Path,
        specification: AxysSpecification,
        portfolio_performance_path: util.PathLike | None,
        security_performance_path: util.PathLike | None,
        source_path_overrides: Mapping[str, util.PathLike] | None,
    ) -> None:
        """Initialize shared state for file-based and Python-value construction."""
        self.specifications_path = specifications_path
        self._specification = specification
        self.specifications = self._specification.values
        self.portfolio_performance_path = self._specification.performance_path(
            portfolio_performance_path, "portfolio_performance"
        )
        self.security_performance_path = self._specification.performance_path(
            security_performance_path, "security_performance"
        )
        self._classification_loader = AxysClassificationSourceLoader(
            self._specification,
            self._error_message,
            source_path_overrides,
        )
        self._supporting_source_loader = AxysSupportingSourceLoader(
            self._specification,
            self._classification_loader,
        )

    def get_portfolio(
        self,
        portfolio_code: str,
        from_date: dt.date | None = None,
        thru_date: dt.date | None = None,
        classification_name: str | None = None,
    ) -> AxysPortfolio:
        """Return one reconciled Axys portfolio for an optional date window.

        Args:
            portfolio_code: Portfolio code to load from Axys performance
                sources.
            from_date: Optional inclusive earliest from date to retain.
            thru_date: Optional inclusive latest thru date to retain.
            classification_name: Optional configured Axys classification to
                load with the returned portfolio.

        Returns:
            Reconciled portfolio output, optionally including classification
            sources for the requested classification.

        Raises:
            PparError: If the requested portfolio has no rows, common periods
                cannot be found, or security returns cannot be reconciled to
                portfolio returns, or if the requested classification source is
                unknown or invalid.
        """
        return self.get_portfolios(
            (portfolio_code,),
            from_date=from_date,
            thru_date=thru_date,
            classification_name=classification_name,
        )[portfolio_code]

    def get_portfolios(
        self,
        portfolio_codes: Sequence[str],
        from_date: dt.date | None = None,
        thru_date: dt.date | None = None,
        classification_name: str | None = None,
    ) -> dict[str, AxysPortfolio]:
        """Return requested reconciled portfolios from one source scan per file.

        Args:
            portfolio_codes: Portfolio codes to load together.
            from_date: Optional inclusive earliest from date to retain.
            thru_date: Optional inclusive latest thru date to retain.
            classification_name: Optional configured Axys classification to
                attach to each returned portfolio.

        Returns:
            Reconciled portfolios keyed by requested portfolio code.

        Raises:
            PparError: If any requested portfolio has no rows, common periods
                cannot be found, security returns cannot be reconciled, or the
                requested classification source is invalid.
        """
        requested_codes = (
            (portfolio_codes,)
            if isinstance(portfolio_codes, str)
            else tuple(dict.fromkeys(portfolio_codes))
        )
        if not requested_codes:
            return {}
        date_range = AxysDateRange(
            from_date or self._specification.default_from_date,
            thru_date or self._specification.default_thru_date,
        )
        resolved_classification_name = (
            classification_name or self._specification.default_classification_name
        )
        portfolios = self._portfolio_loader(date_range).load(requested_codes)
        for portfolio_code in requested_codes:
            if portfolio_code not in portfolios:
                raise PparError(
                    self._error_message(
                        f"No portfolio performance rows for portfolio {portfolio_code!r}",
                        portfolio_code,
                        date_range.from_date,
                        date_range.thru_date,
                    ),
                )
        if resolved_classification_name is None:
            return portfolios
        return {
            portfolio_code: replace(
                portfolio,
                classification_sources=self.get_classification_sources(
                    resolved_classification_name,
                    portfolio,
                ),
            )
            for portfolio_code, portfolio in portfolios.items()
        }

    def get_classification_sources(
        self,
        classification_name: str,
        portfolio: AxysPortfolio,
    ) -> AxysClassificationSources:
        """Return one Axys classification and its configured mapping source.

        Args:
            classification_name: Requested classification source name.
            portfolio: Reconciled portfolio whose security identifiers limit
                security-master sources.

        Returns:
            Classification source bundle ready for an attribution call.

        Raises:
            PparError: If the classification source is unknown, invalid, or
                references an invalid mapping source.
        """
        return self._supporting_source_loader.load_classification_sources(
            classification_name,
            portfolio,
        )

    def _portfolio_loader(
        self,
        date_range: AxysDateRange,
    ) -> AxysPortfolioLoader:
        """Return a portfolio loader for the requested date window.

        Args:
            date_range: Inclusive date window to retain.

        Returns:
            Portfolio loader using the configured performance paths and date
            filters.
        """
        def error_message(message: str, portfolio_code: str | None = None) -> str:
            """Return error context for this portfolio-loading request."""
            return self._error_message(
                message,
                portfolio_code,
                date_range.from_date,
                date_range.thru_date,
            )

        performance_loader = AxysPerformanceSourceLoader(
            self._specification,
            error_message,
            date_range,
        )
        return AxysPortfolioLoader(
            self._specification,
            performance_loader,
            error_message,
            self.portfolio_performance_path,
            self.security_performance_path,
        )

    def _error_message(
        self,
        specific_message: str,
        portfolio_code: str | None = None,
        from_date: dt.date | None = None,
        thru_date: dt.date | None = None,
    ) -> str:
        """Return an Axys error detail including source and filter context.

        Args:
            specific_message: Error-specific text to prefix to context.
            portfolio_code: Portfolio involved in the error, when known.
            from_date: Optional inclusive earliest from date requested.
            thru_date: Optional inclusive latest thru date requested.

        Returns:
            Error detail text including paths, portfolio code, and date filters.
        """
        context = (
            "Context: "
            f"specifications_path={self.specifications_path}, "
            "portfolio_performance_path="
            f"{getattr(self, 'portfolio_performance_path', None)}, "
            "security_performance_path="
            f"{getattr(self, 'security_performance_path', None)}, "
            f"portfolio_code={portfolio_code}, "
            f"from_date={from_date}, "
            f"thru_date={thru_date}"
        )
        return f"{specific_message}  |  {context}" if specific_message else context
