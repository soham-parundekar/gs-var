#!/usr/bin/env python3
"""Assemble the daily risk-factor panel the VaR engine runs on.

Writes two things. `factor_levels.csv` holds the level of every factor on
every day: index and fund closes, and yields in percent. `factor_moves.csv`
holds the one-day move in whatever unit that factor's revaluation needs, which
is a fractional return for anything priced in money and a change in percentage
points for anything quoted as a yield.

Keeping levels as well as moves is not redundant. Repricing a bond needs the
yield it is being shocked away from, not just the size of the shock, because
the same 25 basis point move is worth a different amount of money at a 0.5%
yield than at a 5% yield.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gsvar import config, factors  # noqa: E402

CONFIG = config.load()
ROOT = CONFIG.paths.root
RAW = CONFIG.paths.raw / "factors"
INTERIM = CONFIG.paths.interim
PROCESSED = CONFIG.paths.processed

# Two years before the first VaR date, so the lookback window is full from the
# start of the comparison period rather than growing into it.
START = CONFIG["sample"]["factor_start"]
END = CONFIG["sample"]["factor_end"]
MIN_COVERAGE = CONFIG["data"]["minimum_factor_coverage"]

RATE_FACTORS = [f"us_{t}y" for t in (2, 5, 10, 30)] + [f"eur_{t}y" for t in (2, 5, 10)]


def main() -> int:
    for directory in (RAW, INTERIM, PROCESSED):
        directory.mkdir(parents=True, exist_ok=True)

    tickers = list(factors.EQUITY_INDICES) + list(factors.FX_PAIRS) + list(factors.COMMODITY_FUNDS)
    prices = factors.market_closes(tickers, START, END, RAW)
    prices = prices.rename(
        columns={**factors.EQUITY_INDICES, **factors.FX_PAIRS, **factors.COMMODITY_FUNDS}
    )
    print(f"market series: {len(prices.columns)} factors, {len(prices)} raw dates")

    us = factors.treasury_par_curve(int(START[:4]), int(END[:4]) - 1, RAW)
    euro = factors.euro_area_curve(START, END, RAW)
    curves = us.join(euro, how="outer").sort_index()
    print(f"curve series: {len(curves.columns)} tenors, {len(curves)} raw dates")

    levels = factors.align_to_common_calendar(prices, curves, min_coverage=MIN_COVERAGE)
    print(f"common calendar: {len(levels)} days, {levels.index.min().date()} to {levels.index.max().date()}")

    price_factors = [c for c in levels.columns if c not in RATE_FACTORS]
    moves = pd.concat(
        [
            levels[price_factors].pct_change(),
            # Yields are already in percentage points, so a difference is the
            # shock the bond pricer expects. No scaling here: a 0.25 means
            # 25 basis points, consistently, everywhere downstream.
            levels[RATE_FACTORS].diff(),
        ],
        axis=1,
    ).dropna(how="any")[levels.columns]

    check(levels, moves)

    levels.to_csv(INTERIM / "factor_levels.csv")
    moves.to_csv(PROCESSED / "factor_moves.csv")
    print(f"wrote data/interim/factor_levels.csv and data/processed/factor_moves.csv ({len(moves)} days)")

    summary = pd.DataFrame(
        {
            "unit": ["return" if c in price_factors else "yield change (pp)" for c in moves.columns],
            "mean": moves.mean(),
            "std": moves.std(),
            "min": moves.min(),
            "max": moves.max(),
        }
    )
    summary.to_csv(PROCESSED / "factor_move_summary.csv")
    print("\n" + summary.round(5).to_string())
    return 0


def check(levels: pd.DataFrame, moves: pd.DataFrame) -> None:
    """Catch the failures that would otherwise show up as a plausible VaR.

    A duplicated date, a zero price, or a run of identical closes all produce
    a number at the end of the pipeline rather than an error, which is the
    dangerous kind of data problem.
    """
    if levels.index.has_duplicates:
        raise ValueError("duplicate dates in the factor panel")
    if not levels.index.is_monotonic_increasing:
        raise ValueError("factor panel is not sorted by date")

    priced = [c for c in levels.columns if c not in RATE_FACTORS]
    non_positive = [c for c in priced if (levels[c] <= 0).any()]
    if non_positive:
        raise ValueError(f"non-positive prices, which break return calculations: {non_positive}")

    # A market that closed but was forward-filled shows up as a long run of
    # exact zeros. The tolerable run length is not the same for both kinds of
    # factor. A traded price repeating to the cent for days on end means a
    # stale feed. A Treasury yield repeating does not: the curve is quoted to
    # the basis point, and with the two-year note at 0.13% through the second
    # half of 2020 it genuinely did not move on 19% of days. Flagging that
    # would be flagging the monetary policy of 2020.
    limits = {True: 15, False: 5}
    for column in moves.columns:
        runs = (moves[column] == 0).astype(int).groupby((moves[column] != 0).cumsum()).sum()
        if runs.max() >= limits[column in RATE_FACTORS]:
            raise ValueError(f"{column} has {runs.max()} consecutive unchanged days")


if __name__ == "__main__":
    raise SystemExit(main())
