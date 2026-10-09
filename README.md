# Reconstructing Goldman Sachs's disclosed VaR model

Goldman Sachs publishes more about its Value-at-Risk model than it has to. Every
10-K gives the methodology in plain language (one-day horizon, 95% confidence,
historical simulation with full revaluation of roughly 70,000 market factors),
the average daily VaR split across four risk categories, a separate line
reconciling those four figures to the firmwide number, and a count of the days
on which a loss exceeded the previous day's VaR.

This project takes that description seriously enough to rebuild it. A
historical-simulation engine runs on seventeen public risk factors, held in a
proxy book sized so that each sleeve's risk matches Goldman's disclosed
category split, and the output is compared against what Goldman reports.

## What this is not

It is not a reconstruction of Goldman's trading book. Positions are not
disclosed at any level of detail and never will be. What the filings pin down
is the *relative* size of four buckets of market risk, and that is enough to
build a portfolio of public instruments whose risk is divided the same way.
Everything here follows from that and nothing more.

The dollar level of this book carries no information either: it is a
normalisation chosen so the tables read in familiar units. The quantities worth
comparing are ratios and behaviour, not magnitudes.

## Research question

Goldman's disclosed diversification effect, defined in the filings as the
difference between total VaR and the sum of the four category VaRs, has sat
between 39.0% and 45.5% of the summed category VaRs for ten consecutive years,
with a standard deviation of 2.1 percentage points across a sample containing
both the COVID crash and the 2022 rate shock.

Can a historical-simulation engine built on free data, calibrated to the same
risk-category split, reproduce that number, its stability, and the backtesting
behaviour of a well-calibrated 95% model?

## What came out of it

**The level is reproducible; the stability is not.** A book resized each year to
the disclosed split averages 42.8% against Goldman's 42.0%, which is close. Its
year-to-year standard deviation is 6.0 percentage points against Goldman's 2.1,
and the yearly gap averages 5.6 points. Run the fixed book through all sixteen
ways the four sleeves can be signed and the two properties trade off against
each other: every configuration averaging 40% or more swings by at least 8.6
points a year, and every configuration steady to within 3.1 points averages
35.6% or below. None reaches both corners.

**Plain historical simulation fails on clustering, not on count.** Over
2016-2025 the model produced 128 exceptions in 2,293 days, a rate of 5.58%
against a nominal 5%, which Kupiec's test does not reject (p = 0.21).
Christoffersen's independence test rejects it overwhelmingly (p < 0.0001). The
exceptions arrive in heaps: 46 of them in 2022 alone, out of 230 trading days.
In that year the realised daily profit and loss had a standard deviation of 98.3
against an average VaR of 96.4, because the two-year lookback window was still
full of 2020 and 2021.

**Rescaling scenarios to current volatility repairs it.** The Hull-White variant
passes all three tests at 99% confidence (Kupiec p = 0.84, independence
p = 0.51, conditional coverage p = 0.79) where plain simulation spends 18.6% of
its days in the Basel red zone and peaks at 19 exceptions in a 250-day window
against a red threshold of 10.

**Full revaluation is worth about a third of a percent here.** Repricing the
bond sleeve by discounting its cashflows at the shocked yield, rather than
multiplying by modified duration, moves VaR by 0.19% to 0.39% a year, with a
largest single day of 0.67%. Convexity is not why one-day VaR needs full
revaluation on a book of vanilla bonds. It is why a book with options does.

**A negative result worth keeping.** The fixed book's year-over-year VaR path
does not track Goldman's: five of nine years move in the same direction,
Spearman's rho is −0.02. Holding exposures still and letting only market
volatility move does not reproduce their path, and the filings say why.
Goldman's own explanation of its VaR change has the same shape in four
consecutive years, 2021 through 2024: volatility moved one way, "partially
offset by" exposures moving the other. A static book cannot reproduce a path
produced by a desk trading against the market.

![Diversification effect over time](reports/figures/diversification_over_time.png)

![Level against stability](reports/figures/stability_frontier.png)

## Reproducing it

```bash
pip install -r requirements.txt
make all
```

