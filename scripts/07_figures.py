#!/usr/bin/env python3
"""Figures for the report.

Four of them, one per finding worth looking at rather than reading. The
convexity result is a single number and stays in a table, where a number
belongs.

Colour carries series identity in at most two slots per chart, every series is
labelled on the plot as well as in the legend, and the Basel zone boundaries
are drawn as labelled threshold lines rather than coloured bands, because the
green and red status hues are close to indistinguishable under deuteranopia
and nothing here should depend on telling them apart.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gsvar import book, calibration, config  # noqa: E402

CONFIG = config.load()
ROOT = CONFIG.paths.root
PROCESSED = CONFIG.paths.processed
FIGURES = CONFIG.paths.figures

INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#dcdbd6"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
WARNING = "#fab219"
CRITICAL = "#d03b3b"


def style(ax, title: str, ylabel: str, subtitle: str | None = None) -> None:
    # The subtitle sits just above the axes, so the title has to clear both it
    # and its own descenders. A pad of 22 points covers a 9.5-point subtitle
    # with room to spare; the default of 6 puts them on top of each other.
    ax.set_title(title, loc="left", fontsize=12.5, color=INK, pad=22 if subtitle else 8)
    if subtitle:
        ax.text(
            0, 1.012, subtitle, transform=ax.transAxes, fontsize=9.5, color=MUTED, va="bottom"
        )
    ax.set_ylabel(ylabel, fontsize=10, color=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9.5)


def save(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / name, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote reports/figures/{name}")


def diversification_over_time() -> None:
    comparison = pd.read_csv(PROCESSED / "diversification_comparison.csv", index_col=0)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(comparison.index, comparison["goldman_pct"], color=INK, linewidth=2.4, marker="o",
            markersize=5, label="Goldman, as disclosed", zorder=3)
    ax.plot(comparison.index, comparison["model_recalibrated_pct"], color=BLUE, linewidth=2,
            marker="o", markersize=4.5, label="proxy book, resized each year")
    ax.plot(comparison.index, comparison["model_fixed_pct"], color=ORANGE, linewidth=2,
            marker="o", markersize=4.5, label="proxy book, fixed since 2019")

    last = comparison.index.max()
    for series, colour, text in (
        ("goldman_pct", INK, "Goldman"),
        ("model_recalibrated_pct", BLUE, "resized yearly"),
        ("model_fixed_pct", ORANGE, "fixed book"),
    ):
        ax.annotate(text, (last, comparison.loc[last, series]), xytext=(8, 0),
                    textcoords="offset points", color=colour, fontsize=9.5, va="center")

    style(ax, "Goldman's diversification benefit barely moves; the proxy book's does",
          "diversification effect, % of summed category VaR",
          "share of the four category VaRs that cancels out once they are simulated together")
    ax.set_xlim(comparison.index.min() - 0.3, last + 2.2)
    ax.set_ylim(0, 60)
    ax.legend(frameon=False, fontsize=9.5, loc="lower left", ncol=3)
    save(fig, "diversification_over_time.png")


def stability_frontier() -> None:
    """The finding that a single time series cannot show.

    Each point is one of the sixteen ways the four sleeves can be signed. The
    horizontal axis is the average diversification benefit over 2016-2025 and
    the vertical axis is how much it wandered year to year. Goldman sits in
    the bottom middle: a typical level held very steady. The model's points
    avoid that corner entirely.
    """
    variants = pd.read_csv(PROCESSED / "robustness_sign_variants.csv")
    disclosed = calibration.first_reported(pd.read_csv(PROCESSED / "gs_var_average_daily.csv"))
    goldman = (
        -disclosed["diversification_effect"] / disclosed[list(book.CATEGORIES)].sum(axis=1) * 100.0
    ).loc[2016:2025]

    fig, ax = plt.subplots(figsize=(9, 5.6))
    ax.scatter(variants["mean_diversification_pct"], variants["std_across_years"],
               s=58, color=BLUE, edgecolor="white", linewidth=1.2, zorder=3,
               label="proxy book, one point per sleeve-sign combination")
    # Several combinations land almost on top of each other, so labels
    # alternate above and below once neighbours get close enough to collide.
    # Several combinations land almost on top of one another. Labels in a
    # crowded run step through three vertical offsets so no two share a line.
    offsets = [(0, 10), (0, -16), (0, 22)]
    ordered = variants.sort_values("mean_diversification_pct").reset_index(drop=True)
    previous_x, step = None, 0
    for _, row in ordered.iterrows():
        x, y = row["mean_diversification_pct"], row["std_across_years"]
        crowded = previous_x is not None and abs(x - previous_x) < 1.4
        step = (step + 1) % len(offsets) if crowded else 0
        ax.annotate(row["signs"], (x, y), xytext=offsets[step],
                    textcoords="offset points", fontsize=7.4, color=MUTED, ha="center")
        previous_x = x

    ax.scatter([goldman.mean()], [goldman.std()], s=190, marker="*", color=INK,
               zorder=4, label="Goldman, as disclosed")
    ax.annotate("Goldman", (goldman.mean(), goldman.std()), xytext=(10, -4),
                textcoords="offset points", fontsize=10.5, color=INK, fontweight="bold")

    style(ax, "No sleeve configuration reaches both Goldman's level and its steadiness",
          "year-to-year standard deviation (pp)",
          "signs in order: interest rates, equity, currency, commodity")
    ax.set_xlabel("average diversification effect, % of summed category VaR",
                  fontsize=10, color=MUTED)
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    ax.set_ylim(0, 12.5)
    save(fig, "stability_frontier.png")


def var_against_outcomes() -> None:
    daily = pd.read_csv(PROCESSED / "backtest_daily_historical_simulation_95.csv",
                        index_col=0, parse_dates=True)
    breaches = daily[daily["exception"] == 1]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.fill_between(daily.index, -daily["var_total"], 0, color=BLUE, alpha=0.13, linewidth=0,
                    label="95% VaR, one day ahead")
    ax.plot(daily.index, -daily["var_total"], color=BLUE, linewidth=1.5)
    ax.plot(daily.index, daily["realised_pnl_next"], color=MUTED, linewidth=0.55,
            label="realised profit and loss", zorder=2)
    ax.scatter(breaches.index, breaches["realised_pnl_next"], s=11, color=CRITICAL,
               zorder=4, label=f"exception ({len(breaches)} days)")

    style(ax, "The 2022 rate shock ran straight through a two-year lookback window",
          "$ millions, proxy book",
          "losses below the shaded VaR line are exceptions; the book is sized once on 2019 and never resized")
    ax.axhline(0, color=GRID, linewidth=0.8)
    ax.legend(frameon=False, fontsize=9.5, loc="lower left", ncol=3)
    save(fig, "var_against_outcomes.png")


def rolling_exceptions() -> None:
    plain = pd.read_csv(PROCESSED / "backtest_daily_historical_simulation_99.csv",
                        index_col=0, parse_dates=True)
    weighted = pd.read_csv(PROCESSED / "backtest_daily_volatility_weighted_99.csv",
                           index_col=0, parse_dates=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(plain.index, plain["exceptions_in_window"], color=BLUE, linewidth=1.8,
            label="historical simulation")
    ax.plot(weighted.index, weighted["exceptions_in_window"], color=ORANGE, linewidth=1.8,
            label="volatility weighted")

    # The yellow and red status hues are near-indistinguishable under
    # deuteranopia, so each threshold is named in text on the plot. The label
    # is the encoding here; the colour only reinforces it.
    for level, colour, text in ((5, WARNING, "yellow zone begins (5)"),
                                (10, CRITICAL, "red zone begins (10)")):
        ax.axhline(level, color=colour, linewidth=1.4, linestyle=(0, (6, 4)))
        ax.annotate(text, xy=(0.995, level), xycoords=("axes fraction", "data"),
                    xytext=(0, 5), textcoords="offset points", fontsize=9.5,
                    color=MUTED, ha="right", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                              edgecolor="none", alpha=0.85))

    style(ax, "Rescaling scenarios to current volatility keeps the model out of the red zone",
          "exceptions in the trailing 250 days",
          "99% one-day VaR, Basel traffic-light thresholds for a 250-day window")
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    save(fig, "rolling_exceptions.png")


def main() -> int:
    diversification_over_time()
    stability_frontier()
    var_against_outcomes()
    rolling_exceptions()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
