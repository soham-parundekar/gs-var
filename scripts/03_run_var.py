#!/usr/bin/env python3
"""Size the proxy book, run the VaR engine, and compare against the filings.

Produces the two books described in `gsvar.calibration`: one resized every
year to that year's disclosed category split, and one sized once on a base
year and then held still. The first answers the diversification question, the
second feeds the backtest and the regime comparison.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gsvar import book, calibration, config  # noqa: E402
from gsvar import historical_sim as hs  # noqa: E402

CONFIG = config.load()
ROOT = CONFIG.paths.root
PROCESSED = CONFIG.paths.processed

BASE_YEAR = CONFIG.base_year  # calm, and before every year the backtest scores
YEARS = CONFIG.years


def main() -> int:
    moves = pd.read_csv(PROCESSED / "factor_moves.csv", index_col=0, parse_dates=True)
    levels = pd.read_csv(CONFIG.paths.interim / "factor_levels.csv", index_col=0, parse_dates=True)
    disclosed = calibration.first_reported(pd.read_csv(PROCESSED / "gs_var_average_daily.csv"))

    settings = CONFIG.settings()
    print(f"window {settings.window} days, {int((1 - settings.quantile) * 100)}% confidence\n")

    # ---- book sized once, on the base year, then left alone -----------------
    targets = calibration.sleeve_targets(pd.read_csv(PROCESSED / "gs_var_average_daily.csv"), BASE_YEAR)
    fixed_positions = calibration.calibrate(moves, levels, targets, BASE_YEAR, settings)
    book.notionals_table(fixed_positions).to_csv(PROCESSED / "book_fixed_notionals.csv", index=False)

    error = calibration.calibration_error(fixed_positions, moves, levels, targets, BASE_YEAR, settings)
    print(f"sizing check, base year {BASE_YEAR}:")
    print(error.round(4).to_string(), "\n")

    fixed = hs.run(fixed_positions, moves, levels, settings, start=CONFIG.start, end=CONFIG.end)
    fixed.to_csv(PROCESSED / "var_fixed_book_daily.csv")
    fixed_annual = hs.annual_summary(fixed)
    fixed_annual.to_csv(PROCESSED / "var_fixed_book_annual.csv")

    # ---- book resized every year to that year's disclosed split -------------
    recal, sizing = calibration.recalibrated_by_year(
        moves, levels, pd.read_csv(PROCESSED / "gs_var_average_daily.csv"), YEARS, settings
    )
    recal.to_csv(PROCESSED / "var_recalibrated_daily.csv")
    sizing.to_csv(PROCESSED / "calibration_error_by_year.csv", index=False)
    recal_annual = hs.annual_summary(recal)
    recal_annual.to_csv(PROCESSED / "var_recalibrated_annual.csv")

    worst = sizing["error_pct"].abs().max()
    print(f"largest sizing error across all years and sleeves: {worst:.2e}%")
    if worst > 1e-6:
        print("  WARNING: sizing is meant to be exact; a non-zero error means "
              "profit and loss is not proportional to notional somewhere")

    # ---- the comparison -----------------------------------------------------
    comparison = build_comparison(disclosed, fixed_annual, recal_annual)
    comparison.to_csv(PROCESSED / "diversification_comparison.csv")
    print("\ndiversification effect, percent of summed category VaR:")
    print(comparison.round(1).to_string())

    gap = (comparison["model_recalibrated_pct"] - comparison["goldman_pct"]).abs()
    print(f"\nmean absolute gap, recalibrated book vs disclosed: {gap.mean():.1f} pp")
    print(f"worst year: {gap.idxmax()} at {gap.max():.1f} pp")
    return 0


def build_comparison(
    disclosed: pd.DataFrame, fixed: pd.DataFrame, recalibrated: pd.DataFrame
) -> pd.DataFrame:
    categories = list(book.CATEGORIES)
    summed = disclosed[categories].sum(axis=1)

    frame = pd.DataFrame(
        {
            "goldman_pct": -disclosed["diversification_effect"] / summed * 100.0,
            "goldman_total_var": disclosed["total"],
            "goldman_sum_category_var": summed,
            "model_fixed_pct": fixed["diversification_pct"],
            "model_recalibrated_pct": recalibrated["diversification_pct"],
            "model_recalibrated_total_var": recalibrated["var_total"],
        }
    )
    frame["total_var_error_pct"] = (
        (frame["model_recalibrated_total_var"] - frame["goldman_total_var"])
        / frame["goldman_total_var"]
        * 100.0
    )
    return frame.loc[frame["model_recalibrated_pct"].notna()]


if __name__ == "__main__":
    raise SystemExit(main())
