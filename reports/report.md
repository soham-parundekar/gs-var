# Reconstructing Goldman Sachs's disclosed Value-at-Risk model and its diversification benefit

## Scope, stated before anything else

Goldman Sachs does not disclose positions. Nothing in this report reconstructs
their trading book, and no number here should be read as an estimate of what
they hold.

What the 10-K does disclose, every year, is the average daily Value-at-Risk of
four risk categories and a reconciling line between those four figures and the
firmwide total. That fixes the *proportions* of market risk, and proportions are
enough to size a portfolio of public instruments so its risk divides the same
way. This report builds that portfolio, runs Goldman's stated methodology over
it, and compares the output against the disclosures.

The dollar level of the proxy book is a normalisation. It was chosen so the
tables read in familiar units and it carries no information. Three things here
are comparable to Goldman and the rest is not: the diversification effect as a
percentage of summed category VaRs, the year-to-year behaviour of that
percentage, and the backtesting properties of a 95% model. Absolute VaR is not
comparable and is never claimed to be.

## 1. Question and hypotheses

Goldman describes its model the same way in every filing in the sample: a
one-day horizon at 95% confidence, a single VaR model covering interest rate,
equity price, currency rate and commodity price risk, computed by historical
simulation with full valuation of approximately 70,000 market factors. The
diversification effect is defined in the filings as the difference between total
VaR and the sum of the four category VaRs, arising because the categories are
not perfectly correlated.

Across FY2016 to FY2025 that effect has been remarkably steady:

| Year | Interest rates | Equity | Currency | Commodity | Sum | Diversification | Total | Effect as % of sum |
|---|---|---|---|---|---|---|---|---|
| 2016 | 45 | 25 | 21 | 17 | 108 | (45) | 63 | 41.7 |
| 2017 | 40 | 24 | 12 | 13 | 89 | (35) | 54 | 39.3 |
| 2018 | 46 | 31 | 14 | 11 | 102 | (42) | 60 | 41.2 |
| 2019 | 46 | 27 | 11 | 12 | 96 | (40) | 56 | 41.7 |
| 2020 | 71 | 55 | 23 | 20 | 169 | (75) | 94 | 44.4 |
| 2021 | 60 | 43 | 13 | 25 | 141 | (55) | 86 | 39.0 |
| 2022 | 97 | 33 | 32 | 47 | 209 | (95) | 114 | 45.5 |
| 2023 | 96 | 29 | 24 | 19 | 168 | (69) | 99 | 41.1 |
| 2024 | 81 | 37 | 26 | 19 | 163 | (71) | 92 | 43.6 |
| 2025 | 70 | 47 | 24 | 17 | 158 | (68) | 90 | 43.0 |

Average daily VaR, $ millions, as first reported. Mean 42.0%, standard
deviation 2.08 percentage points, range 39.0 to 45.5.

Total VaR nearly doubled between 2019 and 2022 and the diversification ratio
moved by four points. That stability across a decade containing a pandemic and
the fastest tightening cycle since the 1980s is the thing worth testing.

Three hypotheses follow.

**H1.** A historical-simulation engine on public factors, sized to the disclosed
category split, reproduces a diversification effect in the disclosed 39 to 45%
range.

**H2.** It reproduces the *stability* of that effect as well as its level.

**H3.** Its exceptions are consistent with a well-calibrated 95% model under
Kupiec's and Christoffersen's tests.

H1 holds on average. H2 fails, and the way it fails is the most informative
result here. H3 fails on independence while passing on count, which is the
classic signature of historical simulation and the reason the volatility-weighted
variant exists.

## 2. Data

### Disclosures

Ten 10-K filings, FY2016 through FY2025, CIK 0000886982, retrieved from EDGAR.
Four tables and one sentence are parsed from each: average daily VaR by
category, period-end VaR by category, the year's high and low VaR, the frequency
distribution of daily net revenues, and the exception count.

