"""Derive evidence-based Axys security weights.

The adapter prefers contribution-implied weights and falls back to reported
weights only where an implied value is unavailable. Exact signed evidence is
preserved. When complete evidence needs adjustment, the solver minimizes the
sum of squared weight changes while retaining each nonzero anchor's sign and
keeping zero anchors at zero.
"""

from __future__ import annotations

# Python imports
from itertools import combinations
import math
from typing import Final, Sequence

# Third-party imports
import numpy as np
import numpy.typing as npt
import polars as pl

# Project imports
import ppar.schema as cols

_MATCH_TOLERANCE: Final[float] = 1e-12
_NEAR_ZERO_WEIGHT: Final[float] = 1e-18
_RETURN_EPSILON: Final[float] = 1e-12

FloatArray = npt.NDArray[np.float64]


def derive_reconciled_weights(
    security_performance_df: pl.DataFrame,
    portfolio_return: float,
) -> tuple[list[float], float]:
    """Return evidence-based weights aligned to a portfolio return.

    Args:
        security_performance_df: Security-level rows for a single portfolio
            period.
        portfolio_return: Finite portfolio return reported for the same
            period.

    Returns:
        Reconciled weights summing to one and the weighted security return
        achieved by those weights.

    Raises:
        ValueError: If the frame is empty, financial evidence is nonfinite,
            missing weights are underdetermined, source evidence is
            contradictory, or the target return is infeasible without
            reversing a source-supported sign.

    Notes:
        A finite contribution divided by a nonzero security return is the
        preferred anchor. The reported weight is used only when an implied
        weight cannot be calculated. If complete anchors require adjustment,
        the unique minimum-Euclidean-distance solution is used subject to the
        weight-sum and portfolio-return equations and anchor-sign constraints.
    """
    if security_performance_df.is_empty():
        raise ValueError("security_performance_df must contain at least one row.")
    if not math.isfinite(portfolio_return):
        raise ValueError("portfolio_return must be finite.")

    contributions = _optional_financial_values(
        security_performance_df[cols.CONTRIBUTION],
        cols.CONTRIBUTION,
    )
    returns = _required_financial_values(
        security_performance_df[cols.RETURN],
        cols.RETURN,
    )
    reported_weights = _optional_financial_values(
        security_performance_df[cols.WEIGHT],
        cols.WEIGHT,
    )
    anchor_weights = _derive_anchor_weights(
        contributions,
        returns,
        reported_weights,
    )

    missing_indices = [
        index for index, weight in enumerate(anchor_weights) if weight is None
    ]
    if missing_indices:
        reconciled_weights = _infer_missing_weights(
            anchor_weights,
            returns,
            portfolio_return,
            missing_indices,
        )
    else:
        complete_anchors = _complete_financial_values(anchor_weights)
        if _matches_constraints(complete_anchors, returns, portfolio_return):
            reconciled_weights = complete_anchors
        else:
            reconciled_weights = _minimum_departure_weights(
                complete_anchors,
                returns,
                portfolio_return,
            )

    if not _matches_constraints(reconciled_weights, returns, portfolio_return):
        raise ValueError(
            "security weight evidence is contradictory or cannot reproduce "
            "the portfolio return."
        )
    return reconciled_weights, _weighted_return(reconciled_weights, returns)


def _optional_financial_values(
    series: pl.Series,
    field_name: str,
) -> list[float | None]:
    """Return optional finite floats without substituting for missing evidence."""
    values = series.cast(pl.Float64, strict=False).to_list()
    normalized: list[float | None] = []
    for value in values:
        if value is None:
            normalized.append(None)
            continue
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError(f"{field_name} must contain only null or finite values.")
        normalized.append(numeric_value)
    return normalized


def _required_financial_values(series: pl.Series, field_name: str) -> list[float]:
    """Return finite floats or reject absent and nonfinite values."""
    values = _optional_financial_values(series, field_name)
    if any(value is None for value in values):
        raise ValueError(f"{field_name} must contain finite values.")
    return [value for value in values if value is not None]


def _complete_financial_values(values: Sequence[float | None]) -> list[float]:
    """Return complete float values after an earlier missing-value check."""
    if any(value is None for value in values):
        raise ValueError("financial values unexpectedly contain missing evidence.")
    return [value for value in values if value is not None]


