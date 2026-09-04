# Methodology

ppar presents benchmark-relative portfolio analytics from security-period rows. Its
portable `perfattr` dependency validates and prepares source-neutral dates, weights,
returns, contributions, periods, and classifications, then performs attribution and
the associated reconciliation checks.

## Contribution and attribution

Simple contribution is weight multiplied by security return. Active return is
portfolio return minus benchmark return. For each classification group, ppar reports
an allocation effect, a portfolio-weighted selection effect, and their sum as the
total attribution effect. When both group returns are defined, the selection effect
is portfolio weight multiplied by the difference between the portfolio and benchmark
group returns. In a three-effect presentation, benchmark-weighted selection and
interaction sum to this same portfolio-weighted selection effect. ppar incorporates
what that presentation calls selection and interaction into `Selection_Effect_Simple`
and does not report a separate interaction column.

Multi-period effects use logarithmic (Carino) smoothing so the detailed effects foot
to linked active return. Cumulative returns compound geometrically. Fixed reporting
frequencies consolidate complete source periods and apply the configured holiday
calendar when identifying period ends.

Overall identifier weights are averaged by the elapsed days in the accepted source
periods. Unobserved calendar gaps do not enter the denominator. Overall identifier
contributions use the same logarithmic linking convention as attribution, so their
sum equals the geometrically linked total return rather than the sum of simple-period
returns.

A mapped group can have zero net weight and nonzero contribution when signed
constituents offset. Its contribution is retained and its mathematically undefined
group return is reported as null. The group's total Brinson-Fachler effect is
calculated directly as active contribution minus active weight multiplied by the
period benchmark return. When the benchmark group return is defined, allocation uses
the usual Brinson-Fachler formula and selection is the reconciling residual. When the
benchmark group return is undefined, allocation is zero and selection carries the
complete total effect.

Heatmaps preserve the same distinction. A zero-net group's defined nonzero
contribution remains visible, while a mathematically undefined portfolio or active
return is masked and is not annotated as zero. An absent date/classification cell
represents no group exposure or contribution and retains the model's defined zero.
Portfolio-only heatmaps omit ordinary missing holdings whose weight and selected
metric are both zero.

At the native source frequency, portfolio and benchmark returns are compared only
when their complete inclusive date pairs match. Leading or trailing history outside
the shared window may be omitted, but an unmatched period inside that window is an
error. At a fixed frequency, the two sources may use different partitions, such as
daily and monthly rows, only when every reported bucket covers the same complete,
gapless inclusive dates on both sides.

The package retains inexpensive reconciliation checks in normal runs. A failed
financial invariant raises `PparError` instead of returning an invalid result.

## Ex-post risk

For fixed-frequency returns, ppar reports absolute and relative statistics including
mean and annualized return, volatility, downside deviation, Sharpe and Sortino ratios,
tracking error, information ratio, beta, correlation, alpha, Jensen's alpha,
M-squared, Treynor ratio, and parametric value at risk.

Return-like values are annualized by compounding; volatility-like values use the
square root of periods per year. Value at risk uses the configured confidence level
and portfolio value and is displayed as a nonnegative potential loss. These are
ex-post analytics, not forecasts or investment advice.

Periodic portfolio and benchmark returns must be finite and strictly greater than
-100%, so every wealth relative used for geometric annualization remains positive.
Positive leveraged returns have no corresponding fixed upper limit. A derived
return-like statistic, such as regression alpha, must satisfy the same domain before
it can be annualized. Direct NumPy integer and floating inputs are converted to
`float64` before subtraction or any other calculation, preventing signed or unsigned
integer arithmetic from changing a risk result.

Beta uses sample covariance divided by sample benchmark variance with matching
degrees of freedom. A genuinely constant benchmark, or variation no larger than the
floating-point resolution at the scale of its values, has undefined beta. A
representable low-volatility benchmark remains valid; it is not classified as
constant by a fixed absolute threshold. The same scale-aware variation decision is
used before calculating correlation. A covariance residue no larger than one
floating-point unit at the scale of the centered return cross-products is treated as
zero beta; an observable small positive or negative beta remains valid.

Sharpe, Sortino, and information ratios apply the corresponding source-resolution
test to volatility, downside deviation, and active-return dispersion. A small but
observable risk denominator therefore produces its ordinary finite ratio regardless
of the absolute return scale. Exact or resolution-limited zero risk with a zero
numerator is undefined; with a nonzero numerator it produces signed infinity. Treynor
uses every finite, nonzero beta as a signed divisor, including a small negative beta,
while an undefined beta keeps Treynor undefined.