None of it is tagged in XBRL, so the tables are found by content. Their HTML
changes shape across the sample: dollar signs sometimes share a cell with the
figure and sometimes sit in their own, negatives appear as `(45)` or split into
`(45` and `)`, the year columns move between two and three, and from FY2019 the
firmwide high/low row has its label on a separate line from its numbers. Every
row is flattened to a string and the signed numbers read out of it, which
survives all of it.

Two parsing results are worth recording.

Because each filing restates the prior year, most years appear twice and the two
readings agree. One year does not. The FY2023 filing reports 2022 average daily
VaR as 96/35/32/47 with a total of 113, where the FY2022 filing reported
97/33/32/47 and 114. The filing explains it: during the first quarter of 2023
Goldman added the currency exposure on certain debt and equity positions to VaR
and removed certain other positions, and conformed the prior period. The figures
used here are as first reported, so that a scope change does not sit inside the
time series. The restated values are kept in the CSV with their source year.

The identity that categories plus the diversification effect equals the total
holds exactly in all twelve parsed years, which is the strongest available check
that the tables were read correctly.

### Risk factors

Seventeen factors, all free, from the issuer, the central bank or the exchange.

| Category | Factors | Source |
|---|---|---|
| Interest rates | US par yields at 2, 5, 10, 30 years | US Treasury daily par yield curve |
| | Euro area AAA spot rates at 2, 5, 10 years | ECB |
| Equity prices | S&P 500, EURO STOXX 50, Nikkei 225, MSCI EM | Yahoo Finance |
| Currency rates | EUR/USD, USD/JPY, GBP/USD | Yahoo Finance |
| Commodity prices | gold, crude oil, base metals, via funds | Yahoo Finance |

Equity indices enter in local currency. A dollar investor holding the Nikkei
carries yen risk too, but Goldman reports currency risk in its own category, so
including it in the equity sleeve would double-count it and make the attribution
meaningless.

Commodities enter through funds rather than front-month futures. On 20 April
2020 the WTI front-month contract settled at minus $37.63, and a percentage
return is not defined across a sign change: the series shows a single day of
minus 306%, which is arithmetic rather than economics. Funds cannot price below
zero. The cost is roll yield, noted in the limitations.

The panel is restricted to days on which every market was open, which costs
about 9% of trading days and leaves 224 to 233 days a year against
Goldman's 250 to 253. Forward-filling a closed market would plant runs of zero
returns in the scenario set and understate that factor's risk.

Two data checks are worth naming because both fired during development. A
non-positive price anywhere breaks a return calculation, and a long run of
identical values means a stale feed. The second check needs different tolerances
for the two kinds of factor: the two-year Treasury yield sat at 0.13% through the
second half of 2020 and, quoted to the basis point, genuinely did not move on
19.4% of days. Flagging that would be flagging the monetary policy of 2020. A
traded price repeating for five days running is still an error.

## 3. Method

### Instruments and revaluation

Equity, currency and commodity positions are linear in their factor, so
repricing them is a multiplication and the distinction between full revaluation
and a delta approximation does not arise.

The rate sleeve is where full revaluation means something. US positions are par
coupon bonds priced off the par yield curve; because a par bond's yield to
maturity equals the par yield by construction, discounting its own cashflows at
that yield reprices it exactly with no curve interpolation. Euro positions are
zero-coupon bonds priced off the ECB spot curve, exact for the same reason.
Bootstrapping one convention into the other would need a yield at every coupon
date and so an interpolation assumption the data does not support.

Positions are constant-maturity: each day the book holds a freshly struck bond
at the stated tenor. That matches how the par curve itself is built and avoids a
ten-year backtest in which the two-year note matures halfway through.

### Sizing the book

Within a sleeve, instruments are weighted to contribute equal standalone VaR.
Equal notional would not do. At the 2019 year-end curve a thirty-year par bond
has a modified duration of 21.5 against 2.0 for a two-year note, and once the
different volatility of the two yields is counted it carries about fifteen times
the one-day risk per unit of notional. An equally sized rates sleeve would be a
thirty-year position with rounding errors attached.

