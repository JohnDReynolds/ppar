"""Load reconciled Axys portfolio performance outputs."""

from __future__ import annotations

# Python imports
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

# Third-party imports
import polars as pl

# Project imports
from ppar.axys_apx import reconciliation
from ppar.axys_apx.performance_sources import AxysPerformanceSourceLoader
from ppar.axys_apx.specification import _AxysSpecification
import ppar.schema as cols
from ppar.errors import PparError
from ppar.frequency import Frequency
import ppar.utilities as util

if TYPE_CHECKING:
    from ppar import Analytics

_ANALYTICS_REQUIRED_COLUMNS = {
    cols.FROM_DATE,
    cols.THRU_DATE,
    cols.IDENTIFIER,
    cols.RETURN,
    cols.WEIGHT,
}
_SECURITY_PERFORMANCE_CLASSIFICATION_NAME = "Security"
_PORTFOLIO_NAME_SEPARATOR = " - "
_PortfolioErrorMessage = Callable[[str, str | None], str]


def _partition_by_portfolio_code(
    performance: pl.DataFrame,
) -> dict[str, pl.DataFrame]:
    """Partition performance rows once while retaining normalized identity and order.

    Args:
        performance: Normalized portfolio- or security-performance rows containing
            validated string portfolio codes.

    Returns:
        DataFrames keyed by normalized portfolio code. Both partition order and row order
        within each partition follow the source frame.
    """
    partitions = performance.partition_by(
        cols.PORTFOLIO_CODE,
        maintain_order=True,
        include_key=True,
        as_dict=True,
    )
    return {
        cast(str, key[0]): partition
        for key, partition in partitions.items()
    }


def _portfolio_display_name(
    portfolio_code: str,
    portfolio_performance: pl.DataFrame,
) -> str:
    """Return the code-prefixed name from the latest retained period.

    Args:
        portfolio_code: Exact account code represented by the source rows.
        portfolio_performance: Validated retained rows for that account.

    Returns:
        Portfolio code and latest chronological display name joined by the
        established separator.
    """
    chronological = portfolio_performance.sort(
        [cols.THRU_DATE, cols.FROM_DATE]
    )
    latest_name = cast(str, chronological[-1, cols.PORTFOLIO_NAME])
    return f"{portfolio_code}{_PORTFOLIO_NAME_SEPARATOR}{latest_name}"


@dataclass(frozen=True)
class AxysPortfolio:
    """Contain one reconciled portfolio returned by AxysData.

    Application code normally obtains instances from
    :meth:`ppar.axys_apx.AxysData.get_portfolio` or
    :meth:`ppar.axys_apx.AxysData.get_portfolios`.

    Attributes:
        portfolio_code: Identifier used to select the portfolio in Axys sources.
        portfolio_name: Code-prefixed display name from the latest retained
            portfolio-performance period, supplied to analytics output.
        security_performance: Reconciled security-level performance rows
            accepted by :class:`ppar.Analytics`.
    """

    portfolio_code: str
    portfolio_name: str
    security_performance: pl.DataFrame

    def to_analytics(
        self,
        benchmark: AxysPortfolio | None = None,
        *,
        frequency: Frequency = Frequency.AS_OFTEN_AS_POSSIBLE,
        annual_minimum_acceptable_return: float = (
            util.DEFAULT_ANNUAL_MINIMUM_ACCEPTABLE_RETURN
        ),
        annual_risk_free_rate: float = util.DEFAULT_ANNUAL_RISK_FREE_RATE,
        confidence_level: float = util.DEFAULT_CONFIDENCE_LEVEL,
        portfolio_value: tuple[float, str] = (
            util.DEFAULT_PORTFOLIO_VALUE,
            util.DEFAULT_CURRENCY_SYMBOL,
        ),
        holidays: str | Path | None = None,
    ) -> Analytics:
        """Return an Analytics instance for this reconciled Axys portfolio.

        Args:
            benchmark: Optional reconciled Axys benchmark. When omitted,
                Analytics reuses the portfolio data as its benchmark.
            frequency: Reporting frequency used to consolidate subperiods.
            annual_minimum_acceptable_return: Annual minimum acceptable return used in
                downside-risk calculations.
            annual_risk_free_rate: Annual risk-free rate used in risk statistics that
                require a risk-free return.
            confidence_level: Confidence level used when calculating value at risk.
            portfolio_value: Tuple containing the portfolio value and its currency
                symbol for value-at-risk calculations.
            holidays: Optional path to a headerless, single-column holiday
                file used to determine effective reporting-period endpoints.

        Returns:
            Analytics instance initialized with this portfolio's reconciled
            security-performance rows and display name.

        Raises:
            PparError: If Analytics validation fails.
        """
        # Import lazily so Axys portfolio containers do not force analytics imports
        # unless the convenience adapter is used.
        from ppar import Analytics  # pylint: disable=import-outside-toplevel

        return Analytics(
            portfolio_data_source=self.security_performance,
            benchmark_data_source=(
                None if benchmark is None else benchmark.security_performance
            ),
            portfolio_name=self.portfolio_name,
            benchmark_name=None if benchmark is None else benchmark.portfolio_name,
            portfolio_classification_name=_SECURITY_PERFORMANCE_CLASSIFICATION_NAME,
            benchmark_classification_name=(
                None if benchmark is None else _SECURITY_PERFORMANCE_CLASSIFICATION_NAME
            ),
            frequency=frequency,
            annual_minimum_acceptable_return=annual_minimum_acceptable_return,
            annual_risk_free_rate=annual_risk_free_rate,
            confidence_level=confidence_level,
            portfolio_value=portfolio_value,
            holidays=holidays,
        )

