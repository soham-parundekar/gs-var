# Sources

Every source that materially shaped the research question, the method, the data
or a conclusion. `source_register.csv` holds the same list in machine-readable
form, with the project component that depends on each one. Nothing is listed
here that the project does not actually use.

All sources were accessed on 9 October 2026.

The manuscript under `paper/` draws on a wider literature than the code does,
and registers it separately in `paper/references/source_register.csv`, which
records for each work whether it was read in full or verified by metadata
alone. Preserved documents from either register are stored once, here, so
`papers/` and `official_reports/` may hold a file that only the manuscript's
register lists.

## Primary disclosures

The ten annual reports are the subject of the project rather than a background
reference. Each supplies the average daily, period-end and high/low VaR by risk
category, the diversification effect, the exception count, and (from FY2019) the
daily net revenue distribution.

| ID | Fiscal year | Filed | Accession |
|---|---|---|---|
| REF-001 | 2016 | 2017-02-27 | 0001193125-17-056804 |
| REF-002 | 2017 | 2018-02-26 | 0001193125-18-056383 |
| REF-003 | 2018 | 2019-02-26 | 0001193125-19-050198 |
| REF-004 | 2019 | 2020-02-21 | 0001193125-20-043853 |
| REF-005 | 2020 | 2021-02-22 | 0001193125-21-049380 |
| REF-006 | 2021 | 2022-02-25 | 0001193125-22-052682 |
| REF-007 | 2022 | 2023-02-24 | 0000886982-23-000003 |
| REF-008 | 2023 | 2024-02-23 | 0000886982-24-000006 |
| REF-009 | 2024 | 2025-02-27 | 0000886982-25-000005 |
| REF-010 | 2025 | 2026-02-25 | 0000886982-26-000091 |

The Goldman Sachs Group, Inc., Annual Report on Form 10-K, CIK 0000886982.
Retrieved from EDGAR at
`https://www.sec.gov/Archives/edgar/data/886982/<accession>/<document>`; the
exact URL and primary document name for each year are in
`source_register.csv` and in `data/processed/gs_filing_manifest.csv`.

SEC filings are public and freely redistributable. The Market Risk Management
section of each is preserved verbatim under `sec_filings/`, which is the text
every figure in this project was read from. The complete filings run to about
95 MB of inline XBRL and are not committed; `scripts/01_fetch_disclosures.py`
downloads them again from the accession numbers above.

One substantive note on the disclosures themselves. The FY2023 filing restates
2022 average daily VaR (96/35/32/47, total 113) against the FY2022 filing's
original (97/33/32/47, total 114). The filing explains that during the first
quarter of 2023 Goldman added the currency exposure on certain debt and equity
positions to VaR and removed certain others, and conformed the prior period.
Figures used in this project are as first reported.

## Data sources

**REF-011. U.S. Department of the Treasury, Daily Treasury Par Yield Curve
Rates.** Par yields at 2, 5, 10 and 30 years, 2010 to 2025. US government work,
public domain.
<https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve>

**REF-012. European Central Bank, euro area yield curves, AAA-rated central
government bonds, spot rates.** Series `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y`,
`SR_5Y` and `SR_10Y`, 2010 to 2025. Reusable with attribution.
<https://data.ecb.europa.eu/data/datasets/YC>

**REF-013. Yahoo Finance, daily closing prices**, retrieved with the `yfinance`
library: `^GSPC`, `^STOXX50E`, `^N225`, `EEM`, `EURUSD=X`, `JPY=X`, `GBPUSD=X`,
`GLD`, `USO`, `DBB`. The terms of use do not permit redistribution, so no copy
is committed; `scripts/02_build_factors.py` retrieves it again.

None of the three datasets is stored in the repository. The Treasury and ECB
series are public domain or openly licensed and could be, but Yahoo's terms do
not allow redistribution and the aligned panel mixes all three, so
`data/raw/factors/`, `data/interim/` and `data/processed/factor_moves.csv` are
all excluded from version control. `scripts/02_build_factors.py` rebuilds them.

## Method

**REF-014. Kupiec, Paul H. (1995).** "Techniques for verifying the accuracy of
risk measurement models." *Journal of Derivatives*, Vol. 3, pp. 73-84. Working
paper version: Finance and Economics Discussion Series 95-24, Board of Governors
of the Federal Reserve System. Supplies the proportion-of-failures likelihood
ratio test. The journal version is copyrighted and not redistributed here; the
Federal Reserve working paper is freely available at
<https://fedinprint.org/item/fedgfe/34596/original>

**REF-015. Christoffersen, Peter F. (1998).** "Evaluating Interval Forecasts."
*International Economic Review*, Vol. 39, No. 4, pp. 841-862. Supplies the
Markov independence test and the joint conditional coverage test. Copyrighted;
available through the publisher or a library.
<https://ideas.repec.org/a/ier/iecrev/v39y1998i4p841-62.html>

