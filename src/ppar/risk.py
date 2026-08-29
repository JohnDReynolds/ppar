"""Calculate and format ex-post portfolio risk statistics.

This module contains the ``_Statistic`` enumeration and the ``RiskStatistics``
class. ``RiskStatistics`` calculates absolute risk, downside risk,
benchmark-relative risk, risk-adjusted performance, and regression statistics
for a portfolio and benchmark return series.
"""

# Python Imports
import datetime as dt
from enum import Enum
import math
from numbers import Real
from pathlib import Path
from statistics import NormalDist
from typing import cast, Sequence

# Third-Party Imports
import numpy as np
import numpy.typing as npt
import polars as pl

# Project Imports
import ppar.schema as cols
from ppar.frequency import Frequency, periods_per_year
from ppar import tables as html_table
from ppar.performance import Performance
from ppar.errors import PparError
import ppar.utilities as util

# Constants
_DEFAULT_OUTPUT_PRECISION = 8


class _Statistic(Enum):
    """Enumeration of supported ex-post risk statistics.

    The values are arranged in the order used by the formatted output views.
    """

    # Absolute Risk
    RETURN_RANGE = "Return Range"
    MEAN_RETURN = "Mean Return"
    MEAN_RETURN_ANNUALIZED = "Annualized Mean Return"
    STANDARD_DEVIATION = "Standard Deviation"
    STANDARD_DEVIATION_ANNUALIZED = "Annualized Standard Deviation"
    # Downside Risk
    DOWNSIDE_PROBABILITY = "Downside Probability"  # aka "Shortfall Risk"
    EXPECTED_DOWNSIDE_VALUE = "Expected Downside Value"
    DOWNSIDE_DEVIATION = "Downside Deviation"
    DOWNSIDE_DEVIATION_ANNUALIZED = "Annualized Downside Deviation"
    VALUE_AT_RISK = "Value At Risk"
    # Benchmark-Relative Risk
    CORRELATION = "Correlation"
    R_SQUARED = "R-Squared"  # aka "Coefficient Of Determination"
    TRACKING_ERROR = "Tracking Error"
    TRACKING_ERROR_ANNUALIZED = "Annualized Tracking Error"
    # Risk-Adjusted Performance
    SHARPE_RATIO = "Sharpe Ratio"
    SHARPE_RATIO_ANNUALIZED = "Annualized Sharpe Ratio"
    SORTINO_RATIO = "Sortino Ratio"
    SORTINO_RATIO_ANNUALIZED = "Annualized Sortino Ratio"
    INFORMATION_RATIO = "Information Ratio"
    M_SQUARED = "M_Squared"  # aka "Modigliani-Modigliani"
    TREYNOR_RATIO = "Treynor Ratio"
    # Regression
    BETA = "Beta"  # slope
    ALPHA = "Alpha"  # intercept
    ALPHA_ANNUALIZED = "Annualized Alpha"
    JENSENS_ALPHA = "Jensens Alpha"
    JENSENS_ALPHA_ANNUALIZED = "Annualized Jensens Alpha"


# View categories.
_CATEGORIES = pl.Series(
    "Category",
    (["Absolute Risk"] * 5)
    + (["Downside Risk"] * 5)
    + (["Benchmark-Relative Risk"] * 4)
    + (["Risk-Adjusted Performance"] * 7)
    + (["Regression"] * 5),
)

# The minimum quantity of returns in order to calculate the statistics.
_MINIMUM_QUANTITY_OF_RETURNS = 2


