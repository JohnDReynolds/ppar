"""Solve Axys security weights that reconcile to portfolio returns."""

from __future__ import annotations

# Python imports
import math
from typing import Final, Sequence

# Third-party imports
import polars as pl

# Project imports
import ppar.schema as cols

_MATCH_TOLERANCE: Final[float] = 1e-12
_NEAR_ZERO_WEIGHT: Final[float] = 1e-18
_RETURN_EPSILON: Final[float] = 1e-12


def derive_reconciled_weights(
    security_performance_df: pl.DataFrame,
    portfolio_return: float,
) -> tuple[list[float], float]:
    """Return nonnegative normalized weights aligned to a portfolio return.

    Args:
        security_performance_df: Security-level rows for a single portfolio
            period.
        portfolio_return: Portfolio return reported for the same period.

    Returns:
        Tuple containing adjusted nonnegative weights summing to one and the
        weighted security return achieved by those weights.

    Raises:
        ValueError: If ``security_performance_df`` contains no rows.

    Notes:
        When a security return is nonzero, contribution divided by return is
        preferred as the anchor weight. Otherwise, a valid reported weight is
        used. Invalid anchors fall back to equal participation before the
        weights are tilted toward the portfolio return.
    """
    if security_performance_df.is_empty():
        raise ValueError("security_performance_df must contain at least one row.")

    contributions = (
        security_performance_df[cols.CONTRIBUTION]
        .cast(pl.Float64, strict=False)
        .fill_null(0.0)
        .to_list()
    )
    returns = (
        security_performance_df[cols.RETURN]
        .cast(pl.Float64, strict=False)
        .fill_null(0.0)
        .to_list()
    )
    weights = (
        security_performance_df[cols.WEIGHT]
        .cast(pl.Float64, strict=False)
        .fill_null(float("nan"))
        .to_list()
    )
    contributions = [_finite_or_default(value, 0.0) for value in contributions]
    returns = [_finite_or_default(value, 0.0) for value in returns]
    weights = [_finite_or_default(value, float("nan")) for value in weights]

    implied_weights: list[float | None] = []
    for contribution, sec_return in zip(contributions, returns):
        if abs(sec_return) <= _RETURN_EPSILON:
            implied_weights.append(None)
            continue
        implied_weight = contribution / sec_return
        implied_weights.append(implied_weight if implied_weight >= 0.0 else None)

    anchor_weights = [
        implied_weight if implied_weight is not None else weight if weight >= 0.0 else 1.0
        for implied_weight, weight in zip(implied_weights, weights)
    ]
    anchor_total = sum(anchor_weights)
    if anchor_total <= 0.0 or not math.isfinite(anchor_total):
        anchor_weights = [1.0] * len(anchor_weights)
        anchor_total = float(len(anchor_weights))
    anchor_weights = [max(0.0, weight) / anchor_total for weight in anchor_weights]

    adjusted_weights = _solve_adjusted_weights(anchor_weights, returns, portfolio_return)
    adjusted_total = sum(adjusted_weights)
    if not math.isfinite(adjusted_total) or adjusted_total <= _NEAR_ZERO_WEIGHT:
        adjusted_weights = [1.0 / float(len(adjusted_weights))] * len(adjusted_weights)
    else:
        adjusted_weights = [weight / adjusted_total for weight in adjusted_weights]
    return adjusted_weights, _weighted_return(adjusted_weights, returns)


def _finite_or_default(value: float | None, default: float) -> float:
    """Return a finite value or a replacement for missing/nonfinite input.

    Args:
        value: Numeric candidate to inspect.
        default: Replacement when ``value`` is absent or nonfinite.

    Returns:
        ``value`` when finite; otherwise, ``default``.
    """
    if value is None:
        return default
    return value if math.isfinite(value) else default


