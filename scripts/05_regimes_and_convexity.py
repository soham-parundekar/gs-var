#!/usr/bin/env python3
"""Regime comparison, and what full revaluation is worth on the rates sleeve.

Two pieces of analysis that both bear on whether the engine is doing what
Goldman says its engine does.

The regime comparison asks whether the model's VaR rises and falls in the
years Goldman's does. Only the fixed book can answer that, because the
recalibrated book is told each year what Goldman's VaR did.

The convexity comparison reprices the rate positions two ways on identical
scenarios: discounting the cashflows again at the shocked yield, which is
what "full valuation" means, and multiplying by modified duration, which is
what a delta-normal model does instead. The gap between them is the whole
practical content of the phrase, and it is near zero in calm years.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gsvar import book, calibration, config, regimes  # noqa: E402
from gsvar import historical_sim as hs  # noqa: E402

CONFIG = config.load()
ROOT = CONFIG.paths.root
PROCESSED = CONFIG.paths.processed
SECTIONS = CONFIG.paths.references / "sec_filings"
BASE_YEAR = CONFIG.base_year


def main() -> int:
    moves = pd.read_csv(PROCESSED / "factor_moves.csv", index_col=0, parse_dates=True)
    levels = pd.read_csv(CONFIG.paths.interim / "factor_levels.csv", index_col=0, parse_dates=True)
    disclosures = pd.read_csv(PROCESSED / "gs_var_average_daily.csv")
    disclosed = calibration.first_reported(disclosures)

    fixed = pd.read_csv(PROCESSED / "var_fixed_book_daily.csv", index_col=0, parse_dates=True)
    fixed_annual = pd.read_csv(PROCESSED / "var_fixed_book_annual.csv", index_col=0)

    # ---- does the model move in the same years Goldman's does? -------------
    agreement = regimes.year_over_year_agreement(
        fixed_annual["var_total"], disclosed.loc[CONFIG.years[0]:CONFIG.years[-1], "total"]
    )
    pd.Series(agreement).to_csv(PROCESSED / "regime_year_over_year.csv", header=["value"])
    print("year-over-year change in average daily VaR, fixed book against the filings")
    for key, value in agreement.items():
        print(f"  {key:26s} {value:.3f}" if isinstance(value, float) else f"  {key:26s} {value}")

    changes = pd.DataFrame(
        {
            "model_var": fixed_annual["var_total"],
            "goldman_var": disclosed.loc[CONFIG.years[0]:CONFIG.years[-1], "total"],
        }
    ).dropna()
    changes["model_change_pct"] = changes["model_var"].pct_change() * 100.0
    changes["goldman_change_pct"] = changes["goldman_var"].pct_change() * 100.0
    changes["same_direction"] = np.sign(changes["model_change_pct"]) == np.sign(
        changes["goldman_change_pct"]
    )
    changes.to_csv(PROCESSED / "var_year_over_year.csv")
    print("\n" + changes.round(1).to_string())

    # ---- regimes ------------------------------------------------------------
    table = regimes.regime_table(fixed, moves)
    table.to_csv(PROCESSED / "regime_table.csv", index=False)
    print("\n\nvolatility regimes, fixed book:")
    print(table.round(2).to_string(index=False))

    # ---- what Goldman itself said each year --------------------------------
    said = []
    for year in CONFIG.years:
        path = SECTIONS / f"GS_10K_FY{year}_market_risk.txt"
        if not path.exists():
            continue
        sentence = regimes.disclosed_commentary(path.read_text(encoding="utf-8"))
        if sentence:
            said.append({"fiscal_year": year, "commentary": sentence})
    pd.DataFrame(said).to_csv(PROCESSED / "disclosed_var_commentary.csv", index=False)
    print(f"\nextracted Goldman's own explanation of the VaR change for "
          f"{len(said)} of {len(CONFIG.years)} years")

    # ---- convexity ----------------------------------------------------------
    convexity = convexity_comparison(moves, levels, disclosures)
    convexity.to_csv(PROCESSED / "convexity_comparison.csv")
    print("\n\ninterest-rate sleeve VaR, full revaluation against the duration approximation:")
    print(convexity.round(3).to_string())
    return 0


def convexity_comparison(
    moves: pd.DataFrame, levels: pd.DataFrame, disclosures: pd.DataFrame
) -> pd.DataFrame:
    """Rates-sleeve VaR priced both ways, on the same book and scenarios."""
    settings = CONFIG.settings()
    targets = calibration.sleeve_targets(disclosures, BASE_YEAR)
    positions = [
        p
        for p in calibration.calibrate(moves, levels, targets, BASE_YEAR, settings)
        if p.category == "interest_rates"
    ]

    dates = moves.index
    first = int(dates.searchsorted(pd.Timestamp(CONFIG.start)))
    rows = []
    for i in range(max(first, settings.window - 1), len(dates) - 1):
        window = moves.iloc[i - settings.window + 1 : i + 1]
        base = levels.loc[dates[i]]

        full = np.zeros(len(window))
        linear = np.zeros(len(window))
        for position in positions:
            full += position.notional * book.scenario_returns(position, window, base)
            linear += position.notional * book.scenario_returns(
                position, window, base, linearised=True
            )

        rows.append(
            {
                "date": dates[i],
                "var_full_revaluation": hs.var_from_scenarios(full, settings),
                "var_duration_only": hs.var_from_scenarios(linear, settings),
            }
        )

    daily = pd.DataFrame(rows).set_index("date")
    daily["difference_pct"] = (
        (daily["var_full_revaluation"] - daily["var_duration_only"])
        / daily["var_duration_only"]
        * 100.0
    )

    yearly = daily.groupby(daily.index.year).mean()
    yearly["largest_daily_gap_pct"] = daily.groupby(daily.index.year)["difference_pct"].apply(
        lambda s: s.abs().max()
    )
    yearly.index.name = "year"
    return yearly


if __name__ == "__main__":
    raise SystemExit(main())
