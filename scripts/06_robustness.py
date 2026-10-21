#!/usr/bin/env python3
"""How much of the result survives the choices that had to be made.

Four of them are tested here.

Sleeve direction is the one that matters. The base book is long everything
because Goldman does not disclose the sign of its net exposures, and the
diversification effect depends on those signs far more than on anything else
in the specification. All sixteen combinations are run.

Lookback window is disclosed, at five years, and that is the baseline. One,
two and three years are run beside it anyway, because the gradient across
them is what says how much of any stability gap belongs to the window rather
than to the book being held fixed.

Age weighting is disclosed in kind but not in degree: the filings say the
importance of the data reduces over time without giving the rate. Equal
weighting is the control; two decay rates from the literature bracket it.

Percentile convention is undisclosed. Linear interpolation is the default;
the discrete order statistic is the conservative alternative.
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gsvar import backtest as bt  # noqa: E402
from gsvar import book, calibration, config  # noqa: E402
from gsvar import historical_sim as hs  # noqa: E402

CONFIG = config.load()
ROOT = CONFIG.paths.root
PROCESSED = CONFIG.paths.processed
BASE_YEAR = CONFIG.base_year
YEARS = CONFIG.years


def main() -> int:
    moves = pd.read_csv(PROCESSED / "factor_moves.csv", index_col=0, parse_dates=True)
    levels = pd.read_csv(CONFIG.paths.interim / "factor_levels.csv", index_col=0, parse_dates=True)
    disclosures = pd.read_csv(PROCESSED / "gs_var_average_daily.csv")
    disclosed = calibration.first_reported(disclosures)

    goldman = (
        -disclosed["diversification_effect"]
        / disclosed[list(book.CATEGORIES)].sum(axis=1)
        * 100.0
    ).loc[CONFIG.years[0]:CONFIG.years[-1]]

    print("Goldman's disclosed diversification effect, percent of summed category VaR:")
    print(f"  range {goldman.min():.1f} to {goldman.max():.1f}, mean {goldman.mean():.1f}, "
          f"standard deviation {goldman.std():.1f}\n")

    signs = sign_sweep(moves, levels, disclosures, goldman)
    windows = window_sweep(moves, levels, disclosures, goldman)
    weighting = weighting_sweep(moves, levels, disclosures, goldman)
    conventions = percentile_sweep(moves, levels, disclosures)

    signs.to_csv(PROCESSED / "robustness_sign_variants.csv", index=False)
    windows.to_csv(PROCESSED / "robustness_windows.csv", index=False)
    weighting.to_csv(PROCESSED / "robustness_age_weighting.csv", index=False)
    conventions.to_csv(PROCESSED / "robustness_percentile.csv", index=False)
    return 0


def sign_sweep(moves, levels, disclosures, goldman) -> pd.DataFrame:
    """Diversification effect under all sixteen sleeve-direction combinations."""
    settings = CONFIG.settings()
    targets = calibration.sleeve_targets(disclosures, BASE_YEAR)
    base = calibration.calibrate(moves, levels, targets, BASE_YEAR, settings)

    rows = []
    for label, positions in book.sign_variants(base).items():
        daily = hs.run(positions, moves, levels, settings, start=CONFIG.start, end=CONFIG.end)
        annual = hs.annual_summary(daily)
        ratio = annual["diversification_pct"]
        gap = (ratio - goldman.reindex(ratio.index)).abs()

        rows.append(
            {
                "signs": label,
                "mean_diversification_pct": ratio.mean(),
                "min_pct": ratio.min(),
                "max_pct": ratio.max(),
                "std_across_years": ratio.std(),
                "mean_absolute_gap_vs_goldman_pp": gap.mean(),
            }
        )

    frame = pd.DataFrame(rows).sort_values("mean_absolute_gap_vs_goldman_pp")
    print("sleeve directions, ordered by how close they land to the disclosures")
    print("(order of signs: interest rates, equity, currency, commodity)")
    print(frame.round(2).to_string(index=False))
    print(f"\n  Goldman's year-to-year standard deviation is {goldman.std():.2f} pp; "
          f"the steadiest sign combination manages {frame['std_across_years'].min():.2f} pp\n")
    return frame


def window_sweep(moves, levels, disclosures, goldman) -> pd.DataFrame:
    """Diversification and backtest results at one, two and three years."""
    rows = []
    for window in CONFIG["engine"]["alternative_windows"]:
        settings = CONFIG.settings(window=window)
        targets = calibration.sleeve_targets(disclosures, BASE_YEAR)
        positions = calibration.calibrate(moves, levels, targets, BASE_YEAR, settings)
        daily = hs.run(positions, moves, levels, settings, start=CONFIG.start, end=CONFIG.end)
        annual = hs.annual_summary(daily)

        scored = bt.summary(daily["realised_pnl_next"], daily["var_total"], settings.quantile)
        ratio = annual["diversification_pct"]
        rows.append(
            {
                "window_days": window,
                "mean_diversification_pct": ratio.mean(),
                "std_across_years": ratio.std(),
                "mean_absolute_gap_vs_goldman_pp": (ratio - goldman.reindex(ratio.index)).abs().mean(),
                "exceptions": scored["exceptions"],
                "exception_rate_pct": scored["exception_rate_pct"],
                "kupiec_p_value": scored["kupiec_p_value"],
                "independence_p_value": scored["independence_p_value"],
            }
        )

    frame = pd.DataFrame(rows)
    print("lookback window")
    print(frame.round(3).to_string(index=False), "\n")
    return frame


def weighting_sweep(moves, levels, disclosures, goldman) -> pd.DataFrame:
    """Diversification and backtest results across scenario age-decay rates.

    Run at the disclosed window, so the only thing moving between rows is how
    fast the weight on an old scenario falls away. The reason this matters for
    the headline result is that age weighting is the mechanism by which a bank
    can hold a risk measure responsive to current conditions without changing
    its positions, which is the explanation a static book cannot offer.
    """
    rows = []
    for decay in CONFIG["engine"]["alternative_age_decays"]:
        settings = CONFIG.settings(age_decay=decay)
        targets = calibration.sleeve_targets(disclosures, BASE_YEAR)
        positions = calibration.calibrate(moves, levels, targets, BASE_YEAR, settings)
        daily = hs.run(positions, moves, levels, settings, start=CONFIG.start, end=CONFIG.end)
        annual = hs.annual_summary(daily)

        scored = bt.summary(daily["realised_pnl_next"], daily["var_total"], settings.quantile)
        ratio = annual["diversification_pct"]
        # Half-life in trading days, which is the readable form of the rate.
        half_life = float("inf") if decay == 1.0 else math.log(0.5) / math.log(decay)
        rows.append(
            {
                "age_decay": decay,
                "half_life_days": half_life,
                "window_days": settings.window,
                "mean_diversification_pct": ratio.mean(),
                "std_across_years": ratio.std(),
                "mean_absolute_gap_vs_goldman_pp": (ratio - goldman.reindex(ratio.index)).abs().mean(),
                "exceptions": scored["exceptions"],
                "exception_rate_pct": scored["exception_rate_pct"],
                "kupiec_p_value": scored["kupiec_p_value"],
                "independence_p_value": scored["independence_p_value"],
            }
        )

    frame = pd.DataFrame(rows)
    print("scenario age weighting, at the disclosed five-year window")
    print(frame.round(3).to_string(index=False))
    print(f"  Goldman's year-to-year standard deviation is {goldman.std():.2f} pp; "
          f"the steadiest decay rate here manages {frame['std_across_years'].min():.2f} pp\n")
    return frame


def percentile_sweep(moves, levels, disclosures) -> pd.DataFrame:
    """Interpolated against discrete reading of the loss quantile."""
    rows = []
    for interpolate in (True, False):
        settings = replace(CONFIG.settings(), interpolate=interpolate)
        targets = calibration.sleeve_targets(disclosures, BASE_YEAR)
        positions = calibration.calibrate(moves, levels, targets, BASE_YEAR, settings)
        daily = hs.run(positions, moves, levels, settings, start=CONFIG.start, end=CONFIG.end)
        scored = bt.summary(daily["realised_pnl_next"], daily["var_total"], settings.quantile)
        annual = hs.annual_summary(daily)

        rows.append(
            {
                "convention": "linear interpolation" if interpolate else "discrete order statistic",
                "mean_var": daily["var_total"].mean(),
                "mean_diversification_pct": annual["diversification_pct"].mean(),
                "exceptions": scored["exceptions"],
                "exception_rate_pct": scored["exception_rate_pct"],
            }
        )

    frame = pd.DataFrame(rows)
    difference = abs(frame["mean_var"].iloc[0] - frame["mean_var"].iloc[1])
    print("percentile convention")
    print(frame.round(3).to_string(index=False))
    print(f"  the two conventions differ by {difference / frame['mean_var'].mean() * 100:.2f}% "
          "of the VaR level\n")
    return frame


if __name__ == "__main__":
    raise SystemExit(main())