def _solve_adjusted_weights(
    anchor_weights: Sequence[float],
    returns: Sequence[float],
    target_return: float,
) -> list[float]:
    """Find reconciled weights using progressively broader solution methods.

    Args:
        anchor_weights: Initial normalized nonnegative weights.
        returns: Security returns corresponding to ``anchor_weights``.
        target_return: Portfolio return to match.

    Returns:
        Reconciled weights when a solution is found, or the anchor weights if
        no attempted solution can match the target return.

    Notes:
        The routine first attempts a closed-form tilt, then a bisection search,
        and finally a two-security convex-combination fallback.
    """
    anchor_return = _weighted_return(anchor_weights, returns)
    if abs(anchor_return - target_return) <= _MATCH_TOLERANCE:
        return list(anchor_weights)

    closed_form_weights = _solve_closed_form_tilt(
        anchor_weights, returns, target_return, _NEAR_ZERO_WEIGHT
    )
    if closed_form_weights is not None and (
        abs(_weighted_return(closed_form_weights, returns) - target_return)
        <= 10.0 * _MATCH_TOLERANCE
    ):
        return closed_form_weights

    bisection_weights = _solve_bisection_tilt(anchor_weights, returns, target_return)
    if bisection_weights is not None and (
        abs(_weighted_return(bisection_weights, returns) - target_return)
        <= 10.0 * _MATCH_TOLERANCE
    ):
        return bisection_weights

    two_security_weights = _solve_two_security_fallback(anchor_weights, returns, target_return)
    return two_security_weights if two_security_weights is not None else list(anchor_weights)


# pylint: disable-next=too-many-locals
def _solve_bisection_tilt(
    anchor_weights: Sequence[float],
    returns: Sequence[float],
    target_return: float,
    max_iterations: int = 200,
) -> list[float] | None:
    """Search for a feasible return-matching tilt by bisection.

    Args:
        anchor_weights: Initial normalized nonnegative weights.
        returns: Security returns corresponding to ``anchor_weights``.
        target_return: Portfolio return to match.
        max_iterations: Maximum midpoint refinements for a bracketed root.

    Returns:
        Adjusted weights if a feasible bracketed solution is found; otherwise,
        ``None``.
    """
    candidate_lambdas = [
        -1.0e12,
        -1.0e9,
        -1.0e6,
        -1.0e3,
        -1.0,
        -1.0e-3,
        0.0,
        1.0e-3,
        1.0,
        1.0e3,
        1.0e6,
        1.0e9,
        1.0e12,
    ]
    valid_points: list[tuple[float, float]] = []
    for lambda_value in candidate_lambdas:
        weights = _weights_from_lambda(anchor_weights, returns, lambda_value, _NEAR_ZERO_WEIGHT)
        if weights is None:
            continue
        residual = _weighted_return(weights, returns) - target_return
        if math.isfinite(residual):
            valid_points.append((lambda_value, residual))

    for lambda_value, residual in valid_points:
        if abs(residual) <= _MATCH_TOLERANCE:
            return _weights_from_lambda(anchor_weights, returns, lambda_value, _NEAR_ZERO_WEIGHT)

    for (left_lambda, left_residual), (right_lambda, right_residual) in zip(
        valid_points[:-1], valid_points[1:]
    ):
        if left_residual * right_residual > 0.0:
            continue
        lower_lambda = left_lambda
        upper_lambda = right_lambda
        lower_residual = left_residual
        for _ in range(max_iterations):
            middle_lambda = 0.5 * (lower_lambda + upper_lambda)
            middle_weights = _weights_from_lambda(
                anchor_weights, returns, middle_lambda, _NEAR_ZERO_WEIGHT
            )
            if middle_weights is None:
                return None
            middle_residual = _weighted_return(middle_weights, returns) - target_return
            if abs(middle_residual) <= _MATCH_TOLERANCE:
                return middle_weights
            if lower_residual * middle_residual <= 0.0:
                upper_lambda = middle_lambda
            else:
                lower_lambda = middle_lambda
                lower_residual = middle_residual
        return _weights_from_lambda(
            anchor_weights,
            returns,
            0.5 * (lower_lambda + upper_lambda),
            _NEAR_ZERO_WEIGHT,
        )
    return None


def _solve_closed_form_tilt(
    anchor_weights: Sequence[float],
    returns: Sequence[float],
    target_return: float,
    near_zero_weight: float,
) -> list[float] | None:
    """Calculate weights using the analytical linear-tilt solution.

    Args:
        anchor_weights: Initial normalized nonnegative weights.
        returns: Security returns corresponding to ``anchor_weights``.
        target_return: Portfolio return to match.
        near_zero_weight: Minimum viable normalization magnitude.

    Returns:
        Adjusted weights if the closed-form tilt is feasible; otherwise,
        ``None``.
    """
    anchor_return = _weighted_return(anchor_weights, returns)
    second_moment = sum(
        weight * sec_return * sec_return for weight, sec_return in zip(anchor_weights, returns)
    )
    denominator = second_moment - (target_return * anchor_return)
    if not math.isfinite(denominator) or abs(denominator) <= near_zero_weight:
        return None
    lambda_value = (target_return - anchor_return) / denominator
    return _weights_from_lambda(anchor_weights, returns, lambda_value, near_zero_weight)