Each sleeve is then scaled so its average daily standalone VaR over the
calibration year equals Goldman's disclosed figure for that category and year.
The scaling is closed form rather than iterative. Profit and loss on every
position here is proportional to notional, because scenario returns do not
depend on position size, so multiplying a sleeve's notionals by k multiplies
every scenario outcome by k and therefore any percentile of that distribution by
k. One division per sleeve lands on target. Measured afterwards, the largest
sizing error across all years and sleeves is 6.6 × 10⁻¹⁴ percent, which is the
claim verified rather than assumed.

That exactness is the design. The sum of the four category VaRs matches
Goldman's by construction and therefore carries no information. Total VaR and
the diversification effect are *not* matched. They come out of the correlations
in the public factor data, and comparing them against the disclosures is the
experiment.

Two books are built. The **recalibrated** book is resized every year to that
year's disclosed split, which removes the exposure mix from the comparison and
leaves only the correlations. It is not a forecast: sizing the 2022 book uses a
figure published in February 2023. The **fixed** book is sized once on 2019 and
left alone, so its VaR path responds only to the market. Only the fixed book is
backtested, because only its notionals were set before the data it is scored on.

### The engine

For each valuation date, the scenario set is the previous 502 trading days of
factor moves, about two years, applied to the book as it stands at that day's
market levels. The 5% quantile of the resulting profit and loss distribution is
the VaR, reported as a positive loss. Category VaR uses only that category's
positions; total VaR moves every factor together, historical day by historical
day. The diversification effect is total minus the sum of the four.

VaR stamped with date t is compared against the profit and loss realised on t+1,
which is Goldman's own stated convention: daily net revenues are compared with
VaR calculated as of the end of the prior business day. No quantity dated t+1
enters the VaR dated t, and a test enforces this by rewriting every move after a
cut-off and checking that nothing on or before it changed.

Window length and the percentile convention are not disclosed. Two years and
linear interpolation are the defaults; both alternatives are run in section 6.

## 4. Results

### Diversification

| Year | Goldman | Recalibrated book | Fixed book | Total VaR error |
|---|---|---|---|---|
| 2016 | 41.7 | 47.0 | 47.3 | −9.1% |
| 2017 | 39.3 | 44.7 | 44.8 | −8.9% |
| 2018 | 41.2 | 43.2 | 40.8 | −3.4% |
| 2019 | 41.7 | 42.8 | 42.8 | −2.0% |
| 2020 | 44.4 | 51.1 | 47.3 | −12.0% |
| 2021 | 39.0 | 50.3 | 48.8 | −18.6% |
| 2022 | 45.5 | 42.1 | 35.2 | +6.2% |
| 2023 | 41.1 | 33.7 | 28.3 | +12.6% |
| 2024 | 43.6 | 33.8 | 24.3 | +17.2% |
| 2025 | 43.0 | 39.4 | 30.0 | +6.4% |
| **Mean** | **42.0** | **42.8** | **39.0** | |
| **Std dev** | **2.08** | **5.98** | **8.87** | |

H1 holds. The recalibrated book averages 42.8% against Goldman's 42.0%, well
inside the disclosed range.

H2 fails. The model's ratio swings three times as much year to year, and the
error in total VaR changes sign in 2022: the proxy book over-diversifies before
then, understating total VaR by up to 18.6%, and under-diversifies afterwards,
overstating it by up to 17.2%. The turn is the equity-bond correlation flipping
positive in the inflation regime, which removes the main diversifier from a
directional book. Goldman's ratio went *up* that year, to its sample maximum of
45.5%.

### Is it the long-only assumption?

A dealer's inventory is not reliably long anything, and the sign of each sleeve
is not disclosed. Since the diversification effect depends on how the sleeves
line up, all sixteen sign combinations were run on the fixed book.

| | Mean ratio | Year-to-year std dev |
|---|---|---|
| Goldman | 42.0 | 2.08 |
| Seven variants averaging ≥ 40% | 40.5 to 45.7 | 8.66 to 10.77 |
| Four variants with std dev ≤ 3.1 | 28.5 to 35.6 | 2.19 to 3.02 |