class RiskStatistics:
    """Calculate ex-post risk statistics for portfolio and benchmark returns.

    The class accepts either two ``Performance`` instances or two NumPy arrays
    of periodic returns. It calculates the statistics enumerated by
    ``_Statistic`` and stores the formatted results in a Polars DataFrame.

    Notes:
        Results can be retrieved using ``to_html()``,
        ``to_polars()``, or ``to_table()``, and
        written using ``write_csv()``.
    """

    def __init__(
        self,
        returns: Sequence[Performance] | Sequence[npt.NDArray[np.float64]],
        frequency: Frequency,
        annual_minimum_acceptable_return: float = util.DEFAULT_ANNUAL_MINIMUM_ACCEPTABLE_RETURN,
        annual_risk_free_rate: float = util.DEFAULT_ANNUAL_RISK_FREE_RATE,
        confidence_level: float = util.DEFAULT_CONFIDENCE_LEVEL,
        portfolio_value: tuple[float, str] = (
            util.DEFAULT_PORTFOLIO_VALUE,
            util.DEFAULT_CURRENCY_SYMBOL,
        ),
    ):
        """Initialize and calculate risk statistics.

        Args:
            returns: Either a sequence of two ``Performance`` instances or a
                sequence of two NumPy arrays of periodic returns. Index ``0`` is
                the portfolio and index ``1`` is the benchmark.
            frequency: Frequency of the portfolio and benchmark returns.
                Supported values are ``Frequency.MONTHLY``,
                ``Frequency.QUARTERLY``, and ``Frequency.YEARLY``.
            annual_minimum_acceptable_return: Annual minimum acceptable return
                used for downside-risk calculations.
            annual_risk_free_rate: Annual risk-free rate used for
                risk-adjusted performance statistics.
            confidence_level: Confidence level used for value-at-risk
                calculations.
            portfolio_value: Tuple containing the portfolio value and currency
                symbol used when calculating and displaying value at risk.

        Raises:
            PparError: If the frequency, financial parameters, portfolio value,
                input pair, return-source types, return dimensions, return
                lengths, observation count, finite values, or Performance dates
                fail validation.
        """
        # Validate public options before indexing either input pair.
        if not isinstance(frequency, Frequency) or frequency == Frequency.AS_OFTEN_AS_POSSIBLE:
            raise PparError(
                "Risk statistics require monthly, quarterly, or yearly frequency; "
                f"received {frequency!r}."
            )
        return_pair = util.two_item_tuple(returns, "RiskStatistics returns")
        portfolio_value_pair = util.two_item_tuple(
            portfolio_value, "RiskStatistics portfolio_value"
        )

        parameter_values = {
            "annual_minimum_acceptable_return": annual_minimum_acceptable_return,
            "annual_risk_free_rate": annual_risk_free_rate,
            "confidence_level": confidence_level,
            "portfolio_value": portfolio_value_pair[0],
        }
        invalid_parameter: str | None = None
        for parameter, value in parameter_values.items():
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                invalid_parameter = parameter
                break
        if invalid_parameter is None and annual_minimum_acceptable_return <= -1.0:
            invalid_parameter = "annual_minimum_acceptable_return"
        if invalid_parameter is None and annual_risk_free_rate <= -1.0:
            invalid_parameter = "annual_risk_free_rate"
        if invalid_parameter is None and not 0.0 < confidence_level < 1.0:
            invalid_parameter = "confidence_level"
        if invalid_parameter is None and cast(Real, portfolio_value_pair[0]) < 0.0:
            invalid_parameter = "portfolio_value"
        if invalid_parameter is None and not isinstance(portfolio_value_pair[1], str):
            invalid_parameter = "portfolio_value currency symbol"
        if invalid_parameter is not None:
            invalid_value = (
                portfolio_value_pair
                if invalid_parameter.startswith("portfolio_value")
                else parameter_values[invalid_parameter]
            )
            raise PparError(
                f"{invalid_parameter}={invalid_value!r}.",
                context={"parameter": invalid_parameter, "value": invalid_value},
            )

        portfolio_value_amount = float(cast(Real, portfolio_value_pair[0]))
        currency_symbol = cast(str, portfolio_value_pair[1])

        # Set the validated frequency and currency symbol.
        self._frequency = frequency
        self._currency_symbol = currency_symbol

        # Set dates, names, and returns from the input parameters.
        if isinstance(return_pair[0], Performance) and isinstance(return_pair[1], Performance):
            portfolio_totals = return_pair[0].period_totals()
            benchmark_totals = return_pair[1].period_totals()
            self._from_date = portfolio_totals[cols.FROM_DATE][0]
            self._thru_date = portfolio_totals[cols.THRU_DATE][-1]
            self._portfolio_name = return_pair[0].name
            self._benchmark_name = return_pair[1].name
            self._portfolio_returns = portfolio_totals[cols.TOTAL_RETURN].to_numpy()
            self._benchmark_returns = benchmark_totals[cols.TOTAL_RETURN].to_numpy()
            self._performances_to_audit = cast(Sequence[Performance], return_pair)
        elif isinstance(return_pair[0], np.ndarray) and isinstance(return_pair[1], np.ndarray):
            array_pair = cast(
                tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]],
                return_pair,
            )
            for label, values in zip(("portfolio", "benchmark"), array_pair):
                is_real_numeric = np.issubdtype(
                    values.dtype, np.integer
                ) or np.issubdtype(values.dtype, np.floating)
                if values.ndim != 1 or not is_real_numeric:
                    raise PparError(
                        f"{label} returns must be a one-dimensional numeric array.",
                        context={
                            "return_source": label,
                            "dimensions": values.ndim,
                            "dtype": str(values.dtype),
                        },
                    )
            self._from_date = dt.date.min
            self._thru_date = dt.date.max
            self._portfolio_name = "Portfolio"
            self._benchmark_name = "Benchmark"
            self._portfolio_returns = array_pair[0]
            self._benchmark_returns = array_pair[1]
            self._performances_to_audit = cast(Sequence[Performance], tuple())
        else:
            raise PparError(
                "both items must be Performance objects or NumPy arrays.",
                context={
                    "portfolio_type": type(return_pair[0]).__name__,
                    "benchmark_type": type(return_pair[1]).__name__,
                },
            )

        # Now that self._portfolio_returns has been established, set self._quantity_of_returns.
        self._quantity_of_returns = len(self._portfolio_returns)

        # Validate that the portfolio and benchmark have the same quantity of returns.
        if self._quantity_of_returns != len(self._benchmark_returns):
            raise PparError(
                "Portfolio and benchmark return counts differ: "
                f"{self._quantity_of_returns} and {len(self._benchmark_returns)}."
            )

        # Validate that there are enough returns.
        if self._quantity_of_returns < _MINIMUM_QUANTITY_OF_RETURNS:
            raise PparError(
                f"Risk statistics require at least {_MINIMUM_QUANTITY_OF_RETURNS} "
                f"returns; received {self._quantity_of_returns}."
            )

        # NaN and infinite observations cannot produce meaningful statistics.
        try:
            returns_are_finite = np.all(np.isfinite(self._portfolio_returns)) and np.all(
                np.isfinite(self._benchmark_returns)
            )
        except TypeError as error:
            raise PparError("Portfolio and benchmark returns must be numeric.") from error
        if not returns_are_finite:
            raise PparError("Portfolio and benchmark returns must be finite.")

        # If Performance objects were supplied directly, validate date alignment.
        if self._performances_to_audit:
            self._audit()

        # Get all statistic values.
        statistic_values = self._calculate_all_statistics(
            annual_minimum_acceptable_return,
            annual_risk_free_rate,
            confidence_level,
            portfolio_value_amount,
        )

        # Create self._df from the statistic_values dictionary.
        self._df = pl.DataFrame(statistic_values)

        # Rename the non-annualized column names so the frequency is prepended, and
        # the currency symbol is prepended for the portfolio_value.
        self._df.columns = [
            self._frequency_column_name(col, portfolio_value_amount) for col in self._df.columns
        ]

        # Create the final DataFrame.
        self._df = (
            self._df
            # Transpose 2 rows to 2 Portfolio and Benchmark columns.
            .transpose(include_header=True, column_names=("Portfolio", "Benchmark"))
            .lazy()
            # Add the Difference column.
            .with_columns((pl.col("Portfolio") - pl.col("Benchmark")).alias("Difference"))
            # Add the Category column.
            .with_columns(_CATEGORIES)
            .collect()
        )

    def _annualize_return(self, mean_frequency_return: float, qty_periods_per_year: int) -> float:
        """Annualize a mean periodic return.

        Args:
            mean_frequency_return: Mean return for the input frequency.
            qty_periods_per_year: Number of periods per year for the input
                frequency.

        Returns:
            Annualized return, or ``np.nan`` when the return series contains
            fewer than one year's worth of observations.
        """
        # Cannot annualize if you do not have at least a years worth of returns, so return np.nan.
        return (
            np.nan
            if self._quantity_of_returns < qty_periods_per_year
            else ((1 + mean_frequency_return) ** qty_periods_per_year) - 1
        )

    def _audit(self) -> None:
        """Audit the source performance pair.

        Raises:
            PparError: Raised by ``Performance.audit_performances()`` if the
                source portfolio and benchmark performances fail validation.
        """
        # Audit the portfolio/benchmark pair of performances.
        Performance.audit_performances(
            self._performances_to_audit, self._from_date, self._thru_date
        )

    @staticmethod
    def _beta(
        portfolio_returns: npt.NDArray[np.float64], benchmark_returns: npt.NDArray[np.float64]
    ) -> float:
        """Calculate beta between portfolio and benchmark returns.

        Args:
            portfolio_returns: Portfolio periodic returns.
            benchmark_returns: Benchmark periodic returns.

        Returns:
            Portfolio beta relative to the benchmark.
        """
        # Use a consistent degrees-of-freedom (sample ddof=1) for both covariance
        # and variance so the beta calculation is not biased by mismatched normalizations.
        covariance_matrix = np.cov(portfolio_returns, benchmark_returns, ddof=1)
        covariance = covariance_matrix[0, 1]
        benchmark_variance = np.var(benchmark_returns, ddof=1)
        if np.isclose(benchmark_variance, 0.0):
            return math.nan
        return cast(float, covariance / benchmark_variance)  # cast for mypy

    def _calculate_all_statistics(
        self,
        annual_minimum_acceptable_return: float,
        annual_risk_free_rate: float,
        confidence_level: float,
        portfolio_value: float,
    ) -> dict[str, list[float]]:
        """Calculate all statistic values for portfolio and benchmark.

        Args:
            annual_minimum_acceptable_return: Annual minimum acceptable return
                used for downside-risk calculations.
            annual_risk_free_rate: Annual risk-free rate used for
                risk-adjusted performance statistics.
            confidence_level: Confidence level used for value-at-risk
                calculations.
            portfolio_value: Portfolio currency value used for value-at-risk
                calculations.

        Returns:
            Dictionary keyed by statistic display name. Each value contains
            the portfolio statistic followed by the benchmark statistic.

        Raises:
            PparError: Raised by ``periods_per_year()`` if the stored frequency
                is unsupported for annualization.
        """
        # Do not annualize partial-year samples. Annualized risk numbers can look
        # authoritative even when there are too few observations to support them.
        qty_periods_per_year = periods_per_year(self._frequency)
        annualization_coefficient = (
            np.nan
            if self._quantity_of_returns < qty_periods_per_year
            else math.sqrt(qty_periods_per_year)
        )

        # Convert annual hurdle/risk-free rates to the observation frequency by
        # compounding. For example, a 12% annual hurdle is not treated as 1% per
        # month; it is the monthly rate that compounds to 12%.
        frequency_mar = RiskStatistics._deannualize_return(
            annual_minimum_acceptable_return, qty_periods_per_year
        )
        frequency_rfr = RiskStatistics._deannualize_return(
            annual_risk_free_rate, qty_periods_per_year
        )

        # Calculate other common values used below.
        active_returns = self._portfolio_returns - self._benchmark_returns
        benchmark_mean = cast(float, np.mean(self._benchmark_returns))

        # Initialize the dictionaries for the statistics.
        statistic_values: dict[str, list[float]] = {}

        # Calculate the statistics.
        for idx, rets in enumerate((self._portfolio_returns, self._benchmark_returns)):
            # Calculate the basic statistics.
            mean = cast(float, np.mean(rets))
            stddev = cast(float, np.std(rets))

            # Downside deviation penalizes every observation by its shortfall below
            # the minimum acceptable return. Observations above the hurdle contribute
            # zero, so this is a semi-deviation around the hurdle rather than around
            # the mean.
            downside_returns = np.clip(rets - frequency_mar, a_min=-np.inf, a_max=0)
            downside_deviation = float(np.sqrt(np.mean(downside_returns**2)))

            # Expected downside value is an unconditional shortfall: periods above
            # the hurdle are excluded from the numerator but remain in the denominator.
            # This keeps it comparable with downside probability.
            returns_below_mar = rets[rets < frequency_mar] - frequency_mar

            # Calculate the risk-free ratios.
            excess_returns_mean, sharpe_ratio = (
                RiskStatistics._calculate_risk_free_ratios(rets, frequency_rfr)
            )
            sortino_ratio = RiskStatistics._ratio_with_zero_denominator(
                mean - frequency_mar,
                downside_deviation,
            )

            if idx == 0:  # Portfolio
                # Active risk uses portfolio minus benchmark returns period by period.
                active_returns_stddev = float(np.std(active_returns))
                # With a constant risk-free rate, beta is unchanged by subtracting
                # that rate from both portfolio and benchmark returns.
                beta = RiskStatistics._beta(self._portfolio_returns, self._benchmark_returns)

                # Regression alpha here is the intercept implied by mean returns:
                # alpha = portfolio_mean - beta * benchmark_mean.
                alpha = mean - (beta * benchmark_mean)
                benchmark_stddev = float(np.std(self._benchmark_returns))
                correlation_coefficient = (
                    math.nan
                    if np.isclose(stddev, 0.0)
                    or np.isclose(benchmark_stddev, 0.0)
                    else cast(
                        float,
                        np.corrcoef(
                            self._portfolio_returns,
                            self._benchmark_returns,
                        )[0, 1],
                    )
                )

                # Jensen's alpha measures excess return over the CAPM-implied
                # excess return, using the same periodic risk-free rate.
                jensens_alpha = excess_returns_mean - (beta * (benchmark_mean - frequency_rfr))
            else:  # Benchmark
                # Benchmark-relative statistics are only meaningful for the
                # portfolio row; the benchmark has no benchmark-relative benchmark.
                active_returns_stddev = math.nan
                beta = math.nan
                alpha = math.nan
                correlation_coefficient = math.nan
                jensens_alpha = math.nan

            for statistic in _Statistic:
                if idx == 0:
                    # Allocate the statistic: 0 = Portfolio, 1 = Benchmark.
                    statistic_values[statistic.value] = []

                # Set the appropriate statistic value.
                match statistic:
                    case _Statistic.ALPHA:
                        value = alpha
                    case _Statistic.ALPHA_ANNUALIZED:
                        # Alpha is a return-like quantity, so annualize by compounding
                        # rather than by sqrt(periods), which is for volatility.
                        value = self._annualize_return(alpha, qty_periods_per_year)
                    case _Statistic.BETA:
                        value = beta
                    case _Statistic.CORRELATION:
                        value = correlation_coefficient
                    case _Statistic.DOWNSIDE_DEVIATION:
                        value = downside_deviation
                    case _Statistic.DOWNSIDE_DEVIATION_ANNUALIZED:
                        value = annualization_coefficient * downside_deviation
                    case _Statistic.DOWNSIDE_PROBABILITY:
                        value = len(returns_below_mar) / self._quantity_of_returns
                    case _Statistic.EXPECTED_DOWNSIDE_VALUE:
                        value = float(np.sum(returns_below_mar)) / self._quantity_of_returns
                    case _Statistic.INFORMATION_RATIO:
                        if idx == 0:
                            value = RiskStatistics._ratio_with_zero_denominator(
                                float(np.mean(active_returns)),
                                active_returns_stddev,
                            )
                        else:
                            value = math.nan
                    case _Statistic.JENSENS_ALPHA:
                        value = jensens_alpha
                    case _Statistic.JENSENS_ALPHA_ANNUALIZED:
                        value = self._annualize_return(jensens_alpha, qty_periods_per_year)
                    case _Statistic.M_SQUARED:
                        if idx == 0:
                            # M-squared expresses Sharpe performance as a return
                            # scaled to benchmark volatility, then adds back cash.
                            value = (
                                sharpe_ratio * float(np.std(self._benchmark_returns))
                            ) + frequency_rfr
                        else:
                            value = math.nan
                    case _Statistic.MEAN_RETURN:
                        value = mean
                    case _Statistic.MEAN_RETURN_ANNUALIZED:
                        value = self._annualize_return(mean, qty_periods_per_year)
                    case _Statistic.R_SQUARED:
                        value = correlation_coefficient**2
                    case _Statistic.RETURN_RANGE:
                        value = float(np.max(rets) - np.min(rets))
                    case _Statistic.SHARPE_RATIO:
                        value = sharpe_ratio
                    case _Statistic.SHARPE_RATIO_ANNUALIZED:
                        value = annualization_coefficient * sharpe_ratio
                    case _Statistic.SORTINO_RATIO:
                        value = sortino_ratio
                    case _Statistic.SORTINO_RATIO_ANNUALIZED:
                        value = annualization_coefficient * sortino_ratio
                    case _Statistic.STANDARD_DEVIATION:
                        value = stddev
                    case _Statistic.STANDARD_DEVIATION_ANNUALIZED:
                        value = annualization_coefficient * stddev
                    case _Statistic.TRACKING_ERROR:
                        value = active_returns_stddev
                    case _Statistic.TRACKING_ERROR_ANNUALIZED:
                        value = annualization_coefficient * active_returns_stddev
                    case _Statistic.TREYNOR_RATIO:
                        if idx == 0:
                            # Treynor uses beta, not volatility, as the risk unit.
                            # Preserve the excess-return sign when finite beta is
                            # effectively zero. Nonfinite beta remains undefined.
                            value = (
                                math.nan
                                if not np.isfinite(beta)
                                else RiskStatistics._ratio_with_zero_denominator(
                                    excess_returns_mean,
                                    beta,
                                )
                            )
                        else:
                            value = math.nan
                    case _Statistic.VALUE_AT_RISK:
                        value = RiskStatistics._parametric_var(
                            mean, stddev, confidence_level, portfolio_value
                        )

                statistic_values[statistic.value].append(value)

        # Return all statistic values.
        return statistic_values

    @staticmethod
    def _calculate_risk_free_ratios(
        returns: npt.NDArray[np.float64], frequency_rfr: float
    ) -> tuple[float, float]:
        """Calculate risk-free-rate-adjusted performance ratios.

        Args:
            returns: Periodic return series.
            frequency_rfr: Risk-free rate converted to the same periodic
                frequency as ``returns``.

        Returns:
            Tuple containing mean excess return and Sharpe ratio.
        """
        # The current model assumes one constant risk-free rate for all periods.
        # Under that assumption, subtracting the risk-free rate shifts the mean
        # excess return but leaves standard deviation unchanged.
        excess_returns = returns - frequency_rfr
        excess_returns_mean = excess_returns.mean()

        # A zero-volatility nonzero excess-return series has an unbounded Sharpe
        # ratio. Preserve the numerator's sign rather than always returning +inf.
        denom = excess_returns.std()
        sharpe_ratio = RiskStatistics._ratio_with_zero_denominator(
            float(excess_returns_mean),
            float(denom),
        )
        return float(excess_returns_mean), sharpe_ratio

    @staticmethod
    def _ratio_with_zero_denominator(numerator: float, denominator: float) -> float:
        """Divide while preserving sign for a finite zero denominator.

        Args:
            numerator: Ratio numerator.
            denominator: Ratio denominator.

        Returns:
            The ordinary quotient, signed infinity for a nonzero numerator over
            an effectively zero denominator, or ``NaN`` when the ratio is
            indeterminate or either input is nonfinite.
        """
        if not math.isfinite(numerator) or not math.isfinite(denominator):
            return math.nan
        if np.isclose(denominator, 0.0):
            if np.isclose(numerator, 0.0):
                return math.nan
            return math.copysign(math.inf, numerator)
        return numerator / denominator

    @staticmethod
    def _deannualize_return(annual_return: float, qty_periods_per_year: int) -> float:
        """Convert an annual return to a periodic return.

        Args:
            annual_return: Annual return to convert.
            qty_periods_per_year: Number of periods per year.

        Returns:
            Periodic return corresponding to ``qty_periods_per_year``.
        """
        return cast(
            float, ((1 + annual_return) ** (1 / qty_periods_per_year)) - 1
        )  # cast for mypy

    def _frequency_column_name(self, column_name: str, portfolio_value: float) -> str:
        """Build a display column name for a statistic.

        Non-annualized statistics are prefixed with the reporting frequency.
        Value-at-risk is also labeled with the portfolio currency value.

        Args:
            column_name: Base statistic column name.
            portfolio_value: Portfolio currency value used for value-at-risk
                labeling.

        Returns:
            Display column name.
        """
        if column_name == _Statistic.VALUE_AT_RISK.value:
            return (
                f"{self._frequency.value} {column_name} for "
                f"{self._currency_symbol}{portfolio_value:,.0f}"
            )
        if not column_name.startswith("Annualized"):
            return f"{self._frequency.value} {column_name}"
        return column_name

    @staticmethod
    def _parametric_var(
        mean: float,
        stddev: float,
        confidence_level: float,
        portfolio_value: float,
    ) -> float:
        """Calculate parametric value at risk.

        Args:
            mean: Mean periodic return.
            stddev: Standard deviation of periodic returns.
            confidence_level: Confidence level, such as ``0.95`` for 95%.
            portfolio_value: Portfolio currency value.

        Returns:
            Parametric value at risk as a positive currency amount.
        """
        # For a 95% VaR, use the 5th percentile of the normal return distribution.
        # ``z_score`` is negative, so ``mean + z * stddev`` is the lower-tail return.
        z_score = NormalDist().inv_cdf(1 - confidence_level)

        # Report VaR as a nonnegative potential loss. Example: if the 5th-percentile
        # return is -3%, a $100,000 portfolio has $3,000 VaR. If the lower-tail
        # quantile is still positive, the loss is floored at zero.
        var = max(0.0, -(mean + (z_score * stddev)) * portfolio_value)

        # This package uses the common positive-loss convention; callers do not
        # need to negate the result for presentation.
        return var

    def to_html(self) -> str:
        """Return the statistics table as an HTML page string.

        Returns:
            HTML string containing the formatted risk-statistics table.
        """
        title, subtitle = self._title_and_subtitle()
        return html_table.riskstatistics_html(
            self._df,
            title,
            subtitle,
            self._currency_symbol,
        )

    def to_polars(self) -> pl.DataFrame:
        """Return the statistics as a Polars DataFrame.

        Returns:
            Polars DataFrame containing the calculated risk statistics.
        """
        return self._df.clone()

    def to_table(self) -> html_table.HtmlTable:
        """Return the statistics as a lightweight HTML table object.

        Returns:
            HtmlTable object containing the formatted risk-statistics table.
        """
        title, subtitle = self._title_and_subtitle()
        return html_table.riskstatistics_table(
            self._df,
            title,
            subtitle,
            self._currency_symbol,
        )

    def _title_and_subtitle(self) -> tuple[str, str]:
        """Return title and subtitle text for risk-statistics output."""
        return (
            f"{self._portfolio_name or ''} vs {self._benchmark_name or ''}",
            f"Ex-Post Risk Statistics: {self._frequency.value} from {self._from_date} to "
            f"{self._thru_date}",
        )

    def write_csv(
        self, file_path: util.PathLike, float_precision: int = _DEFAULT_OUTPUT_PRECISION
    ) -> None:
        """Write the statistics to a CSV file.

        Args:
            file_path: Output CSV file path.
            float_precision: Number of decimal places to write for floating
                point values.
        """
        if not isinstance(float_precision, int) or isinstance(float_precision, bool):
            raise PparError("float_precision must be an integer from 0 through 15.")
        if not 0 <= float_precision <= 15:
            raise PparError("float_precision must be an integer from 0 through 15.")
        self._df.write_csv(Path(file_path), float_precision=float_precision)