def _derive_anchor_weights(
    contributions: Sequence[float | None],
    returns: Sequence[float],
    reported_weights: Sequence[float | None],
) -> list[float | None]:
    """Return preferred contribution-implied or fallback reported anchors."""
    anchors: list[float | None] = []
    for contribution, security_return, reported_weight in zip(
        contributions,
        returns,
        reported_weights,
    ):
        if contribution is not None and abs(security_return) > _RETURN_EPSILON:
            anchors.append(contribution / security_return)
            continue
        if contribution is not None and abs(contribution) > _MATCH_TOLERANCE:
            raise ValueError(
                "security weight evidence is contradictory: a zero security "
                "return has a nonzero contribution."
            )
        anchors.append(reported_weight)
    return anchors


def _infer_missing_weights(
    anchor_weights: Sequence[float | None],
    returns: Sequence[float],
    target_return: float,
    missing_indices: Sequence[int],
) -> list[float]:
    """Infer at most two missing weights when the equations are unique."""
    if len(missing_indices) > 2:
        raise ValueError(
            "security weights are underdetermined: more than two row-level "
            "anchors are missing."
        )

    known_weight = sum(
        float(weight) for weight in anchor_weights if weight is not None
    )
    known_return = sum(
        float(weight) * security_return
        for weight, security_return in zip(anchor_weights, returns)
        if weight is not None
    )
    remaining_weight = 1.0 - known_weight
    remaining_return = target_return - known_return
    inferred = list(anchor_weights)

    if len(missing_indices) == 1:
        missing_index = missing_indices[0]
        inferred[missing_index] = remaining_weight
    else:
        left_index, right_index = missing_indices
        left_return = returns[left_index]
        right_return = returns[right_index]
        return_difference = right_return - left_return
        if abs(return_difference) <= _RETURN_EPSILON:
            raise ValueError(
                "security weights are underdetermined: missing rows have "
                "indistinguishable returns."
            )
        right_weight = (
            remaining_return - (remaining_weight * left_return)
        ) / return_difference
        inferred[left_index] = remaining_weight - right_weight
        inferred[right_index] = right_weight

    complete_weights = _complete_financial_values(inferred)
    if not _matches_constraints(complete_weights, returns, target_return):
        raise ValueError(
            "security weight evidence is contradictory: the uniquely inferred "
            "weights do not reproduce the portfolio return."
        )
    return complete_weights


def _minimum_departure_weights(
    anchor_weights: Sequence[float],
    returns: Sequence[float],
    target_return: float,
) -> list[float]:
    """Project complete anchors onto the constraints without changing signs.

    The transformed optimization minimizes the sum of squared differences
    between the derived weights and source anchors. Positive anchors remain
    nonnegative, negative anchors remain nonpositive, and exact zero anchors
    remain zero. This permits signed source portfolios without inventing
    shorts or long positions unsupported by the source.
    """
    supported_indices = [
        index
        for index, weight in enumerate(anchor_weights)
        if abs(weight) > _NEAR_ZERO_WEIGHT
    ]
    if not supported_indices:
        raise ValueError(
            "security weight evidence is infeasible: all source anchors are zero."
        )

    signs = np.asarray(
        [math.copysign(1.0, anchor_weights[index]) for index in supported_indices],
        dtype=np.float64,
    )
    anchor_magnitudes = np.asarray(
        [abs(anchor_weights[index]) for index in supported_indices],
        dtype=np.float64,
    )
    supported_returns = np.asarray(
        [returns[index] for index in supported_indices],
        dtype=np.float64,
    )
    constraints = np.vstack((signs, signs * supported_returns))
    targets = np.asarray([1.0, target_return], dtype=np.float64)
    magnitudes = _project_nonnegative_with_equalities(
        anchor_magnitudes,
        constraints,
        targets,
    )

    weights = [0.0] * len(anchor_weights)
    for index, sign, magnitude in zip(supported_indices, signs, magnitudes):
        weights[index] = float(sign * magnitude)
    if not _matches_constraints(weights, returns, target_return):
        raise ValueError(
            "security weight evidence is infeasible without reversing a "
            "source-supported sign."
        )
    return weights


