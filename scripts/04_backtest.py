#!/usr/bin/env python3
"""Backtest the proxy book's VaR against its own realised profit and loss.

Scored on the fixed book only. Its notionals were set from the 2019
disclosures and never touched again, so every day from 2020 onwards is out of
sample with respect to the sizing. The recalibrated book cannot be backtested
honestly, because sizing the 2022 book needs a number Goldman published in
February 2023.

Four models are scored: plain historical simulation and the volatility-
weighted variant, each at 95% and 99%. The 99% runs exist because that is the
confidence level the Basel traffic light was calibrated for, and because
Goldman separately discloses its 99% regulatory exception count, which gives
a second external comparison.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gsvar import backtest as bt  # noqa: E402
from gsvar import calibration, config, volatility  # noqa: E402
from gsvar import historical_sim as hs  # noqa: E402

CONFIG = config.load()
ROOT = CONFIG.paths.root
PROCESSED = CONFIG.paths.processed

BASE_YEAR = CONFIG.base_year
OUT_OF_SAMPLE_START = CONFIG["backtest"]["out_of_sample_start"]


def main() -> int:
    moves = pd.read_csv(PROCESSED / "factor_moves.csv", index_col=0, parse_dates=True)
    levels = pd.read_csv(CONFIG.paths.interim / "factor_levels.csv", index_col=0, parse_dates=True)
    disclosures = pd.read_csv(PROCESSED / "gs_var_average_daily.csv")

    targets = calibration.sleeve_targets(disclosures, BASE_YEAR)
    ewma = volatility.ewma_forecast(moves)

    rows, daily = [], {}
    for coverage in CONFIG["engine"]["alternative_quantiles"]:
        settings = CONFIG.settings(quantile=coverage)
        positions = calibration.calibrate(moves, levels, targets, BASE_YEAR, settings)

        for label, vol in (("historical_simulation", None), ("volatility_weighted", ewma)):
            result = hs.run(
                positions, moves, levels, settings,
                start=CONFIG.start, end=CONFIG.end, volatility=vol,
            )
            daily[(label, coverage)] = result

            for period, frame in (
                (f"{CONFIG.years[0]}-{CONFIG.years[-1]}", result),
                (f"{OUT_OF_SAMPLE_START[:4]}-{CONFIG.years[-1]}", result.loc[OUT_OF_SAMPLE_START:]),
            ):
                record = bt.summary(frame["realised_pnl_next"], frame["var_total"], coverage)
                record.update({"model": label, "confidence_pct": int((1 - coverage) * 100), "period": period})
                rows.append(record)

    results = pd.DataFrame(rows)
    ordered = [
        "model", "confidence_pct", "period", "observations", "exceptions",
        "exception_rate_pct", "kupiec_p_value", "independence_p_value",
        "conditional_coverage_p_value", "basel_worst_zone", "basel_peak_window_exceptions",
        "days_green_pct", "days_yellow_pct", "days_red_pct",
        "basel_yellow_at", "basel_red_at", "largest_exception_multiple",
    ]
    results = results[ordered + [c for c in results.columns if c not in ordered]]
    results.to_csv(PROCESSED / "backtest_results.csv", index=False)

    pd.set_option("display.width", 250)
    print("backtest of the fixed proxy book\n")
    print(results[ordered[:14]].round(4).to_string(index=False))

    for key, frame in daily.items():
        label, coverage = key
        name = f"backtest_daily_{label}_{int((1 - coverage) * 100)}.csv"
        breaches = bt.exceptions(frame["realised_pnl_next"], frame["var_total"])
        out = frame[["var_total", "realised_pnl_next", "pnl_date"]].copy()
        out["exception"] = breaches
        out = out.join(bt.rolling_zone(breaches, coverage))
        out.to_csv(PROCESSED / name)

    compare_with_disclosures(daily, PROCESSED)
    return 0


def compare_with_disclosures(daily: dict, out_dir: Path) -> None:
    """Model exception counts per year, beside Goldman's disclosed counts.

    The two are not the same measurement and the table says so. Goldman counts
    days on which its *net revenues* fell short of the prior day's VaR, and
    those revenues include intraday market-making income, which is positive
    far more often than not. The proxy book has no client flow and no bid-offer
    spread, so its profit and loss is a clean mark-to-market on a static
    position. A dealer's revenue cushion is exactly the thing that should make
    Goldman's exception count lower, and the comparison is here to size that
    gap rather than to pretend it away.
    """
    disclosed = pd.read_csv(out_dir / "gs_var_exceptions.csv")
    disclosed = disclosed.drop_duplicates(subset=["year", "confidence_pct"])

    frames = []
    for (label, coverage), frame in daily.items():
        breaches = bt.exceptions(frame["realised_pnl_next"], frame["var_total"])
        yearly = breaches.groupby(breaches.index.year).agg(["sum", "size"])
        yearly.columns = ["model_exceptions", "model_days"]
        yearly["model"] = label
        yearly["confidence_pct"] = int((1 - coverage) * 100)
        frames.append(yearly.reset_index(names="year"))

    model = pd.concat(frames)
    merged = model.merge(
        disclosed.rename(columns={"exceptions": "goldman_exceptions"})[
            ["year", "confidence_pct", "goldman_exceptions"]
        ],
        on=["year", "confidence_pct"],
        how="left",
    )
    merged["model_rate_pct"] = merged["model_exceptions"] / merged["model_days"] * 100.0
    merged.to_csv(out_dir / "exceptions_vs_disclosed.csv", index=False)

    print("\n\nexception counts by year, plain historical simulation at 95%:")
    view = merged[(merged.model == "historical_simulation") & (merged.confidence_pct == 95)]
    print(view[["year", "model_days", "model_exceptions", "model_rate_pct", "goldman_exceptions"]]
          .round(2).to_string(index=False))

    in_sample = disclosed.year.between(CONFIG.years[0], CONFIG.years[-1])
    disclosed95 = disclosed[(disclosed.confidence_pct == 95) & in_sample]
    total = int(disclosed95["exceptions"].sum())
    print(f"\nGoldman, {CONFIG.years[0]}-{CONFIG.years[-1]}: {total} exceptions at 95% across roughly "
          f"{251 * len(disclosed95)} trading days ({total / (251 * len(disclosed95)) * 100:.2f}% of days)")


if __name__ == "__main__":
    raise SystemExit(main())