The two properties trade off and no configuration reaches both corners. The
steadiest book in the set varies by 2.19 points a year, which is Goldman's 2.08
almost exactly, but it averages 33.9%. Every book that averages 40% or more
swings by at least 8.66 points.

That is the central finding. The level is easy and the steadiness is not. A
static four-sleeve book with fixed signs cannot hold a diversification ratio
near 42% through both 2021 and 2023, because the correlation structure
underneath it changed and the book did not. Goldman's did hold, which implies
something the proxy lacks: a far larger and more independent factor set,
exposures that move, or both. The filings support the second. Goldman's own
commentary attributes year-over-year VaR changes to exposure changes as well as
volatility, and the Q1 2023 scope change shows them moving positions in and out
of the measure.

### Does the model's VaR move when Goldman's does?

The fixed book answers this one, because its exposures never change and its
VaR therefore responds only to the market.

| Year | Model average VaR | Change | Goldman | Change | Same direction |
|---|---|---|---|---|---|
| 2016 | 62.6 | | 63 | | |
| 2017 | 64.4 | +2.9% | 54 | −14.3% | no |
| 2018 | 56.9 | −11.8% | 60 | +11.1% | no |
| 2019 | 54.9 | −3.5% | 56 | −6.7% | yes |
| 2020 | 60.7 | +10.6% | 94 | +67.9% | yes |
| 2021 | 59.6 | −1.7% | 86 | −8.5% | yes |
| 2022 | 96.4 | +61.5% | 114 | +32.6% | yes |
| 2023 | 132.1 | +37.1% | 99 | −13.2% | no |
| 2024 | 134.6 | +2.0% | 92 | −7.1% | no |
| 2025 | 104.3 | −22.6% | 90 | −2.2% | yes |

Five of nine years agree on direction. Pearson correlation on the changes is
0.29 (p = 0.45) and Spearman's rank correlation is −0.02 (p = 0.97). There is
no relationship worth reporting, and the average gap between the two
percentage changes is 24 points.

That is a clean negative result, and the filings say why. Goldman explains its
own year-over-year VaR change in every annual report, and in four consecutive
years the explanation has the same shape:

> Our average daily VaR decreased to $86 million in 2021 from $94 million in
> 2020, due to lower levels of volatility, partially offset by increased
> exposures. (FY2021)

> Our average daily VaR increased to $114 million in 2022 from $86 million in
> 2021, due to higher levels of volatility, partially offset by reduced
> exposures. (FY2022)

> Our average daily VaR decreased to $99 million in 2023 from $113 million in
> 2022, due to lower levels of volatility, partially offset by increased
> exposures. (FY2023)

Goldman moved exposure against volatility in each of those years, and in 2024
as well. A book that holds its positions still cannot reproduce a path
produced by a desk that trades against the market, and the 2023 divergence is
exactly that: model VaR rose 37% as the 2022 scenarios sat in the window,
while Goldman's fell 13% as volatility subsided and they added exposure into
it. The ten extracted sentences are in
`data/processed/disclosed_var_commentary.csv`.

### Regimes

| Regime | Days | Mean VaR | Diversification | Realised P&L sd | Exception rate | Equity vol (ann.) | 10y vol (bp/day) |
|---|---|---|---|---|---|---|---|
| calm 2017-2019 | 687 | 58.8 | 42.8% | 31.7 | 4.2% | 12.7% | 4.0 |
| COVID shock 2020 | 82 | 61.5 | 45.7% | 75.0 | 12.2% | 57.2% | 8.8 |
| recovery 2021 | 231 | 59.7 | 48.8% | 34.4 | 4.8% | 13.7% | 4.5 |
| rate shock 2022 | 195 | 102.1 | 34.3% | 102.8 | 20.0% | 25.4% | 8.4 |
| after 2024-2025 | 452 | 119.6 | 27.2% | 53.6 | 1.6% | 16.7% | 5.8 |