# pylint: disable-next=too-many-locals
def _solve_two_security_fallback(
    anchor_weights: Sequence[float],
    returns: Sequence[float],
    target_return: float,
) -> list[float] | None:
    """Construct a feasible portfolio from one or two security returns.

    Args:
        anchor_weights: Initial normalized nonnegative weights used to rank
            candidate security pairs.
        returns: Security returns corresponding to ``anchor_weights``.
        target_return: Portfolio return to match.

    Returns:
        Weights concentrated in a security or security pair that spans the
        target return, or ``None`` when no such combination exists.
    """
    for row_index, sec_return in enumerate(returns):
        if abs(sec_return - target_return) <= _MATCH_TOLERANCE:
            weights = [0.0] * len(returns)
            weights[row_index] = 1.0
            return weights

    best_pair: tuple[int, int] | None = None
    best_pair_score = -1.0
    for left_index, left_return in enumerate(returns):
        for right_index in range(left_index + 1, len(returns)):
            right_return = returns[right_index]
            if target_return < min(left_return, right_return) - _MATCH_TOLERANCE:
                continue
            if target_return > max(left_return, right_return) + _MATCH_TOLERANCE:
                continue
            if abs(left_return - right_return) <= _MATCH_TOLERANCE:
                continue
            pair_score = anchor_weights[left_index] + anchor_weights[right_index]
            if pair_score > best_pair_score:
                best_pair = (left_index, right_index)
                best_pair_score = pair_score
    if best_pair is None:
        return None

    left_index, right_index = best_pair
    left_return = returns[left_index]
    right_return = returns[right_index]
    right_weight = (target_return - left_return) / (right_return - left_return)
    left_weight = 1.0 - right_weight
    if left_weight < -_MATCH_TOLERANCE or right_weight < -_MATCH_TOLERANCE:
        return None
    weights = [0.0] * len(returns)
    weights[left_index] = max(0.0, left_weight)
    weights[right_index] = max(0.0, right_weight)
    total_weight = sum(weights)
    return None if total_weight <= 0.0 else [weight / total_weight for weight in weights]


def _weighted_return(weights: Sequence[float], returns: Sequence[float]) -> float:
    """Return the weighted arithmetic return for aligned sequences.

    Args:
        weights: Portfolio weights.
        returns: Security returns corresponding to ``weights``.

    Returns:
        Sum of each weight multiplied by its corresponding return.
    """
    return sum(weight * sec_return for weight, sec_return in zip(weights, returns))


def _weights_from_lambda(
    anchor_weights: Sequence[float],
    returns: Sequence[float],
    lambda_value: float,
    near_zero_weight: float,
) -> list[float] | None:
    """Apply a linear return tilt and normalize the resulting weights.

    Args:
        anchor_weights: Initial normalized nonnegative weights.
        returns: Security returns corresponding to ``anchor_weights``.
        lambda_value: Tilt parameter applied to each security return.
        near_zero_weight: Minimum viable normalization or total-weight value.

    Returns:
        Normalized nonnegative tilted weights when feasible; otherwise,
        ``None``.
    """
    normalization = 1.0 + (lambda_value * _weighted_return(anchor_weights, returns))
    if not math.isfinite(normalization) or abs(normalization) <= near_zero_weight:
        return None
    raw_weights = [
        anchor_weight * (1.0 + (lambda_value * sec_return)) / normalization
        for anchor_weight, sec_return in zip(anchor_weights, returns)
    ]
    if not all(math.isfinite(weight) for weight in raw_weights):
        return None
    if any(weight < -near_zero_weight for weight in raw_weights):
        return None
    cleaned_weights = [0.0 if weight < 0.0 else weight for weight in raw_weights]
    total_weight = sum(cleaned_weights)
    if not math.isfinite(total_weight) or total_weight <= near_zero_weight:
        return None
    return [weight / total_weight for weight in cleaned_weights]