`make all` runs seven stages in order. The first downloads ten 10-K filings from
EDGAR and parses the disclosure tables out of them; the rest need no network.
Expect about fifteen minutes end to end, most of it in the robustness sweep,
which runs the engine nineteen times.

```
scripts/01_fetch_disclosures.py      filings from EDGAR, tables to CSV
scripts/02_build_factors.py          risk factors, aligned to one calendar
scripts/03_run_var.py                position sizing and the VaR engine
scripts/04_backtest.py               Kupiec, Christoffersen, Basel zones
scripts/05_regimes_and_convexity.py  regime comparison, convexity
scripts/06_robustness.py             sleeve signs, windows, percentile rule
scripts/07_figures.py                figures for the report
```

SEC asks automated clients to identify themselves. Set `SEC_CONTACT` to your own
name and email before running stage 1.

```bash
export SEC_CONTACT="Your Name your.email@example.com"
```

There are no notebooks. Every result comes from a script that runs top to
bottom, which is a deliberate choice: a notebook that has to be executed in a
particular order to give the right answer is not reproducible, and the written
analysis belongs in `reports/report.md` where it can be read without a kernel.

Tests cover the pieces where an error would produce a plausible wrong number
rather than a crash: the bond pricer against hand calculations, the Kupiec
statistic against an independent implementation, the Basel bounds against the
published 1996 boundaries, and the engine against a look-ahead probe that
rewrites the future and checks the past did not move.

```bash
pytest
```

## Layout

```
config/params.yaml      every tunable setting, with its reason
src/gsvar/              the library
  edgar.py              filing retrieval
  item7a.py             disclosure parsing
  factors.py            risk-factor data
  curve.py              bond pricing
  book.py               the proxy portfolio
  calibration.py        sizing against the disclosures
  historical_sim.py     the VaR engine
  volatility.py         EWMA and GARCH, for the Hull-White variant
  backtest.py           Kupiec, Christoffersen, Basel
  regimes.py            regime and year-over-year comparison
  config.py             loads config/params.yaml
data/raw/               downloads, not committed
data/processed/         parsed disclosures and model output
data/README.md          the factor set, the transformations, the known problems
references/             source register and the preserved filing sections
reports/report.md       the full write-up
```

## Data

Everything is free and comes from the issuer, the regulator, or an exchange.

| What | Source | Covers |
|---|---|---|
| VaR disclosures | Goldman Sachs 10-K filings, EDGAR, CIK 0000886982 | FY2016-FY2025 |
| US yield curve | US Treasury daily par yield curve | 2013-2025 |
| Euro yield curve | ECB euro area AAA government spot rates | 2013-2025 |
| Equity, currency, commodity | Yahoo Finance daily closes | 2013-2025 |

`references/source_register.csv` lists every source with its retrieval details
and the part of the project that depends on it. `data/README.md` documents the
factor set, the transformations, and the known problems with each series.

## Known limitations

The proxy book holds seventeen factors against Goldman's roughly seventy
thousand, which is the single largest difference between this model and theirs,
and it biases the diversification effect downward relative to a book with more
independent sources of risk.

Restricting the panel to days on which Tokyo, London, New York and the ECB were
all open costs about 9% of trading days, leaving 224 to 233 days a year
against Goldman's 250 to 253. Index closes in different time zones are not
simultaneous, which depresses measured cross-market correlation and so overstates
diversification.

Commodity exposure runs through funds rather than futures, which brings roll
yield with it, because WTI front-month settled below zero in April 2020 and a
percentage return is not defined across a sign change.

The exception comparison is not like-for-like and the report does not pretend
otherwise. Goldman counts days on which net revenues fell short of VaR, and
those revenues include intraday market-making income that is positive far more
often than not. The proxy book has no client flow and no bid-offer spread, so
its profit and loss is a clean mark on a static position. Goldman recorded 10
exceptions at 95% across 2016-2025, about 0.4% of days against a nominal 5%,
and the revenue cushion is most of the reason.

## References

Full citations, accession numbers and access dates are in
`references/references.md`. The market risk section of each filing is preserved
verbatim under `references/sec_filings/`.
