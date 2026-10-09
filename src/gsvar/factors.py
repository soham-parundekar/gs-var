"""Risk-factor data for the proxy book, from free and official sources.

Goldman splits market risk four ways, so the factor set does the same. Each
sleeve is built from instruments that are liquid, have an unbroken daily
history back to 2013, and are priced in a way that keeps the four categories
from overlapping:

    interest rates    US Treasury par yield curve (2y, 5y, 10y, 30y) and the
                      euro area AAA government spot curve (2y, 5y, 10y)
    equity prices     S&P 500, EURO STOXX 50, Nikkei 225, MSCI EM
    currency rates    EUR/USD, USD/JPY, GBP/USD
    commodity prices  gold, crude oil and base metals, via exchange-traded funds

Two choices in that list need explaining.

Equity indices enter in local currency. A dollar investor holding the Nikkei
carries both Japanese equity risk and yen risk, but Goldman reports those in
separate categories, so mixing them here would double-count currency risk in
the equity sleeve and make the category attribution meaningless.

Commodities enter through funds rather than front-month futures. On
20 April 2020 the WTI front-month contract settled at minus $37.63, and a
percentage return is not defined across a sign change: the series shows a
single -306% day, which is arithmetic rather than economics. Funds cannot
price below zero. The cost of that choice is roll yield, which drags the fund
away from spot over long horizons. For one-day VaR the drag is second order,
but it is a real difference from a spot commodity book and is listed in the
project's limitations.
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import pandas as pd

EQUITY_INDICES = {
    "^GSPC": "equity_us",
    "^STOXX50E": "equity_europe",
    "^N225": "equity_japan",
    "EEM": "equity_em",
}

FX_PAIRS = {
    "EURUSD=X": "fx_eurusd",
    "JPY=X": "fx_usdjpy",
    "GBPUSD=X": "fx_gbpusd",
}

COMMODITY_FUNDS = {
    "GLD": "commodity_gold",
    "USO": "commodity_oil",
    "DBB": "commodity_base_metals",
}

# Treasury publishes the full par curve; these are the points the book trades.
US_TENORS = {"2 Yr": 2.0, "5 Yr": 5.0, "10 Yr": 10.0, "30 Yr": 30.0}

# The ECB's AAA-rated euro area government curve, as spot (zero-coupon) rates.
EURO_TENORS = {"SR_2Y": 2.0, "SR_5Y": 5.0, "SR_10Y": 10.0}

_TREASURY_CSV = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)
_ECB_CSV = (
    "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{series}"
    "?format=csvdata&startPeriod={start}&endPeriod={end}"
)


def market_closes(tickers: list[str], start: str, end: str, cache: Path) -> pd.DataFrame:
    """Daily closes for exchange-traded instruments, adjusted for splits.

    Adjusted closes matter here: USO ran a one-for-eight reverse split in
    April 2020, and the unadjusted series would show a 700% overnight gain
    sitting right in the middle of the most important stress window in the
    sample.
    """
    cached = cache / "market_closes.csv"
    if cached.exists():
        frame = pd.read_csv(cached, index_col=0, parse_dates=True)
        if set(tickers).issubset(frame.columns):
            return frame.loc[start:end, tickers]

    import yfinance as yf

    downloaded = yf.download(
        tickers, start=start, end=end, progress=False, auto_adjust=True, threads=False
    )
    closes = downloaded["Close"].sort_index()
    cache.mkdir(parents=True, exist_ok=True)
    closes.to_csv(cached)
    return closes[tickers]


def treasury_par_curve(start_year: int, end_year: int, cache: Path) -> pd.DataFrame:
    """US Treasury par yields in percent, one column per tenor, daily.

    Treasury serves one calendar year per request, so the years are fetched
    separately and stacked.
    """
    cached = cache / "treasury_par_curve.csv"
    if cached.exists():
        return pd.read_csv(cached, index_col=0, parse_dates=True)

    years = []
    for year in range(start_year, end_year + 1):
        raw = _get(_TREASURY_CSV.format(year=year))
        frame = pd.read_csv(io.BytesIO(raw))
        frame["Date"] = pd.to_datetime(frame["Date"], format="%m/%d/%Y")
        years.append(frame.set_index("Date")[list(US_TENORS)])

    curve = pd.concat(years).sort_index()
    curve.columns = [f"us_{int(US_TENORS[c])}y" for c in curve.columns]
    cache.mkdir(parents=True, exist_ok=True)
    curve.to_csv(cached)
    return curve


def euro_area_curve(start: str, end: str, cache: Path) -> pd.DataFrame:
    """Euro area AAA government spot rates in percent, one column per tenor.

    These are already zero-coupon rates, unlike the Treasury series, which is
    quoted on a par basis. The distinction matters when the bonds are priced.
    """
    cached = cache / "euro_area_curve.csv"
    if cached.exists():
        return pd.read_csv(cached, index_col=0, parse_dates=True)

    columns = {}
    for series, tenor in EURO_TENORS.items():
        raw = _get(_ECB_CSV.format(series=series, start=start, end=end))
        frame = pd.read_csv(io.BytesIO(raw))
        dated = frame.set_index(pd.to_datetime(frame["TIME_PERIOD"]))["OBS_VALUE"]
        columns[f"eur_{int(tenor)}y"] = dated

    curve = pd.DataFrame(columns).sort_index()
    curve.index.name = "Date"
    cache.mkdir(parents=True, exist_ok=True)
    curve.to_csv(cached)
    return curve


def _get(url: str, timeout: int = 90) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "gs-var research project"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def align_to_common_calendar(
    prices: pd.DataFrame, curves: pd.DataFrame, min_coverage: float = 0.98
) -> pd.DataFrame:
    """One business-day index on which every factor has an observation.

    Tokyo, London, New York and the ECB all keep different holiday calendars.
    Forward-filling a closed market would plant a run of zero returns in the
    middle of the scenario set and quietly understate that factor's risk, so
    the panel is restricted to days on which everything actually traded.

    The cost is about 9% of trading days, which is acceptable; what
    would not be acceptable is a factor silently dropping out of the window.
    Any column covering less than `min_coverage` of the intersection is
    reported rather than dropped, because losing a factor changes the book.
    """
    panel = prices.join(curves, how="inner")
    complete = panel.dropna(how="any")

    coverage = complete.notna().sum() / max(len(complete), 1)
    thin = coverage[coverage < min_coverage]
    if not thin.empty:
        raise ValueError(f"factors with incomplete coverage after alignment: {dict(thin)}")

    return complete