The COVID window is the sharper illustration of the lag. Equity volatility ran
at 57% annualised and realised profit and loss had a standard deviation of
75.0, while VaR averaged 61.5, barely above its calm-period level of 58.8,
because the shock was six weeks old and the window was two years long. One day
in eight was an exception.

The last row is the mirror image. Mean VaR is at its sample peak of 119.6 with
volatility back to ordinary levels, and the exception rate collapses to 1.6%
against a nominal 5%.

### Backtesting

Fixed book, scored on its own realised profit and loss, out of sample with
respect to sizing from 2020 onward.

| Model | Confidence | Period | Days | Exceptions | Rate | Kupiec p | Independence p | Joint p | Worst Basel zone |
|---|---|---|---|---|---|---|---|---|---|
| Historical simulation | 95% | 2016-2025 | 2293 | 128 | 5.58% | 0.209 | <0.0001 | <0.0001 | red |
| Historical simulation | 95% | 2020-2025 | 1373 | 88 | 6.41% | 0.021 | <0.0001 | <0.0001 | red |
| Volatility weighted | 95% | 2016-2025 | 2293 | 117 | 5.10% | 0.822 | 0.008 | 0.028 | yellow |
| Volatility weighted | 95% | 2020-2025 | 1373 | 71 | 5.17% | 0.772 | 0.012 | 0.040 | yellow |
| Historical simulation | 99% | 2016-2025 | 2293 | 37 | 1.61% | 0.007 | <0.0001 | <0.0001 | red |
| Historical simulation | 99% | 2020-2025 | 1373 | 30 | 2.19% | 0.0001 | <0.0001 | <0.0001 | red |
| Volatility weighted | 99% | 2016-2025 | 2293 | 22 | 0.96% | 0.844 | 0.514 | 0.793 | yellow |
| Volatility weighted | 99% | 2020-2025 | 1373 | 16 | 1.17% | 0.549 | 0.539 | 0.692 | yellow |

H3 fails for plain historical simulation, and it fails on the right test. Over
the full sample the exception *count* is almost exactly where it should be and
Kupiec cannot reject it. Their *arrangement* is indefensible. The model spends
13.7% of days in the Basel red zone at 95% and 18.6% at 99%, peaking at 19
exceptions in a 250-day window against a red threshold of 10.

Year by year the reason is plain:

| Year | Mean VaR | Realised P&L std dev | VaR ÷ 1.645 σ | Exceptions | Days |
|---|---|---|---|---|---|
| 2019 | 54.9 | 33.4 | 1.00 | 11 | 225 |
| 2020 | 60.7 | 51.0 | 0.72 | 13 | 227 |
| 2021 | 59.7 | 34.4 | 1.05 | 11 | 231 |
| 2022 | 96.4 | 98.3 | 0.60 | 46 | 230 |
| 2023 | 132.1 | 85.1 | 0.94 | 11 | 233 |
| 2024 | 134.6 | 60.1 | 1.36 | 3 | 228 |
| 2025 | 104.3 | 46.2 | 1.37 | 4 | 224 |

In 2022 the model carried a VaR of 96.4 against profit and loss with a standard
deviation of 98.3. It was 40% short of what contemporaneous volatility called
for, because the 502-day window was still full of 2020 and 2021. Then it
overshot for two years, running at 1.36 and 1.37 times the normal benchmark as
the 2022 observations stayed in the window and the market calmed. Historical
simulation is late in both directions, and the second error is a ghost: VaR
stays high because of days that are still in the sample, not because of anything
happening in the market.

The five worst days all correspond to real events, which is a check that the
engine is marking the book sensibly rather than a finding:

| Date of loss | Loss | VaR the day before | Multiple |
|---|---|---|---|
| 2022-06-13 | −385.3 | 95.1 | 4.05 |
| 2020-03-18 | −344.2 | 62.0 | 5.55 |
| 2022-09-26 | −333.2 | 117.3 | 2.84 |
| 2020-03-12 | −270.0 | 59.3 | 4.56 |
| 2023-03-14 | −240.8 | 128.9 | 1.87 |

