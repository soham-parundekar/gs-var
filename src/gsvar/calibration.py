"""Sizing the proxy book against Goldman's disclosed risk-category split.

Two books are built, and they answer different questions.

The *recalibrated* book is resized every year so that each sleeve's average
daily VaR equals the figure Goldman reported for that category in that year.
Its exposure mix therefore tracks the disclosures exactly, which removes the
exposure mix from the comparison and leaves only the cross-category
correlations in the public factor data. That is the right book for asking
whether the diversification effect comes out the way Goldman reports it. It
is not a forecast: the sizing for 2022 uses a figure published in 2023.

The *fixed* book is sized once, on a single base year, and then left alone.
Nothing about it responds to anything disclosed afterwards, so the path its
VaR takes from 2020 to 2025 is driven purely by what happened to market
volatility and correlation. That is the right book for the regime comparison
and the only honest one for backtesting, since its notionals were set before
any of the data it is scored on.
"""

from __future__ import annotations

import pandas as pd

from . import book
from . import historical_sim as hs

#: Average daily VaR, in $ millions, as first reported for each year. Column
#: order matches `book.CATEGORIES`.
DISCLOSURE_COLUMNS = {
    "interest_rates": "interest_rates",
    "equity_prices": "equity_prices",
    "currency_rates": "currency_rates",
    "commodity_prices": "commodity_prices",
}


def first_reported(disclosures: pd.DataFrame) -> pd.DataFrame:
    """One row per year, taking the earliest filing that reported it.

    Every 10-K restates the prior year, so most years appear twice. They
    almost always agree. Where they do not, the figure published at the time
    is the one used: Goldman changed the scope of VaR in the first quarter of
    2023 and conformed the 2022 comparative, and splicing a restated 2022 into
    a series of contemporaneous figures would put a methodology change inside
    the time series being studied.
    """
    ordered = disclosures.sort_values(["year", "source_fiscal_year"])
    return ordered.drop_duplicates(subset="year", keep="first").set_index("year")


def sleeve_targets(disclosures: pd.DataFrame, year: int) -> pd.Series:
    row = first_reported(disclosures).loc[year]
    return pd.Series({category: float(row[column]) for category, column in DISCLOSURE_COLUMNS.items()})


def calibrate(
    moves: pd.DataFrame,
    levels: pd.DataFrame,
    targets: pd.Series,
    year: int,
    settings: hs.Settings,
) -> list[book.Position]:
    """Size the book so each sleeve's average daily VaR over `year` hits target.

    The scaling is closed form. Profit and loss on every position here is
    proportional to its notional, so multiplying a sleeve's notionals by k
    multiplies every scenario outcome by k and therefore the average of its
    daily VaR by k as well. One division per sleeve lands exactly on target,
    and `calibration_error` afterwards is a check on that claim rather than a
    convergence criterion.
    """
    through_year = moves.loc[: f"{year}-12-31"]
    weighted = book.equal_risk_weights(
        book.default_book(), through_year, levels, settings.window, settings.quantile
    )

    trial = hs.run(weighted, moves, levels, settings, start=f"{year}-01-01", end=f"{year}-12-31")
    realised = pd.Series(
        {category: trial[f"var_{category}"].mean() for category in book.CATEGORIES}
    )
    return book.rescale_to_targets(weighted, realised, targets)


def calibration_error(
    positions: list[book.Position],
    moves: pd.DataFrame,
    levels: pd.DataFrame,
    targets: pd.Series,
    year: int,
    settings: hs.Settings,
) -> pd.DataFrame:
    """Average sleeve VaR after sizing, against the disclosed figures."""
    result = hs.run(positions, moves, levels, settings, start=f"{year}-01-01", end=f"{year}-12-31")
    achieved = pd.Series(
        {category: result[f"var_{category}"].mean() for category in book.CATEGORIES}
    )
    return pd.DataFrame(
        {
            "disclosed_usd_mm": targets,
            "model_usd_mm": achieved,
            "error_pct": (achieved - targets) / targets * 100.0,
        }
    )


def recalibrated_by_year(
    moves: pd.DataFrame,
    levels: pd.DataFrame,
    disclosures: pd.DataFrame,
    years: list[int],
    settings: hs.Settings,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run each year on a book sized to that year's own disclosed split.

    Returns the stitched daily series and the per-year sizing error.
    """
    daily, errors = [], []
    for year in years:
        targets = sleeve_targets(disclosures, year)
        positions = calibrate(moves, levels, targets, year, settings)

        result = hs.run(positions, moves, levels, settings, start=f"{year}-01-01", end=f"{year}-12-31")
        result["calibration_year"] = year
        daily.append(result)

        error = calibration_error(positions, moves, levels, targets, year, settings)
        error["year"] = year
        errors.append(error.reset_index(names="category"))

    return pd.concat(daily), pd.concat(errors, ignore_index=True)