def _project_nonnegative_with_equalities(
    anchors: FloatArray,
    constraints: FloatArray,
    targets: FloatArray,
) -> FloatArray:
    """Return the nearest nonnegative vector satisfying two equalities.

    A feasible active-set method solves the strictly convex projection. The
    initial feasible point needs at most two nonzero coordinates because the
    constraint vectors are two-dimensional.
    """
    current = _find_feasible_start(anchors, constraints, targets)
    active = {
        index for index, value in enumerate(current) if value <= _MATCH_TOLERANCE
    }
    current[list(active)] = 0.0
    maximum_iterations = max(20, 10 * anchors.size * anchors.size)

    for _ in range(maximum_iterations):
        free = [index for index in range(anchors.size) if index not in active]
        if not free:
            break
        optimum, multipliers = _face_optimum(
            anchors,
            constraints,
            targets,
            free,
        )
        direction = optimum - current
        blocking = [
            index
            for index in free
            if optimum[index] < -_MATCH_TOLERANCE
            and direction[index] < -_MATCH_TOLERANCE
        ]
        if blocking:
            step = min(
                current[index] / -direction[index]
                for index in blocking
            )
            current = current + (step * direction)
            hit = min(
                blocking,
                key=lambda index: (current[index], index),
            )
            current[hit] = 0.0
            active.add(hit)
            continue

        current = optimum
        violating = [
            index
            for index in active
            if float(constraints[:, index] @ multipliers) - anchors[index]
            < -_MATCH_TOLERANCE
        ]
        if not violating:
            current[np.abs(current) <= _MATCH_TOLERANCE] = 0.0
            return current
        release = min(
            violating,
            key=lambda index: (
                float(constraints[:, index] @ multipliers) - anchors[index],
                index,
            ),
        )
        active.remove(release)

    raise ValueError(
        "security weight evidence is infeasible without reversing a "
        "source-supported sign."
    )


def _find_feasible_start(
    anchors: FloatArray,
    constraints: FloatArray,
    targets: FloatArray,
) -> FloatArray:
    """Return a deterministic feasible point with at most two nonzero values."""
    candidates: list[FloatArray] = []
    coordinate_sets = [
        (index,) for index in range(anchors.size)
    ] + list(combinations(range(anchors.size), 2))
    for coordinate_set in coordinate_sets:
        selected = list(coordinate_set)
        solution, _, _, _ = np.linalg.lstsq(
            constraints[:, selected],
            targets,
            rcond=None,
        )
        if np.any(solution < -_MATCH_TOLERANCE):
            continue
        candidate = np.zeros_like(anchors)
        candidate[selected] = np.maximum(solution, 0.0)
        if np.allclose(
            constraints @ candidate,
            targets,
            rtol=0.0,
            atol=_MATCH_TOLERANCE,
        ):
            candidates.append(candidate)
    if not candidates:
        raise ValueError(
            "security weight evidence is infeasible without reversing a "
            "source-supported sign."
        )
    return min(
        candidates,
        key=lambda candidate: float(np.sum((candidate - anchors) ** 2)),
    )


def _face_optimum(
    anchors: FloatArray,
    constraints: FloatArray,
    targets: FloatArray,
    free: Sequence[int],
) -> tuple[FloatArray, FloatArray]:
    """Return the equality-constrained optimum on one active-set face."""
    free_constraints = constraints[:, free]
    free_anchors = anchors[list(free)]
    system = free_constraints @ free_constraints.T
    right_hand_side = (free_constraints @ free_anchors) - targets
    raw_multipliers, _, _, _ = np.linalg.lstsq(
        system,
        right_hand_side,
        rcond=None,
    )
    multipliers = np.asarray(raw_multipliers, dtype=np.float64)
    optimum = np.zeros_like(anchors)
    optimum[list(free)] = free_anchors - (free_constraints.T @ multipliers)
    if not np.allclose(
        constraints @ optimum,
        targets,
        rtol=0.0,
        atol=_MATCH_TOLERANCE,
    ):
        raise ValueError(
            "security weight evidence is infeasible without reversing a "
            "source-supported sign."
        )
    return optimum, multipliers


def _matches_constraints(
    weights: Sequence[float],
    returns: Sequence[float],
    target_return: float,
) -> bool:
    """Return whether weights satisfy sum and portfolio-return equations."""
    return math.isclose(
        sum(weights),
        1.0,
        rel_tol=0.0,
        abs_tol=_MATCH_TOLERANCE,
    ) and math.isclose(
        _weighted_return(weights, returns),
        target_return,
        rel_tol=0.0,
        abs_tol=_MATCH_TOLERANCE,
    )


def _weighted_return(weights: Sequence[float], returns: Sequence[float]) -> float:
    """Return the weighted arithmetic return for aligned sequences."""
    return sum(
        weight * security_return
        for weight, security_return in zip(weights, returns)
    )
