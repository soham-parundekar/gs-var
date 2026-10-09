"""Does the model's VaR move the way Goldman's does?

The dollar level of the proxy book is a normalisation and says nothing. What
can be compared is the shape: when Goldman's average daily VaR rose by half
between 2021 and 2022, did a VaR engine fed only public data do something
similar, and for the same reason?

Two comparisons are made. The first is directional, on year-over-year changes
in average daily VaR, which asks whether the model and the disclosures agree
on which years got riskier. The second splits the sample into volatility
regimes and reports the level of VaR, the volatility of the underlying
factors, and the realised profit and loss in each, which asks whether the
model moved for the right reason rather than by coincidence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

#: Sub-periods with visibly different volatility, chosen from the market
#: record rather than from the results. The 2020 window runs from the week
#: equity markets turned to the end of the first wave; the 2022 window spans
#: the Federal Reserve's hiking cycle from the first rise to the last of that
#: calendar year.
REGIMES = {
    "calm 2017-2019": ("2017-01-01", "2019-12-31"),
    "covid shock 2020": ("2020-02-20", "2020-06-30"),
    "recovery 2021": ("2021-01-01", "2021-12-31"),
    "rate shock 2022": ("2022-03-01", "2022-12-31"),
    "after the shock 2024-2025": ("2024-01-01", "2025-12-31"),
}


def year_over_year_agreement(model_annual: pd.Series, disclosed_annual: pd.Series) -> dict:
    """How closely the model's year-on-year VaR changes track the disclosures.

    Both series are reduced to proportional changes, which removes the level
    difference between a proxy book and a real one and leaves the question
    that can actually be answered. Correlation is reported both ways: Pearson
    on the size of the moves, and Spearman on their ranking, because ten
    observations is few enough that one outlier can carry a Pearson figure on
    its own.
    """
    common = model_annual.index.intersection(disclosed_annual.index)
    model = model_annual.loc[common].pct_change().dropna()
    disclosed = disclosed_annual.loc[common].pct_change().dropna()

    shared = model.index.intersection(disclosed.index)
    model, disclosed = model.loc[shared], disclosed.loc[shared]
    if len(shared) < 3:
        raise ValueError("need at least three year-over-year changes to compare")

    pearson = stats.pearsonr(model, disclosed)
    spearman = stats.spearmanr(model, disclosed)
    agreeing = int((np.sign(model) == np.sign(disclosed)).sum())

    return {
        "years_compared": int(len(shared)),
        "same_direction": agreeing,
        "same_direction_pct": agreeing / len(shared) * 100.0,
        "pearson_r": float(pearson.statistic),
        "pearson_p": float(pearson.pvalue),
        "spearman_rho": float(spearman.statistic),
        "spearman_p": float(spearman.pvalue),
        "mean_absolute_gap_pct": float((model - disclosed).abs().mean() * 100.0),
    }


def regime_table(
    daily: pd.DataFrame, moves: pd.DataFrame, regimes: dict | None = None
) -> pd.DataFrame:
    """VaR, factor volatility and realised results, period by period."""
    rows = []
    for name, (start, end) in (regimes or REGIMES).items():
        window = daily.loc[start:end]
        if window.empty:
            continue
        factor_window = moves.loc[start:end]

        rows.append(
            {
                "regime": name,
                "start": start,
                "end": end,
                "days": len(window),
                "mean_var": window["var_total"].mean(),
                "peak_var": window["var_total"].max(),
                "mean_diversification_pct": (
                    -window["diversification_effect"] / window["sum_category_var"] * 100.0
                ).mean(),
                "realised_pnl_std": window["realised_pnl_next"].std(),
                "worst_day": window["realised_pnl_next"].min(),
                "exceptions_pct": float(
                    (window["realised_pnl_next"] < -window["var_total"]).mean() * 100.0
                ),
                "equity_vol_annualised_pct": factor_window["equity_us"].std() * np.sqrt(252) * 100.0,
                "us_10y_vol_bp_per_day": factor_window["us_10y"].std() * 100.0,
            }
        )
    return pd.DataFrame(rows)


def disclosed_commentary(section_text: str) -> str | None:
    """Goldman's own sentence explaining that year's change in average VaR.

    Useful as a check that the model and the filing attribute a move to the
    same cause. Returns None when the filing phrases it in a way this does
    not recognise, which is preferable to returning a nearby sentence that
    happens to contain the word volatility.
    """
    import re

    pattern = re.compile(
        r"(?:Our\s+)?average daily VaR\s+(increased|decreased|was essentially unchanged)"
        r"[^.]{0,400}\.",
        re.IGNORECASE,
    )
    match = pattern.search(section_text)
    return match.group(0).strip() if match else None
