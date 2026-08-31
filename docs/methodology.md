# Methodology

ppar calculates benchmark-relative portfolio performance from security-period rows.
It validates dates, weights, returns, and classifications, then checks that calculated
contributions and portfolio totals reconcile.

## Contribution and attribution

Simple contribution is weight multiplied by security return. Active return is
portfolio return minus benchmark return. For each classification group, ppar calculates
allocation, selection, and interaction effects and reports their total as the
attribution effect.

Multi-period effects use logarithmic (Carino) smoothing so the detailed effects foot
to linked active return. Cumulative returns compound geometrically. Fixed reporting
frequencies consolidate complete source periods and apply the configured holiday
calendar when identifying period ends.

The package retains inexpensive reconciliation checks in normal runs. A failed
financial invariant raises `PparError` instead of publishing partial output.

## Ex-post risk

For fixed-frequency returns, ppar reports absolute and relative statistics including
mean and annualized return, volatility, downside deviation, Sharpe and Sortino ratios,
tracking error, information ratio, beta, correlation, alpha, Jensen's alpha,
M-squared, Treynor ratio, and parametric value at risk.

Return-like values are annualized by compounding; volatility-like values use the
square root of periods per year. Value at risk uses the configured confidence level
and portfolio value and is displayed as a nonnegative potential loss. These are
ex-post analytics, not forecasts or investment advice.
