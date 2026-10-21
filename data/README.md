# Data

Three stages, kept apart so a cleaning decision can never be mistaken for the
source. `raw/` holds what was downloaded, byte for byte. `interim/` holds the
aligned panel of levels. `processed/` holds what the analysis reads.

`raw/` is not committed. Ten 10-K filings come to about 95 MB of inline XBRL and
the factor caches are reproducible exactly, so `scripts/01_fetch_disclosures.py`
and `scripts/02_build_factors.py` rebuild the directory on demand. The part of
the filings this project actually reads, the Market Risk Management section of
each one, is preserved verbatim under `../references/sec_filings/`.

`interim/` and `processed/factor_moves.csv` are not committed either, for a
different reason. They carry market data: the aligned panel holds Yahoo Finance
closing prices, whose terms of use do not allow redistribution, mixed with the
Treasury and ECB curves, which would be fine on their own. Running
`scripts/02_build_factors.py` recreates both. Everything else in `processed/` is
either model output or a figure parsed from a public SEC filing, and is
committed so the results can be read without running anything.

## Risk factors

Seventeen, grouped to match Goldman's four disclosed risk categories.

| Factor | Category | Instrument | Unit of the daily move | Source |
|---|---|---|---|---|
| `us_2y`, `us_5y`, `us_10y`, `us_30y` | interest rates | par coupon bond, semiannual | change in par yield, percentage points | US Treasury |
| `eur_2y`, `eur_5y`, `eur_10y` | interest rates | zero-coupon bond, annual | change in spot rate, percentage points | ECB |
| `equity_us` | equity prices | S&P 500 | fractional return | `^GSPC` |
| `equity_europe` | equity prices | EURO STOXX 50 | fractional return | `^STOXX50E` |
| `equity_japan` | equity prices | Nikkei 225 | fractional return | `^N225` |
| `equity_em` | equity prices | MSCI Emerging Markets fund | fractional return | `EEM` |
| `fx_eurusd` | currency rates | EUR/USD | fractional return | `EURUSD=X` |
| `fx_usdjpy` | currency rates | USD/JPY | fractional return | `JPY=X` |
| `fx_gbpusd` | currency rates | GBP/USD | fractional return | `GBPUSD=X` |
| `commodity_gold` | commodity prices | gold fund | fractional return | `GLD` |
| `commodity_oil` | commodity prices | crude oil fund | fractional return | `USO` |
| `commodity_base_metals` | commodity prices | base metals fund | fractional return | `DBB` |

A yield change of 0.25 means 25 basis points, consistently, everywhere. Rate
factors keep their level as well as their change, because repricing a bond
needs the yield it is being shocked away from: the same 25 basis point move is
worth a different amount of money at a 0.5% yield than at a 5% one.

## Choices that shaped the panel

**Equity indices enter in local currency.** A dollar investor holding the Nikkei
carries yen risk as well as Japanese equity risk, but Goldman reports currency
risk in a category of its own. Converting the indices would put currency risk
in the equity sleeve and make the category attribution meaningless.

**Commodities enter through funds, not front-month futures.** On 20 April 2020
the WTI front-month contract settled at minus $37.63. A percentage return is not
defined across a sign change, and the series shows a single day of minus 306%,
which is arithmetic rather than a market move. Funds cannot price below zero.
The cost is roll yield, which drags a fund away from spot over long horizons;
over one day it is second order, but it is a real difference from a spot book.

**Prices are adjusted for splits.** USO ran a one-for-eight reverse share
split, effective after the close on 28 April 2020, with post-split shares
trading from 29 April (REF-022). On unadjusted closes that is a 700% overnight
gain sitting in the middle of the most important stress window in the sample,
and it would enter the scenario set as a tail event. Adjusted closes are used
for every traded instrument.

**The calendar is the intersection, not the union.** Tokyo, London, New York and
the ECB keep different holidays. Taking only days when all of them traded costs
about 9% of trading days and leaves 225 to 233 observations a year
against Goldman's 250 to 253. Forward-filling a closed market instead would
plant runs of exact zeros in the scenario set and understate that factor's risk.
The remaining closes are still not simultaneous across time zones, which
depresses measured cross-market correlation and so overstates diversification.
That one is a limitation rather than a choice, and it is not corrected.

## Checks that run on every build

`scripts/02_build_factors.py` stops rather than warns if any of these fail,
because each produces a plausible number rather than an error downstream.

- Duplicate or unsorted dates in the panel.
- A non-positive price, which breaks a return calculation.
- A run of identical values, which means a stale feed.

The last check needs different tolerances for the two kinds of factor. A traded
price repeating to the cent for five days running is an error. A Treasury yield
repeating is not: the curve is quoted to the basis point, and with the two-year
note near 0.13% through the second half of 2020 it genuinely did not move on
43.1% of days in that half-year. Across the whole 2010-2025 panel the figure is
21.1%, and the longest unbroken run is six days. The limits are five
consecutive days for prices and fifteen for yields, so the real series clears
the yield limit with margin while a repeating traded price still trips.
That discretisation slightly understates true rate variability in the near-zero
period, which is listed in the report's limitations.

## What `processed/` contains

| File | Contents |
|---|---|
| `gs_var_average_daily.csv` | Average daily VaR by category and year, one row per year per filing that reported it |
| `gs_var_period_end.csv` | Period-end VaR by category |
| `gs_var_high_low.csv` | The year's high and low VaR by category, and firmwide from FY2019 |
| `gs_net_revenue_distribution.csv` | Daily net revenue buckets and day counts, FY2019 onward |
| `gs_var_exceptions.csv` | Exception counts at 95% risk-management and 99% regulatory VaR |
| `gs_filing_manifest.csv` | Accession number, filing date and URL for each filing |
| `factor_moves.csv` | The daily move of every factor, in its own unit |
| `factor_move_summary.csv` | Mean, standard deviation and extremes per factor |
| `var_fixed_book_daily.csv` | Daily VaR by category, total, diversification effect and next-day result, fixed book |
| `var_recalibrated_daily.csv` | The same for the annually resized book |
| `var_*_annual.csv` | Annual averages in the shape Goldman reports them |
| `diversification_comparison.csv` | Model against disclosed, by year |
| `calibration_error_by_year.csv` | Sizing error per sleeve per year; should be zero to machine precision |
| `backtest_results.csv` | Kupiec, Christoffersen, conditional coverage and Basel zones for four model variants |
| `backtest_daily_*.csv` | Daily VaR, realised result, exception flag and rolling zone |
| `exceptions_vs_disclosed.csv` | Model exception counts beside Goldman's |
| `robustness_*.csv` | Sleeve signs, lookback windows, percentile convention |
| `regime_table.csv`, `var_year_over_year.csv` | Regime comparison |
| `convexity_comparison.csv` | Rate sleeve priced by full revaluation and by duration |
| `disclosed_var_commentary.csv` | Goldman's own sentence explaining each year's change |

## A note on the disclosures

Each 10-K restates the prior year, so most years appear twice in
`gs_var_average_daily.csv` under different `source_fiscal_year` values, and they
agree. One does not. The FY2023 filing reports 2022 average daily VaR as a total
of 113 where the FY2022 filing reported 114, after Goldman changed what sits
inside VaR in the first quarter of 2023 and conformed the comparative. Both
readings are kept. Analysis uses the figure as first reported, so a methodology
change does not sit inside the time series.