**REF-016. Hull, John and White, Alan (1998).** "Incorporating volatility
updating into the historical simulation method for value-at-risk." *Journal of
Risk*, Vol. 1, No. 1, pp. 5-19. DOI
[10.21314/JOR.1998.001](https://doi.org/10.21314/JOR.1998.001). The
volatility-weighted variant implemented in `volatility.py`. Copyrighted;
available from the publisher at the DOI.

**REF-021. U.S. Commodity Futures Trading Commission (2020).** *Interim Staff
Report: Trading in NYMEX WTI Crude Oil Futures Contract Leading up to, on, and
around April 20, 2020*, published 23 November 2020. The source for the two
prices behind the decision to run commodity exposure through exchange-traded
funds rather than front-month futures: the May 2020 contract settled at
-$37.63 per barrel on 20 April 2020, against a close of $18.27 on 17 April. A
percentage return is not defined across that sign change, and the implied
single-day move of -306% is arithmetic rather than a market move a risk model
should be asked to price.
<https://www.cftc.gov/media/5296/InterimStaffReportNYMEX_WTICrudeOil/download>

Work of the US government, public domain, and preserved in full at
`official_reports/2020_CFTC_InterimStaffReport_NYMEX_WTI_April2020.pdf`.

**REF-022. United States Oil Fund, LP (2020).** Current Report on Form 8-K,
exhibit 99.1, filed April 2020, CIK 0001327068. Announces the one-for-eight
reverse share split effective after the close on 28 April 2020, with post-split
shares trading from 29 April. The reason split-adjusted closes are used: on
unadjusted closes the split reads as a 700% overnight gain in the middle of the
2020 stress window.
<https://www.sec.gov/Archives/edgar/data/1327068/000117120020000271/i20263_ex99-1.htm>

SEC filings are public and freely redistributable. Only the exhibit was read,
for the ratio and the effective date, and no copy is stored because the single
fact taken from it is recorded above.

**REF-020. Boudoukh, Jacob, Richardson, Matthew and Whitelaw, Robert (1998).**
"The Best of Both Worlds: A Hybrid Approach to Calculating Value at Risk."
DOI [10.2139/ssrn.51420](https://doi.org/10.2139/ssrn.51420). The age-weighted
historical simulation scheme implemented in `historical_sim.age_weights`, in
which a scenario k days old enters the quantile with weight proportional to a
decay factor raised to k. This is the method Goldman describes when it states
that the importance of its historical data reduces over time.

The reference is to the working paper, which is what was verified: Crossref
registers this DOI with these three authors and an issue year of 1998. The
work also appeared in *Risk* magazine the same year, but Crossref does not
hold that version's volume and page numbers and they were not confirmed
independently, so they are not recorded here. Only the metadata above is
verified; the full text was not obtained, and the decay rates used in this
project were chosen for their half-lives rather than taken from the paper.

**REF-017. Basel Committee on Banking Supervision (1996).** "Supervisory
framework for the use of 'backtesting' in conjunction with the internal models
approach to market risk capital requirements." BCBS publication 22, 4 January
1996. The green, yellow and red zones, which this project rederives from the
binomial distribution rather than hard-coding, and checks against the published
boundaries of five and ten for a 99% model over 250 days.
<https://www.bis.org/publ/bcbs22.htm>

Retrieval was attempted on the access date and the BIS server returned an HTML
page rather than the PDF, so no copy is stored. The document downloads normally
from the page above in a browser.

**REF-018. J.P. Morgan and Reuters (1996).** *RiskMetrics Technical Document*,
fourth edition, New York. The exponentially weighted variance estimator and the
daily decay factor of 0.94. Now maintained by MSCI.
<https://www.msci.com/research-and-insights/paper/1996-riskmetrics-technical-document>

## Validation

**REF-019. The MathWorks, Inc.** `varbacktest.pof` documentation, MATLAB Risk
Management Toolbox. Used as an independent implementation to validate the Kupiec
statistic in this project: 1,043 observations with 57 failures at 95% gives
0.46147 with a p-value of 0.49694, and 17 failures at 99% gives 3.51180 and
0.060933. Both p-values are reproduced exactly. The first statistic is
reproduced to the five decimals shown; the second computes to 3.5118129 here,
1.3e-05 away from the displayed 3.51180, which is itself not the correctly
rounded five-decimal value of 3.51181. The test therefore asserts the
statistics to 1e-4 and the p-values to 1e-5, which is documented in
`tests/test_backtest.py` rather than left as an unexplained tolerance.
<https://www.mathworks.com/help/risk/varbacktest.pof.html>

## Which component depends on what

| Reference | Used by |
|---|---|
| REF-001 to REF-010 | `item7a.py`, calibration targets, every comparison in the report |
| REF-011, REF-012 | `factors.py`, `curve.py`, the interest-rate sleeve |
| REF-013 | `factors.py`, the equity, currency and commodity sleeves |
| REF-014 | `backtest.kupiec_pof` |
| REF-015 | `backtest.christoffersen_independence`, `backtest.conditional_coverage` |
| REF-016 | `volatility.py`, the volatility-weighted engine run |
| REF-017 | `backtest.basel_zone_bounds`, `backtest.rolling_zone` |
| REF-018 | `volatility.ewma_forecast` |
| REF-019 | `tests/test_backtest.py` |
| REF-020 | `historical_sim.age_weights`, the age-weighted engine runs |
| REF-021 | `factors.COMMODITY_FUNDS`, the choice of funds over futures |
| REF-022 | `factors.market_closes`, the use of split-adjusted closes |