The June 2022 CPI print and the Federal Reserve's 75 basis point response, the
COVID crash, the gilt crisis, and the week Silicon Valley Bank failed.

### The volatility-weighted variant

Hull and White's correction rescales each historical return by the ratio of
today's conditional volatility to the volatility in force when the return
happened, so the scenario set is restated in today's units before the percentile
is taken. Volatility is estimated by exponentially weighted variance with the
RiskMetrics decay of 0.94, which is causal by construction: the estimate stamped
with date t uses only moves up to t.

At 99% the corrected model is not rejected by any of the three tests, and it
never enters the Basel red zone, peaking at 5 exceptions in a 250-day window. At
95% it passes on count comfortably (p = 0.82) and still fails independence
(p = 0.008), though the statistic falls from 32.6 to 7.1. Rescaling fixes most
of the clustering and not all of it.

### What full revaluation is worth

The rate sleeve was priced twice on identical scenarios: once by discounting the
cashflows again at the shocked yield, once by multiplying by modified duration.

| Year | Full revaluation vs duration | Largest single day |
|---|---|---|
| 2019 | −0.19% | 0.33% |
| 2022 | −0.35% | 0.63% |
| 2024 | −0.36% | 0.65% |

The gap never reaches four tenths of a percent on an annual average, and 0.67%
on the worst single day of the sample. The sign is right (convexity means a long
bond loses less than duration predicts, so the left tail is less bad and VaR is
lower) but the magnitude is small, and it should be said plainly rather than
dressed up. Over a one-day horizon with a daily yield move of about five basis
points, convexity is a second-order term. Full revaluation earns its cost on
instruments whose value is a sharply non-linear function of the factor, which
means options, and on longer horizons and larger shocks. On vanilla bonds at one
day it buys a third of a percent.

### Comparison against Goldman's own exception counts

| Year | Model exceptions (95%) | Model days | Model rate | Goldman |
|---|---|---|---|---|
| 2016 | 11 | 233 | 4.7% | 0 |
| 2018 | 14 | 230 | 6.1% | 2 |
| 2020 | 13 | 227 | 5.7% | 2 |
| 2022 | 46 | 230 | 20.0% | 2 |
| 2024 | 3 | 228 | 1.3% | 2 |

Goldman recorded 10 exceptions at 95% across 2016-2025, roughly 0.4% of days
against a nominal 5%. A literal Kupiec test on that count rejects calibration at
any conventional level, and the rejection would be meaningless, because the two
measurements are not the same quantity. Goldman compares VaR against *net
revenues*, which include intraday market-making income that is positive far more
often than not; the firm says so in the filing and says it is why exceptions are
rarer than the confidence level implies. The proxy book has no client flow and
no bid-offer spread, so its profit and loss is a clean mark on a static
position. The gap between 0.4% and 5% is a reasonable estimate of how much the
revenue cushion is worth, and it is large.

## 5. Validation

Every number that could be checked against something external was.

The bond pricer reproduces a hand calculation to seven decimals (a ten-year 5%
semiannual bond at a 6% yield prices at 92.5612626), prices par bonds at exactly
100 at their own yield, and its analytic modified duration matches a numerical
derivative. Convexity has the correct sign in both directions.

The Kupiec statistic reproduces an independent implementation on two published
cases to five decimals: 1,043 observations with 57 failures at 95% gives
0.46147 with a p-value of 0.49694, and 17 failures at 99% gives 3.51180 and
0.060933. Its analytic limits hold (zero exceptions give −2T·ln(1−p); a failure
rate exactly equal to coverage gives zero) and a Monte Carlo under the null
gives empirical size of 4.8 to 5.8% at a nominal 5%.

The Basel zone boundaries are rederived from the binomial rather than
hard-coded, and reproduce the published 5 and 10 for a 99% model over 250 days.
That derivation matters because the published boundaries are specific to 99%: a
correctly calibrated 95% model is expected to break about twelve times in 250
days and would sit in the red zone permanently if the 99% thresholds were
carried across unchanged.