class AxysPortfolioLoader:  # pylint: disable=too-few-public-methods
    """Load and reconcile requested Axys portfolios.

    Attributes:
        _specification: Parsed Axys source configuration.
        _loader: Source loader used to read portfolio and security performance.
        _error_message: Callback used to add facade-level validation context.
        _portfolio_performance_path: Portfolio-performance CSV path.
        _security_performance_path: Security-performance CSV path.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        specification: _AxysSpecification,
        loader: AxysPerformanceSourceLoader,
        error_message: _PortfolioErrorMessage,
        portfolio_performance_path: util.PathLike,
        security_performance_path: util.PathLike,
    ) -> None:
        """Initialize a portfolio loader.

        Args:
            specification: Parsed Axys configuration used for display-name
                settings.
            loader: Source loader used to read portfolio and security data.
            error_message: Callback used to add facade-level source context.
            portfolio_performance_path: Portfolio-performance CSV path.
            security_performance_path: Security-performance CSV path.
        """
        self._specification = specification
        self._loader = loader
        self._error_message = error_message
        self._portfolio_performance_path = portfolio_performance_path
        self._security_performance_path = security_performance_path

    def load(self, portfolio_codes: tuple[str, ...] | None) -> dict[str, AxysPortfolio]:
        """Return reconciled security performance for requested portfolios.

        Args:
            portfolio_codes: Portfolio codes to load, or ``None`` to discover
                all codes from the portfolio-performance source.

        Returns:
            Reconciled portfolio output keyed by portfolio code.

        Raises:
            PparError: If source-data rows cannot be loaded, common periods cannot be
                found, or security returns cannot be reconciled to portfolio
                returns.
        """
        requested_codes = tuple(dict.fromkeys(portfolio_codes or ()))
        portfolio_performance = self._loader.load(
            self._portfolio_performance_path,
            "portfolio_performance_columns",
            requested_codes or None,
        )
        if not requested_codes:
            requested_codes = tuple(
                portfolio_performance[cols.PORTFOLIO_CODE].unique().sort().to_list()
            )
        available_codes = set(
            portfolio_performance[cols.PORTFOLIO_CODE].unique().to_list()
        )
        load_codes = tuple(
            portfolio_code
            for portfolio_code in requested_codes
            if portfolio_code in available_codes
        )
        if not load_codes:
            return {}
        if len(load_codes) == 1:
            portfolio_code = load_codes[0]
            security_performance = self._loader.load(
                self._security_performance_path,
                "security_performance_columns",
                load_codes,
            )
            return {
                portfolio_code: self._reconcile_one(
                    portfolio_code,
                    portfolio_performance,
                    security_performance,
                )
            }

        portfolio_partitions = _partition_by_portfolio_code(portfolio_performance)
        del portfolio_performance

        security_performance = self._loader.load(
            self._security_performance_path,
            "security_performance_columns",
            load_codes,
        )
        empty_security_performance = security_performance.clear()
        security_partitions = _partition_by_portfolio_code(security_performance)
        del security_performance

        portfolios: dict[str, AxysPortfolio] = {}
        for portfolio_code in load_codes:
            portfolios[portfolio_code] = self._reconcile_one(
                portfolio_code,
                portfolio_partitions.pop(portfolio_code),
                security_partitions.pop(
                    portfolio_code,
                    empty_security_performance,
                ),
            )
        return portfolios

    def _reconcile_one(
        self,
        portfolio_code: str,
        portfolio_performance: pl.DataFrame,
        security_performance: pl.DataFrame,
    ) -> AxysPortfolio:
        """Return one reconciled portfolio from already filtered source rows.

        Args:
            portfolio_code: Portfolio code represented by both source frames.
            portfolio_performance: Portfolio-level rows for ``portfolio_code``.
            security_performance: Security-level rows for ``portfolio_code``.

        Returns:
            Reconciled portfolio output.

        Raises:
            PparError: If common periods cannot be found or security returns
                cannot be reconciled to portfolio returns.
        """
        def portfolio_error_message(message: str) -> str:
            """Return an error message scoped to the current portfolio code."""
            return self._error_message(message, portfolio_code)

        portfolio_performance, security_performance = reconciliation.filter_to_common_periods(
            portfolio_performance,
            security_performance,
            portfolio_error_message,
        )
        (
            security_performance,
            reconciliation_periods,
        ) = reconciliation.derive_security_performance_for_all_periods(
            portfolio_performance,
            security_performance,
            portfolio_error_message,
        )
        difference = reconciliation.unreconciled_difference(reconciliation_periods)
        if reconciliation.exceeds_fatal_tolerance(difference):
            material_periods = reconciliation.material_reconciliation_periods(
                reconciliation_periods
            )
            raise PparError(
                self._error_message(
                    "Geometrically linked target and achieved returns differ "
                    f"by {difference}. Material period residuals: "
                    f"{material_periods[:10]}",
                    portfolio_code,
                ),
            )

        portfolio_name = _portfolio_display_name(
            portfolio_code,
            portfolio_performance,
        )
        return AxysPortfolio(
            portfolio_code,
            portfolio_name,
            security_performance.select(_ANALYTICS_REQUIRED_COLUMNS),
        )
