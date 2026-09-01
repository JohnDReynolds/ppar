"""Load Axys sources for use by the analytics facade.

This module provides the public ``AxysData`` facade for configured Axys/APX
portfolio and benchmark source loading.
"""

from __future__ import annotations

# Python imports
from collections.abc import Mapping, Sequence
import datetime as dt
from pathlib import Path

# Project imports
from ppar.axys_apx.classification_sources import AxysClassificationSourceLoader
from ppar.axys_apx.date_ranges import AxysDateRange
from ppar.axys_apx.performance_sources import AxysPerformanceSourceLoader
from ppar.axys_apx.portfolios import AxysPortfolio, AxysPortfolioLoader
from ppar.axys_apx.specification import _AxysSpecification
from ppar.axys_apx.supporting_sources import (
    AxysClassificationSources,
    AxysSupportingSourceLoader,
    combine_classification_sources,
)
from ppar.errors import PparError
import ppar.utilities as util


class AxysData:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Configure Axys inputs and expose portfolio/classification loaders.

    Source-setting validation happens during initialization; portfolio
    reconciliation and supporting source loading happen on demand.

    Attributes:
        base_directory: Directory against which relative source paths resolve.
        source_values: Validated source settings.
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
        base_directory: str | Path,
        values: Mapping[str, object],
        *,
        portfolio_performance_path: str | Path | None = None,
        security_performance_path: str | Path | None = None,
    ) -> None:
        """Initialize Axys source configuration.

        Args:
            base_directory: Directory against which relative source paths are
                resolved.
            values: Source paths, source-column mappings, security-master
                classification mappings, and security-identity settings.
            portfolio_performance_path: Optional portfolio-performance CSV
                path overriding ``values``.
            security_performance_path: Optional security-performance CSV path
                overriding ``values``.
        Raises:
            PparError: If the source values are invalid.
        """
        self.base_directory = Path(base_directory).expanduser().resolve()
        specification = _AxysSpecification(
            self.base_directory,
            self._error_message,
            values,
        )
        self._specification = specification
        self.source_values = self._specification.values
        self.portfolio_performance_path = self._specification.performance_path(
            portfolio_performance_path, "portfolio_performance"
        )
        self.security_performance_path = self._specification.performance_path(
            security_performance_path, "security_performance"
        )
        self._classification_loader = AxysClassificationSourceLoader(
            self._specification,
            self._error_message,
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
    ) -> AxysPortfolio:
        """Return one reconciled Axys portfolio for an optional date window.

        Args:
            portfolio_code: Portfolio code to load from Axys performance
                sources.
            from_date: Optional earliest period ``thru_date`` to retain.
            thru_date: Optional latest period ``thru_date`` to retain.
        Returns:
            Reconciled portfolio output.

        Raises:
            PparError: If the requested portfolio has no rows, common periods
                cannot be found, or security returns cannot be reconciled to
                portfolio returns.
        """
        return self.get_portfolios(
            (portfolio_code,),
            from_date=from_date,
            thru_date=thru_date,
        )[portfolio_code]

    def get_portfolios(
        self,
        portfolio_codes: Sequence[str],
        from_date: dt.date | None = None,
        thru_date: dt.date | None = None,
    ) -> dict[str, AxysPortfolio]:
        """Return requested reconciled portfolios from one source scan per file.

        Args:
            portfolio_codes: Portfolio codes to load together.
            from_date: Optional earliest period ``thru_date`` to retain.
            thru_date: Optional latest period ``thru_date`` to retain.
        Returns:
            Reconciled portfolios keyed by requested portfolio code.

        Raises:
            PparError: If any requested portfolio has no rows, common periods
                cannot be found or security returns cannot be reconciled.
        """
        requested_codes = (
            (portfolio_codes,)
            if isinstance(portfolio_codes, str)
            else tuple(dict.fromkeys(portfolio_codes))
        )
        if not requested_codes:
            return {}
        date_range = AxysDateRange(from_date, thru_date)
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
        return portfolios

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
        resolved_classification_name = util.normalize_optional_string(
            classification_name,
            "classification_name",
        )
        if resolved_classification_name is None:
            raise PparError("classification_name is required.")
        return self._supporting_source_loader.load_classification_sources(
            resolved_classification_name,
            portfolio,
        )

    def get_classification_sources_for_pair(
        self,
        classification_name: str,
        portfolio: AxysPortfolio,
        benchmark: AxysPortfolio,
    ) -> AxysClassificationSources:
        """Return combined classification sources for a portfolio and benchmark.

        Args:
            classification_name: Requested classification source name.
            portfolio: Reconciled portfolio whose identifiers limit the first
                classification and mapping sources.
            benchmark: Reconciled benchmark whose identifiers limit the second
                classification and mapping sources.

        Returns:
            Classification items covering both accounts, with mapping sources kept
            in portfolio/benchmark order for an attribution call.

        Raises:
            PparError: If the classification source is unknown or invalid, or the
                resulting portfolio and benchmark sources are incompatible.
        """
        return combine_classification_sources(
            self.get_classification_sources(classification_name, portfolio),
            self.get_classification_sources(classification_name, benchmark),
        )

    def _portfolio_loader(
        self,
        date_range: AxysDateRange,
    ) -> AxysPortfolioLoader:
        """Return a portfolio loader for the requested period-end bounds.

        Args:
            date_range: Inclusive period ``thru_date`` bounds to retain.

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
            from_date: Optional earliest period ``thru_date`` requested.
            thru_date: Optional latest period ``thru_date`` requested.

        Returns:
            Error detail text including paths, portfolio code, and date filters.
        """
        context = (
            "Context: "
            f"base_directory={self.base_directory}, "
            "portfolio_performance_path="
            f"{getattr(self, 'portfolio_performance_path', None)}, "
            "security_performance_path="
            f"{getattr(self, 'security_performance_path', None)}, "
            f"portfolio_code={portfolio_code}, "
            f"from_date={from_date}, "
            f"thru_date={thru_date}"
        )
        return f"{specific_message}  |  {context}" if specific_message else context
