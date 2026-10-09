"""The historical simulation VaR engine.

Goldman describes its own method in one sentence, repeated with little change
across every filing in the sample: a one-day time horizon, a 95% confidence
level, a single VaR model capturing interest rate, equity price, currency rate
and commodity price risk, and historical simulations with full valuation of
approximately 70,000 market factors. This module follows that description on
seventeen factors instead of seventy thousand.

The timing convention is the part worth reading carefully, because getting it
wrong produces a model that looks better than it is. VaR stamped with date t
uses the book and market levels at the close of t and scenarios drawn from
days up to and including t. It is compared against the profit and loss
realised on t+1. Goldman states the same convention: daily net revenues are
compared with VaR calculated as of the end of the prior business day. No
quantity dated t+1 enters the VaR dated t.

Window length is a choice Goldman does not disclose. Two years of daily
scenarios is the common industry setting and is the default here; one and
three years are run alongside it as a check that the conclusions do not
depend on the number.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .book import CATEGORIES, Position, by_category, scenario_returns
from .volatility import rescaled_scenarios


@dataclass(frozen=True)
class Settings:
    window: int = 502  # about two years of trading days
    quantile: float = 0.05  # the 5% worst scenario, for a 95% VaR
    interpolate: bool = True


def var_from_scenarios(pnl: np.ndarray, settings: Settings) -> float:
    """Loss, reported positive, at the configured confidence level.

    Goldman does not disclose how it reads the percentile off a finite
    scenario set, and with 502 scenarios the 5% point falls between the 25th
    and 26th worst. Linear interpolation is the default. The discrete reading
    takes the 26th worst outright, which is the more conservative of the two
    and is what a bank wanting to avoid understating risk would pick. The
    difference is a fraction of a percent of the VaR level and is reported in
    the robustness table rather than assumed away.
    """
    if settings.interpolate:
        return float(-np.percentile(pnl, settings.quantile * 100.0))

    ordered = np.sort(pnl)
    # The conservative reading is the ceiling: with 502 scenarios at 5% the
    # 25.1st worst rounds up to the 26th. Flooring instead would agree
    # whenever the product is fractional and silently pick the wrong side
    # whenever it is a whole number, which is exactly the case a test is
    # likely to be written around.
    index = max(int(np.ceil(settings.quantile * len(ordered))) - 1, 0)
    return float(-ordered[index])


def run(
    positions: list[Position],
    moves: pd.DataFrame,
    levels: pd.DataFrame,
    settings: Settings = Settings(),
    start: str | None = None,
    end: str | None = None,
    volatility: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Daily VaR by category and in total, plus the next day's realised result.

    `volatility` switches on the Hull-White variant. It holds a one-day-ahead
    conditional volatility forecast for each factor, stamped with the date the
    forecast was made, so the value at t is the forecast for t+1. Each
    scenario in the window is then restated in today's volatility units before
    the percentile is read off.

    Realised profit and loss always comes from the unscaled moves. What the
    book actually made on t+1 is not a function of which model was used to
    forecast it, and scaling it would make the backtest circular.
    """
    grouped = by_category(positions)

    # The forecast stamped t-1 is the one that applied to the return realised
    # on t, which is the denominator of the Hull-White ratio.
    applied_volatility = None if volatility is None else volatility.shift(1)

    dates = moves.index
    first = settings.window - 1
    if start is not None:
        first = max(first, int(dates.searchsorted(pd.Timestamp(start))))
    # The last valuation date needs a following day to score against.
    last = len(dates) - 2
    if end is not None:
        last = min(last, int(dates.searchsorted(pd.Timestamp(end), side="right")) - 1)

    if first > last:
        raise ValueError("no valuation dates: window longer than the requested period")

    records = []
    for i in range(first, last + 1):
        valuation_date = dates[i]
        window = moves.iloc[i - settings.window + 1 : i + 1]
        if applied_volatility is not None:
            window = rescaled_scenarios(
                window, applied_volatility, volatility.loc[valuation_date]
            )
        base = levels.loc[valuation_date]

        row: dict[str, float | pd.Timestamp] = {"date": valuation_date}
        total = np.zeros(len(window))

        for category in CATEGORIES:
            sleeve = np.zeros(len(window))
            for position in grouped[category]:
                sleeve += position.notional * scenario_returns(position, window, base)
            total += sleeve
            row[f"var_{category}"] = var_from_scenarios(sleeve, settings)

        row["var_total"] = var_from_scenarios(total, settings)
        row["sum_category_var"] = sum(row[f"var_{c}"] for c in CATEGORIES)
        row["diversification_effect"] = row["var_total"] - row["sum_category_var"]

        # What the book actually made the next day, marked from today's levels.
        next_move = moves.iloc[[i + 1]]
        realised = 0.0
        for position in positions:
            realised += position.notional * float(scenario_returns(position, next_move, base)[0])
        row["realised_pnl_next"] = realised
        row["pnl_date"] = dates[i + 1]

        records.append(row)

    frame = pd.DataFrame(records).set_index("date")
    _check(frame, {category for category in CATEGORIES if grouped[category]})
    return frame


