"""Generate the manuscript's figures from the frozen research outputs.

The research repository has its own figures, styled for a report: they carry
editorial titles and in-plot legends because they are read on their own. A
figure in a paper is read with its caption, so the caption carries the claim
and the figure carries only the data. These are therefore rebuilt here rather
than copied, from the same CSVs the tables come from.

Serif type and a restrained palette, to sit with newtx rather than against it.

Usage:
    python build/make_figures.py            # both figures
    python build/make_figures.py figure1    # one
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PAPER_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(
    os.environ.get("GSVAR_DATA_ROOT", PAPER_ROOT.parent / "data" / "processed")
)
FIGURE_DIR = PAPER_ROOT / "figures"

#: Letterpaper with 1in margins leaves 6.5in of text. Drawing at exactly that
#: width means \includegraphics[width=\linewidth] does not rescale, so the
#: type inside a figure matches the type around it.
TEXT_WIDTH_IN = 6.5

DISCLOSED = "#111111"
RECALIBRATED = "#1f6fb4"
FIXED = "#c2561a"
GRID = "#d9d9d9"


def _style() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times New Roman", "Nimbus Roman"],
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.edgecolor": "#444444",
        "axes.linewidth": 0.7,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "figure.dpi": 400,
        # Not "tight": that crops to drawn content and discards the width
        # set above, which is the whole point of drawing at text width.
        "savefig.bbox": None,
        "figure.constrained_layout.use": True,
        "figure.constrained_layout.h_pad": 0.02,
        "figure.constrained_layout.w_pad": 0.02,
    })


def _read(name: str) -> pd.DataFrame:
    path = DATA_ROOT / name
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Point GSVAR_DATA_ROOT at the research "
            f"repository's data/processed directory."
        )
    return pd.read_csv(path, index_col=0)


def figure1() -> Path:
    """The disclosed series against both proxy books, by year."""
    frame = _read("diversification_comparison.csv")
    years = frame.index.to_numpy()

    fig, ax = plt.subplots(figsize=(TEXT_WIDTH_IN, 3.1))
    for column, colour, label in [
        ("goldman_pct", DISCLOSED, "Goldman, as disclosed"),
        ("model_recalibrated_pct", RECALIBRATED, "proxy, resized each year"),
        ("model_fixed_pct", FIXED, "proxy, fixed since 2019"),
    ]:
        ax.plot(years, frame[column], color=colour, linewidth=1.5,
                marker="o", markersize=3.2, zorder=3)
        # Labelled at the line's own end rather than in a legend box, so the
        # reader's eye does not have to travel.
        ax.annotate(label, xy=(years[-1], frame[column].iloc[-1]),
                    xytext=(5, 0), textcoords="offset points",
                    color=colour, fontsize=8, va="center")

    ax.set_xlim(years.min() - 0.3, years.max() + 4.6)
    ax.set_ylim(28, 57)
    ax.set_xticks(years[::2])
    ax.set_ylabel("Diversification effect, % of summed category VaR")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}")
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    path = FIGURE_DIR / "diversification_over_time.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def figure2() -> Path:
    """Level against steadiness, one point per sleeve-sign configuration."""
    variants = pd.read_csv(DATA_ROOT / "robustness_sign_variants.csv")
    disclosed = _read("diversification_comparison.csv").goldman_pct
    level, steadiness = disclosed.mean(), disclosed.std()

    fig, ax = plt.subplots(figsize=(TEXT_WIDTH_IN, 3.6))

    # The claim is that the corner Goldman occupies is empty, so the lines
    # that define that corner are drawn rather than left to be inferred.
    ax.axhline(steadiness, color=DISCLOSED, linewidth=0.6, linestyle=(0, (4, 3)), zorder=1)
    ax.axvline(level, color=DISCLOSED, linewidth=0.6, linestyle=(0, (4, 3)), zorder=1)

    ax.scatter(variants.mean_diversification_pct, variants.std_across_years,
               s=22, color=RECALIBRATED, zorder=3, linewidths=0)

    # Sixteen labels in a small space collide if each is simply placed above
    # its point. Greedy de-collision: work left to right, keep the label above
    # unless a label already sits near that spot, in which case put it below.
    placed: list[tuple[float, float, int]] = []
    span_x = variants.mean_diversification_pct.max() - variants.mean_diversification_pct.min()
    span_y = variants.std_across_years.max() - variants.std_across_years.min()
    for _, row in variants.sort_values("mean_diversification_pct").iterrows():
        x, y = row.mean_diversification_pct, row.std_across_years
        direction = 1
        for px, py, pdir in placed:
            near = (abs(px - x) < 0.045 * span_x
                    and abs(py - y) < 0.075 * span_y
                    and pdir == direction)
            if near:
                direction = -1
                break
        offset = 6 if direction == 1 else -11
        ax.annotate(row.signs, xy=(x, y), xytext=(0, offset),
                    textcoords="offset points", fontsize=6.4, ha="center",
                    color="#555555", zorder=3)
        placed.append((x, y, direction))

    ax.scatter([level], [steadiness], marker="*", s=180, color=DISCLOSED, zorder=4)
    # The guide line runs under this label, so it gets a plain background.
    ax.annotate("Goldman", xy=(level, steadiness), xytext=(11, -1),
                textcoords="offset points", fontsize=8.5, va="center",
                fontweight="bold", color=DISCLOSED, zorder=5,
                bbox=dict(facecolor="white", edgecolor="none", pad=1.2))

    ax.set_xlabel("Average diversification effect, % of summed category VaR")
    ax.set_ylabel("Year-to-year standard deviation (pp)")
    ax.set_ylim(0, variants.std_across_years.max() + 1.4)
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    path = FIGURE_DIR / "stability_frontier.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def figure3() -> Path:
    """Steadiness and coverage against the age-decay rate, at the disclosed window."""
    grid = pd.read_csv(DATA_ROOT / "robustness_decay_grid.csv")
    disclosed = _read("diversification_comparison.csv").goldman_pct.std()

    # Half-life is the readable axis, but equal weighting has none, so the
    # grid is plotted against decay with half-lives annotated on the ticks.
    grid = grid.sort_values("age_decay")
    x = grid.age_decay.to_numpy()

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(TEXT_WIDTH_IN, 4.1), sharex=True,
        gridspec_kw={"height_ratios": [1.45, 1.0]},
    )

    top.axhline(disclosed, color=DISCLOSED, linewidth=0.9,
                linestyle=(0, (4, 3)), zorder=2)
    top.annotate(f"Goldman, {disclosed:.2f}", xy=(x.min(), disclosed),
                 xytext=(2, 4), textcoords="offset points",
                 fontsize=8, color=DISCLOSED)
    top.plot(x, grid.std_across_years, color=RECALIBRATED, linewidth=1.5,
             marker="o", markersize=3.2, zorder=3)
    top.set_ylabel("Year-to-year s.d. (pp)")
    top.set_ylim(0, grid.std_across_years.max() + 1.2)

    bottom.axhline(5.0, color="#777777", linewidth=0.9, linestyle=(0, (4, 3)), zorder=2)
    bottom.annotate("nominal 5%", xy=(x.min(), 5.0), xytext=(2, 4),
                    textcoords="offset points", fontsize=8, color="#555555")
    bottom.plot(x, grid.exception_rate_pct, color=FIXED, linewidth=1.5,
                marker="o", markersize=3.2, zorder=3)
    bottom.set_ylabel("Exception rate (%)")
    bottom.set_xlabel("Age-decay rate $\\lambda$  (1.0 is equal weighting; "
                      "lower is faster decay)")

    for ax in (top, bottom):
        ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    top.invert_xaxis()

    path = FIGURE_DIR / "decay_grid.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


FIGURES = {"figure1": figure1, "figure2": figure2, "figure3": figure3}


def main(argv: list[str]) -> None:
    _style()
    FIGURE_DIR.mkdir(exist_ok=True)
    for key in argv[1:] or list(FIGURES):
        if key not in FIGURES:
            raise SystemExit(f"unknown figure {key!r}; have {sorted(FIGURES)}")
        print(f"wrote {FIGURES[key]().relative_to(PAPER_ROOT)}")


if __name__ == "__main__":
    main(sys.argv)
