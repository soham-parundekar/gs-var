"""Conditional volatility estimates for the volatility-weighted VaR variant.

Plain historical simulation treats a return from twenty months ago as equally
informative about tomorrow as yesterday's. That assumption has two visible
consequences. The model is slow to react when volatility rises, because the
calm days still in the window hold the percentile down. And it is slow to
come back down afterwards, because a single violent day keeps inflating VaR
for the full length of the window and then drops out of it on one arbitrary
date, which puts a step in the VaR series that corresponds to nothing that
happened in the market. The step is usually called a ghost.

Hull and White's fix is to rescale each historical return by the ratio of
today's volatility to the volatility that prevailed when the return happened,
so the scenario set is restated in today's volatility units before the
percentile is taken.

Both estimators here are causal. The value stamped with date t is a forecast
for t+1 built only from information available at the close of t, which is
what lets the volatility-weighted model be backtested on the same footing as
the unweighted one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

RISKMETRICS_LAMBDA = 0.94  # the standard daily decay factor
BURN_IN = 100  # days used to seed the recursion


def ewma_forecast(moves: pd.DataFrame, decay: float = RISKMETRICS_LAMBDA) -> pd.DataFrame:
    """One-day-ahead volatility forecasts by exponentially weighted variance.

    The value at date t is the forecast for t+1, formed from the squared move
    on t and the previous forecast, so it never uses a return it could not
    have seen. The recursion is seeded with the sample standard deviation of
    the first `BURN_IN` days, and those seeded days are returned as missing
    rather than as a number the data does not support.
    """
    if not 0.0 < decay < 1.0:
        raise ValueError("decay must lie strictly between 0 and 1")
    if len(moves) <= BURN_IN:
        raise ValueError("not enough observations to seed the recursion")

    squared = moves.to_numpy() ** 2
    variance = np.full(squared.shape, np.nan)
    # The recursion updates a second moment about zero, so the seed is the
    # mean squared move over the burn-in, not the variance about its mean.
    # Daily means are tiny next to daily volatility, but the two are not the
    # same quantity and mixing them puts a small bias in every forecast.
    state = np.nanmean(squared[:BURN_IN], axis=0)

    for row in range(BURN_IN, len(squared)):
        state = decay * state + (1.0 - decay) * squared[row]
        variance[row] = state

    return pd.DataFrame(np.sqrt(variance), index=moves.index, columns=moves.columns)


def garch_forecast(
    moves: pd.DataFrame, refit_years: list[int] | None = None, min_history: int = 750
) -> pd.DataFrame:
    """One-day-ahead forecasts from a GARCH(1,1) refitted each calendar year.

    Fitting once over the whole sample would let the 2020 and 2022 shocks set
    the parameters used to forecast 2017, which is look-ahead of exactly the
    kind a backtest is supposed to rule out. The model is therefore refitted
    at the start of each year on the history available at that point, and the
    fitted parameters are then run forward through the year.

    Returns `NaN` before the first fit has enough history, so callers must
    drop those dates rather than treat them as zero volatility.
    """
    from arch import arch_model

    years = refit_years or sorted({d.year for d in moves.index})
    out = pd.DataFrame(np.nan, index=moves.index, columns=moves.columns)

    for column in moves.columns:
        series = moves[column].dropna()
        # Scaling matters: yield changes are O(0.05) in percentage points and
        # the optimiser behaves poorly on variances that small.
        scale = float(series.std())
        scaled = series / scale

        for year in years:
            cutoff = pd.Timestamp(f"{year}-01-01")
            history = scaled.loc[scaled.index < cutoff]
            if len(history) < min_history:
                continue

            fitted = arch_model(history, vol="GARCH", p=1, q=1, mean="Zero", dist="normal").fit(
                disp="off", show_warning=False
            )
            omega, alpha, beta = (
                fitted.params["omega"],
                fitted.params["alpha[1]"],
                fitted.params["beta[1]"],
            )

            # Carry the recursion forward through the year with frozen
            # parameters, starting from the last in-sample conditional variance.
            forward = scaled.loc[scaled.index >= cutoff]
            forward = forward.loc[forward.index.year == year]
            if forward.empty:
                continue

            variance = float(fitted.conditional_volatility.iloc[-1] ** 2)
            shock = float(history.iloc[-1] ** 2)
            for date, value in forward.items():
                variance = omega + alpha * shock + beta * variance
                out.loc[date, column] = np.sqrt(variance) * scale
                shock = float(value**2)

    return out


def rescaled_scenarios(
    window: pd.DataFrame, applied_volatility: pd.DataFrame, current: pd.Series
) -> pd.DataFrame:
    """Restate a scenario window in today's volatility units.

    `applied_volatility` holds, for each historical day, the conditional
    volatility that was in force for that day's return. `current` is today's
    forecast for tomorrow. The ratio of the two is the Hull-White scaling.
    """
    scale = current.to_numpy()[None, :] / applied_volatility.loc[window.index].to_numpy()
    if not np.isfinite(scale).all():
        raise ValueError("volatility estimates are missing over the requested window")
    return pd.DataFrame(window.to_numpy() * scale, index=window.index, columns=window.columns)