#: Share of days on which a positive diversification effect stops looking like
#: VaR's known lack of subadditivity and starts looking like a sign error.
_SUBADDITIVITY_TOLERANCE = 0.01


def _check(frame: pd.DataFrame, populated: set[str]) -> None:
    """Assertions that would have caught every sign error made while writing this.

    The diversification effect is almost always negative: summing four
    standalone category VaRs treats the categories as though they lose
    together, and letting them move as they historically did will normally do
    better than that.

    Almost always, not always. VaR is not a subadditive risk measure, and on a
    scenario set with a sufficiently awkward tail the whole book really can
    show a larger loss quantile than the sum of its parts. That is a property
    of the measure rather than a defect in this code, and it is the reason
    expected shortfall exists. So a handful of such days is recorded and
    allowed; a book showing them on more than one day in a hundred is a sign
    error, because a genuine sign error produces them on nearly every day.
    """
    if (frame["var_total"] <= 0).any():
        raise ValueError("total VaR must be a positive loss")
    for category in populated:
        if (frame[f"var_{category}"] <= 0).any():
            raise ValueError(f"{category} VaR must be a positive loss")

    tolerance = 1e-9 * frame["sum_category_var"].abs().max()
    offenders = frame.index[frame["diversification_effect"] > tolerance]
    share = len(offenders) / len(frame)
    if share > _SUBADDITIVITY_TOLERANCE:
        raise ValueError(
            f"diversification effect is positive on {len(offenders)} of {len(frame)} days "
            f"({share:.1%}), first on {offenders[0].date()}. Occasional days are legitimate "
            "because VaR is not subadditive, but this many points to a sign error"
        )
    frame.attrs["days_without_diversification_benefit"] = int(len(offenders))


def diversification_ratio(frame: pd.DataFrame) -> pd.Series:
    """Diversification effect as a percentage of the summed category VaRs.

    This is the quantity that can be compared against Goldman directly. The
    dollar level of this book is a normalisation and carries no information;
    the ratio does not depend on it.
    """
    return -frame["diversification_effect"] / frame["sum_category_var"] * 100.0


def annual_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Average daily VaR by calendar year, in the shape Goldman reports it."""
    columns = [f"var_{c}" for c in CATEGORIES] + [
        "var_total",
        "sum_category_var",
        "diversification_effect",
    ]
    yearly = frame.groupby(frame.index.year)[columns].mean()
    yearly["diversification_pct"] = (
        -yearly["diversification_effect"] / yearly["sum_category_var"] * 100.0
    )
    yearly["trading_days"] = frame.groupby(frame.index.year).size()
    yearly.index.name = "year"
    return yearly
