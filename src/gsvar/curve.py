"""Bond pricing for the interest-rate sleeve.

This module is what makes "full revaluation" mean something in this project.
Equity, currency and commodity positions are linear in their risk factor, so
repricing them is a multiplication and the distinction between full
revaluation and a delta approximation does not arise. Bonds are different:
price is a convex function of yield, and in a year like 2022, when the
two-year Treasury yield moved more than 400 basis points, the gap between
discounting the cashflows again and multiplying by duration is large enough
to change the VaR number.

Two instrument types appear, one per currency, each priced in the convention
its data source publishes:

    US      Treasury quotes a par yield curve, so the book holds par coupon
            bonds. A par bond's yield to maturity is the par yield by
            construction, which means discounting its own cashflows at that
            yield reprices it exactly, with no curve interpolation.

    Euro    The ECB publishes zero-coupon spot rates, so the book holds
            zero-coupon bonds. Again exact, again no interpolation.

The alternative would be to bootstrap one convention into the other, which
needs a yield at every coupon date and therefore an interpolation assumption
the data does not support. A zero has a longer duration than a par bond of
the same maturity, so the two sleeves are not interchangeable per unit of
notional. The position sizing in `book.py` absorbs that, since it targets a
risk contribution rather than a notional.

Positions are constant-maturity: each day the book is treated as holding a
freshly struck bond at the stated tenor. That matches how the par curve
itself is constructed, and it avoids a ten-year backtest in which the
two-year bond quietly matures halfway through.
"""

from __future__ import annotations

import numpy as np

US_COUPON_FREQUENCY = 2  # Treasury coupons are semiannual.


def price_par_bond(
    coupon_pct: float, yield_pct: float, maturity_years: float, frequency: int = US_COUPON_FREQUENCY
) -> float:
    """Clean price per 100 face of a coupon bond, discounted at a flat yield.

    Parameters are in percent, so a 4.25% yield is passed as 4.25.
    """
    periods = int(round(maturity_years * frequency))
    coupon = coupon_pct / 100.0 / frequency * 100.0
    rate = yield_pct / 100.0 / frequency

    times = np.arange(1, periods + 1)
    if abs(rate) < 1e-12:
        return float(coupon * periods + 100.0)

    discounts = (1.0 + rate) ** -times
    return float(coupon * discounts.sum() + 100.0 * discounts[-1])


def price_zero(yield_pct: float, maturity_years: float) -> float:
    """Price per 100 face of an annually compounded zero-coupon bond.

    The ECB curve goes negative for much of 2015-2021, which is a real
    market condition rather than a data problem, so the discount factor is
    written in a form that stays well behaved below zero.
    """
    rate = yield_pct / 100.0
    if rate <= -1.0:
        raise ValueError(f"spot rate of {yield_pct}% implies a non-positive discount factor")
    return float(100.0 * (1.0 + rate) ** -maturity_years)


def par_bond_return(
    base_yield_pct: float,
    yield_change_pct: float,
    maturity_years: float,
    frequency: int = US_COUPON_FREQUENCY,
) -> float:
    """Fractional one-day price return on a par bond for a given yield move.

    The bond starts at par, so its coupon equals the current yield and its
    starting price is 100 by construction. Repricing at the shocked yield and
    dividing gives a return that does not depend on notional, which is what
    lets the position sizing scale exactly.
    """
    shocked = price_par_bond(
        coupon_pct=base_yield_pct,
        yield_pct=base_yield_pct + yield_change_pct,
        maturity_years=maturity_years,
        frequency=frequency,
    )
    return shocked / 100.0 - 1.0


def zero_bond_return(
    base_yield_pct: float, yield_change_pct: float, maturity_years: float
) -> float:
    """Fractional one-day price return on a zero-coupon bond."""
    start = price_zero(base_yield_pct, maturity_years)
    shocked = price_zero(base_yield_pct + yield_change_pct, maturity_years)
    return shocked / start - 1.0


def par_bond_return_vector(
    base_yield_pct: float,
    yield_changes_pct: np.ndarray,
    maturity_years: float,
    frequency: int = US_COUPON_FREQUENCY,
) -> np.ndarray:
    """`par_bond_return` across a whole scenario set at once.

    The engine reprices every bond under every historical scenario on every
    valuation date. Done one scenario at a time that is several hundred
    million discount-factor evaluations in Python; done as an array it is a
    handful of seconds, and the arithmetic is identical.
    """
    periods = int(round(maturity_years * frequency))
    coupon = base_yield_pct / 100.0 / frequency * 100.0
    rates = (base_yield_pct + np.asarray(yield_changes_pct, dtype=float)) / 100.0 / frequency

    times = np.arange(1, periods + 1)
    discounts = np.power(1.0 + rates[:, None], -times[None, :])
    prices = coupon * discounts.sum(axis=1) + 100.0 * discounts[:, -1]
    return prices / 100.0 - 1.0


def zero_bond_return_vector(
    base_yield_pct: float, yield_changes_pct: np.ndarray, maturity_years: float
) -> np.ndarray:
    """`zero_bond_return` across a whole scenario set at once."""
    start = (1.0 + base_yield_pct / 100.0) ** -maturity_years
    shocked_rates = (base_yield_pct + np.asarray(yield_changes_pct, dtype=float)) / 100.0
    if np.any(shocked_rates <= -1.0):
        raise ValueError("a scenario implies a non-positive discount factor")
    return np.power(1.0 + shocked_rates, -maturity_years) / start - 1.0


def modified_duration_par_bond(
    yield_pct: float, maturity_years: float, frequency: int = US_COUPON_FREQUENCY
) -> float:
    """Modified duration of a par bond, in years.

    Used only for the first-order comparison that isolates how much of the
    rate sleeve's VaR comes from convexity. It is not used to price anything.
    """
    periods = int(round(maturity_years * frequency))
    rate = yield_pct / 100.0 / frequency
    coupon = yield_pct / 100.0 / frequency * 100.0

    times = np.arange(1, periods + 1)
    if abs(rate) < 1e-12:
        weighted = (coupon * times).sum() + 100.0 * periods
        return float(weighted / 100.0 / frequency)

    discounts = (1.0 + rate) ** -times
    cashflows = np.full(periods, coupon)
    cashflows[-1] += 100.0
    macaulay_periods = (times * cashflows * discounts).sum() / 100.0
    return float(macaulay_periods / frequency / (1.0 + rate))


def duration_approximation_return(
    base_yield_pct: float,
    yield_change_pct: float,
    maturity_years: float,
    frequency: int = US_COUPON_FREQUENCY,
    zero_coupon: bool = False,
) -> float:
    """First-order price return, ignoring convexity.

    This is the delta-normal view of a bond. Comparing it against
    `par_bond_return` on the same yield moves shows what full revaluation
    buys, and the answer is small for ordinary days and not small for 2022.
    """
    if zero_coupon:
        # Modified duration of an annually compounded zero.
        duration = maturity_years / (1.0 + base_yield_pct / 100.0)
    else:
        duration = modified_duration_par_bond(base_yield_pct, maturity_years, frequency)
    return float(-duration * yield_change_pct / 100.0)
