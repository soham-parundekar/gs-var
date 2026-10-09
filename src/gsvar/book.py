"""The proxy book: what it holds, and how it is sized against the disclosures.

The honest limit of this project sits in this file. Goldman does not publish
positions, so there is no way to rebuild the trading book. What the 10-K does
publish is the average daily VaR of each of the four risk categories, and that
is enough to pin down the relative size of four sleeves of public risk factors.
The result is a book whose risk is split the way Goldman's disclosed risk is
split. It is not Goldman's book and nothing here should be read as a claim
about their positions.

Sizing runs in two steps.

Within a sleeve, instruments are weighted so that each contributes the same
standalone VaR. Equal notional would not do. At the 2019 year-end curve a
thirty-year par bond has a modified duration of 21.5 against 2.0 for a
two-year note, and once the different volatility of the two yields is counted
it carries roughly fifteen times the one-day risk per unit of notional. An
equally sized rates sleeve would be a thirty-year position with rounding
errors attached.

The sleeve as a whole is then scaled so its average daily standalone VaR over
the calibration year equals the figure Goldman disclosed for that category and
year. The scaling is exact rather than iterative, because the profit and loss
on every position in this book is proportional to its notional: scenario
returns do not depend on position size, so multiplying every notional in a
sleeve by k multiplies every scenario profit and loss by k and therefore
multiplies any percentile of that distribution by k as well.

That exactness is the point of the design. The sum of the four category VaRs
is matched to Goldman's by construction, so it carries no information. The
total book VaR is not matched, and neither is the diversification effect.
Those come out of the cross-category correlations in the public factor data,
and comparing them against the disclosures is the experiment.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import curve

CATEGORIES = ("interest_rates", "equity_prices", "currency_rates", "commodity_prices")

LINEAR = "linear"
PAR_BOND = "par_bond"
ZERO_BOND = "zero_bond"


@dataclass(frozen=True)
class Position:
    """One holding, tied to the single risk factor that reprices it."""

    factor: str
    category: str
    kind: str
    notional: float
    maturity_years: float | None = None

    def scaled(self, multiplier: float) -> "Position":
        return Position(
            self.factor, self.category, self.kind, self.notional * multiplier, self.maturity_years
        )


def default_book() -> list[Position]:
    """The instrument set, before sizing. Notionals are placeholders of 1.

    Everything is held long. A dealer runs both ways and the net sign of each
    of Goldman's sleeves is not disclosed, so a direction had to be chosen;
    long is the one that needs no further justification. It matters, because
    the sign pattern across sleeves drives the diversification effect, and
    `sign_variants` in the robustness analysis works through the alternatives
    rather than leaving the choice buried here.
    """
    positions = [
        Position("us_2y", "interest_rates", PAR_BOND, 1.0, 2.0),
        Position("us_5y", "interest_rates", PAR_BOND, 1.0, 5.0),
        Position("us_10y", "interest_rates", PAR_BOND, 1.0, 10.0),
        Position("us_30y", "interest_rates", PAR_BOND, 1.0, 30.0),
        Position("eur_2y", "interest_rates", ZERO_BOND, 1.0, 2.0),
        Position("eur_5y", "interest_rates", ZERO_BOND, 1.0, 5.0),
        Position("eur_10y", "interest_rates", ZERO_BOND, 1.0, 10.0),
        Position("equity_us", "equity_prices", LINEAR, 1.0),
        Position("equity_europe", "equity_prices", LINEAR, 1.0),
        Position("equity_japan", "equity_prices", LINEAR, 1.0),
        Position("equity_em", "equity_prices", LINEAR, 1.0),
        Position("fx_eurusd", "currency_rates", LINEAR, 1.0),
        Position("fx_usdjpy", "currency_rates", LINEAR, 1.0),
        Position("fx_gbpusd", "currency_rates", LINEAR, 1.0),
        Position("commodity_gold", "commodity_prices", LINEAR, 1.0),
        Position("commodity_oil", "commodity_prices", LINEAR, 1.0),
        Position("commodity_base_metals", "commodity_prices", LINEAR, 1.0),
    ]
    return positions


def scenario_returns(
    position: Position, moves: pd.DataFrame, base_levels: pd.Series, linearised: bool = False
) -> np.ndarray:
    """Fractional profit and loss per unit of notional, one value per scenario.

    For a linear holding this is just the factor's return. For a bond it is a
    full repricing: the cashflows are discounted again at the shocked yield,
    not multiplied by a duration. `base_levels` carries the yield the shock is
    applied to, which is why the engine keeps levels around and not only moves.

    Setting `linearised` replaces the bond repricing with its first-order
    duration approximation, which is what a delta-normal model would use. It
    exists so the two can be run against the same scenarios and the convexity
    contribution read off the difference. It is never used for the headline
    numbers.
    """
    shocks = moves[position.factor].to_numpy()

    if position.kind == LINEAR:
        return shocks

    level = float(base_levels[position.factor])
    if linearised:
        duration = (
            position.maturity_years / (1.0 + level / 100.0)
            if position.kind == ZERO_BOND
            else curve.modified_duration_par_bond(level, position.maturity_years)
        )
        return -duration * shocks / 100.0

    if position.kind == PAR_BOND:
        return curve.par_bond_return_vector(level, shocks, position.maturity_years)
    if position.kind == ZERO_BOND:
        return curve.zero_bond_return_vector(level, shocks, position.maturity_years)
    raise ValueError(f"unknown position type {position.kind!r}")


def profit_and_loss(
    positions: list[Position], moves: pd.DataFrame, base_levels: pd.Series
) -> np.ndarray:
    """Book-level profit and loss in dollars, one value per scenario row."""
    total = np.zeros(len(moves))
    for position in positions:
        total += position.notional * scenario_returns(position, moves, base_levels)
    return total


def equal_risk_weights(
    positions: list[Position],
    moves: pd.DataFrame,
    levels: pd.DataFrame,
    window: int,
    quantile: float,
) -> list[Position]:
    """Weight instruments inside each sleeve to equal standalone VaR.

    Risk per unit notional is measured once, over the final `window` days of
    the calibration sample, and held fixed thereafter. Re-measuring it daily
    would turn the book into a risk-parity strategy that rebalances on
    yesterday's volatility, and a strategy is a different object from the
    static proxy portfolio this project is supposed to be testing.
    """
    scenarios = moves.iloc[-window:]
    base = levels.loc[scenarios.index[-1]]

    unit_risk: dict[str, float] = {}
    for position in positions:
        returns = scenario_returns(position, scenarios, base)
        unit_risk[position.factor] = float(-np.percentile(returns, quantile * 100.0))

    weighted = []
    for position in positions:
        risk = unit_risk[position.factor]
        if risk <= 0:
            raise ValueError(
                f"{position.factor} has a non-positive one-day loss quantile, "
                "so it cannot be risk weighted"
            )
        weighted.append(position.scaled(1.0 / risk))
    return weighted


def by_category(positions: list[Position]) -> dict[str, list[Position]]:
    grouped: dict[str, list[Position]] = {category: [] for category in CATEGORIES}
    for position in positions:
        grouped[position.category].append(position)
    return grouped


def rescale_to_targets(
    positions: list[Position], realised: pd.Series, targets: pd.Series
) -> list[Position]:
    """Scale each sleeve so its average daily VaR hits the disclosed figure.

    `realised` is the average daily standalone VaR each sleeve produced at the
    current notionals; `targets` is what Goldman reported. Because profit and
    loss is proportional to notional, the ratio of the two is the multiplier,
    with no search required.
    """
    multipliers = {}
    for category in CATEGORIES:
        if realised[category] <= 0:
            raise ValueError(f"{category} produced a non-positive average VaR")
        multipliers[category] = float(targets[category]) / float(realised[category])

    return [position.scaled(multipliers[position.category]) for position in positions]


def sign_variants(positions: list[Position]) -> dict[str, list[Position]]:
    """The book under every combination of sleeve directions.

    The base case holds all four sleeves long, which is a choice rather than
    a finding: Goldman does not disclose the direction of its net exposures,
    and a market maker's inventory is not reliably long anything. The choice
    barely moves a sleeve's standalone VaR, since flipping the sign of a
    linear position only reflects its profit and loss distribution and daily
    returns are close to symmetric. It moves the diversification effect a
    great deal, because that depends entirely on how the sleeves line up
    against each other.

    Sixteen combinations is the whole space, so the robustness analysis runs
    all of them instead of sampling. Each is labelled by the signs in the
    order given by `CATEGORIES`, so "+-++" is short equities and long the rest.
    """
    from itertools import product

    variants = {}
    for combination in product((1, -1), repeat=len(CATEGORIES)):
        signs = dict(zip(CATEGORIES, combination))
        label = "".join("+" if signs[c] > 0 else "-" for c in CATEGORIES)
        variants[label] = [p.scaled(signs[p.category]) for p in positions]
    return variants


def notionals_table(positions: list[Position]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "factor": p.factor,
                "category": p.category,
                "kind": p.kind,
                "maturity_years": p.maturity_years,
                "notional_usd_mm": p.notional,
            }
            for p in positions
        ]
    )