The disclosure parser is checked against the identity that categories plus the
diversification effect equals the total, which holds in all twelve years, and
against overlapping years across filings, which agree everywhere except the
documented 2022 restatement. Net revenue bucket counts sum to the stated totals
in all fourteen year-filing pairs.

The engine is checked for exact homogeneity in notional, for a non-positive
diversification effect, and for look-ahead by rewriting all data after a cut-off
and confirming nothing before it moved.

One guard deserves explanation. The diversification effect is almost always
negative, but VaR is not a subadditive risk measure, and on a sufficiently
awkward tail a whole book really can show a larger loss quantile than the sum of
its parts. That is a property of the measure, not a defect in the code, and it
is the reason expected shortfall exists. The engine therefore records rare
positive days and refuses the run only when they exceed one day in a hundred,
which is the threshold that separates the phenomenon from a sign error. On all
reported configurations the count is zero.

## 6. Robustness

**Lookback window.** At 252, 502 and 756 days the mean diversification ratio is
38.2%, 39.0% and 39.7%, and exceptions are 128, 128 and 134. Independence is
rejected at every window. None of the conclusions depends on the choice.

**Percentile convention.** Linear interpolation and the discrete order statistic
differ by 0.02% of the VaR level and produce identical exception counts.

**Sleeve signs.** Reported in section 4. This is the only specification choice
that moves the headline result, which is why all sixteen were run rather than
sampled.

## 7. Limitations

Seventeen factors against roughly seventy thousand is the largest single
difference between this model and Goldman's, and it biases the diversification
effect downward relative to a book with more independent sources of risk.

Index closes in Tokyo, London and New York are not simultaneous. Non-synchronous
pricing depresses measured cross-market correlation and so overstates
diversification, in the opposite direction to the factor-count bias. Neither
has been quantified here.

Restricting to days when all markets were open leaves 224 to 233 observations a
year against Goldman's 250 to 253, which reduces the power of every test
reported.

Commodity exposure carries roll yield because it runs through funds. Over a
one-day horizon the drag is second order, but it is a real difference from a
spot book.

The rate sleeve mixes par coupon bonds in dollars with zero-coupon bonds in
euros, following each source's native convention. A zero has longer duration
than a par bond of the same maturity, so the two sleeves are not interchangeable
per unit of notional. Sizing targets risk rather than notional, which absorbs
it, but the instrument sets are not identical.

At near-zero policy rates, Treasury's one basis point quotation granularity
means the two-year yield shows no change on 19.4% of days in the sample. Real,
and it understates true rate variability slightly in the 2015-2021 window.

The recalibrated book uses figures published after the year it sizes. That is
appropriate for a structural comparison and would be indefensible for a
forecast, which is why the backtest uses the fixed book only.

## 8. What the exercise shows

Goldman's methodology description is specific enough to be reimplemented, and
reimplementing it on seventeen public factors lands the average diversification
benefit within one point of theirs. That much transfers.

The steadiness does not. Their disclosed ratio moved by 2.1 points a year
through a pandemic and a rate shock; a static book with fixed sleeve signs
cannot do better than a trade-off between matching that level and matching that
steadiness, and the gap is wide enough that no configuration out of sixteen
comes close to both. Whatever holds Goldman's ratio still is not present in a
four-sleeve proxy, and the most likely candidates are a much larger independent
factor set and exposures that are actively managed rather than held.

On the engine itself, the backtest says something a count alone would miss. A
model can sit at 5.58% against a nominal 5% and still be unusable, because its
failures arrive in heaps rather than at random. Rescaling the scenario set to
current volatility turns a model that spends a fifth of its days in the Basel
red zone into one that is not rejected on any of the three tests at 99%. That is
the largest improvement available anywhere in this project, and it costs one
volatility estimate per factor.

## References

Citations, accession numbers and access dates are in
`../references/references.md`. The market risk section of each filing is
preserved verbatim under `../references/sec_filings/`.
