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
simulation with full valuation, shocking the relevant market factors for each
position simultaneously. The FY2016 and FY2017 filings put the factor count at
approximately 70,000; later filings drop the number. Two further details are
stated in every filing and matter more than they look: the scenarios are drawn
from five years of historical data, and that data is weighted so the importance
of older observations decays. The diversification effect is defined in the
filings as the difference between total VaR and the sum of the four category
VaRs, arising because the categories are not perfectly correlated.

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
moved by four points. That stability across a decade containing a pandemic, a
zero-rate period and more than 500 basis points of policy tightening is the
thing worth testing.

Three hypotheses follow.

**H1.** A historical-simulation engine on public factors, sized to the disclosed
category split, reproduces a diversification effect in the disclosed 39 to 45%
range.

**H2.** It reproduces the *stability* of that effect as well as its level.

**H3.** Its exceptions are consistent with a well-calibrated 95% model under
Kupiec's and Christoffersen's tests.

H1 holds: the fixed book averages 41.6% against 42.0%. H2 fails, and the way it
fails is the most informative result here — it fails at the disclosed window,
and it fails worse once the disclosed age weighting is added, which rules out
the explanation that the replication is simply using a blunter method than the
bank. H3 fails outright at the disclosed window, on count as well as on
independence, and the volatility-weighted variant repairs it.

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

For each valuation date, the scenario set is the previous 1,260 trading days of
factor moves, applied to the book as it stands at that day's market levels. The
length is not a guess: every filing in the sample states that Goldman samples
from five years of historical data. The 5% quantile of the resulting profit and
loss distribution is the VaR, reported as a positive loss. Category VaR uses
only that category's positions; total VaR moves every factor together,
historical day by historical day. The diversification effect is total minus the
sum of the four.

VaR stamped with date t is compared against the profit and loss realised on t+1,
which is Goldman's own stated convention: daily net revenues are compared with
VaR calculated as of the end of the prior business day. No quantity dated t+1
enters the VaR dated t, and a test enforces this by rewriting every move after a
cut-off and checking that nothing on or before it changed.

Two settings in the filings deserve more attention than the VaR tables usually
get. The window is one. The other is that "the historical data is weighted so
that the relative importance of the data reduces over time," which is age
weighting: a scenario k days old enters with weight proportional to some decay
raised to k. The scheme is disclosed; the rate is not. The baseline here
therefore uses the disclosed window with equal weights, so that no undisclosed
parameter sits inside it, and section 6 runs the weighting as a grid. That
grid turns out to matter more than any other choice in this report.

The percentile convention is also undisclosed. Linear interpolation is the
default and the discrete order statistic is run alongside it in section 6,
where it moves the VaR level by 0.3%.

## 4. Results

### Diversification

| Year | Goldman | Recalibrated book | Fixed book | Total VaR error |
|---|---|---|---|---|
| 2016 | 41.7 | 53.9 | 49.3 | −21.0% |
| 2017 | 39.3 | 47.6 | 46.1 | −13.7% |
| 2018 | 41.2 | 44.8 | 43.2 | −6.1% |
| 2019 | 41.7 | 45.1 | 45.1 | −5.8% |
| 2020 | 44.4 | 49.6 | 45.5 | −9.4% |
| 2021 | 39.0 | 48.1 | 45.9 | −14.9% |
| 2022 | 45.5 | 43.6 | 42.4 | +3.3% |
| 2023 | 41.1 | 37.7 | 34.5 | +5.7% |
| 2024 | 43.6 | 39.1 | 32.3 | +8.0% |
| 2025 | 43.0 | 37.9 | 31.9 | +9.1% |
| **Mean** | **42.0** | **44.7** | **41.6** | |
| **Std dev** | **2.08** | **5.35** | **6.33** | |

H1 holds, and the fixed book holds it more tightly than the recalibrated one:
41.6% against Goldman's 42.0%, a gap of four tenths of a point over ten years.
Resizing the book annually to the disclosed split pushes the average up to
44.7%, which is outside the disclosed range of 39.0 to 45.5 on the high side.
The fixed book is the cleaner comparison in any case, since its notionals were
set on 2019 and never touched afterwards.

H2 fails, and it fails in a more specific way than a variance comparison
conveys. Both model series decline monotonically in the second half of the
sample: the recalibrated ratio falls at 1.49 points a year, with a regression
on the year index giving *p* = 0.002 and R² = 0.71. Goldman's series has no
trend at all (*p* = 0.23). The error in total VaR changes sign in 2022, from
over-diversifying and understating total VaR by up to 21.0% to
under-diversifying and overstating it by up to 9.1%. The turn is the
equity-bond correlation flipping positive in the inflation regime, which
removes the main diversifier from a directional book. Goldman's ratio went *up*
that year, to its sample maximum of 45.5%.

The drift is what a five-year equally weighted window does to a book that
never changes. As the window rolls forward it swallows the inflation-era
correlation structure and never sheds it, so the measured diversification
decays. A dealer repositioning daily has no such ratchet.

### Is it the long-only assumption?

A dealer's inventory is not reliably long anything, and the sign of each sleeve
is not disclosed. Since the diversification effect depends on how the sleeves
line up, all sixteen sign combinations were run on the fixed book.

| | Mean ratio | Year-to-year std dev |
|---|---|---|
| Goldman | 42.0 | 2.08 |
| Eight variants averaging ≥ 40% | 41.6 to 48.0 | 3.68 to 7.62 |
| Five variants with std dev ≤ 2.08 | 29.0 to 35.6 | 1.76 to 2.06 |

The two properties trade off and no configuration reaches both corners. Taking
Goldman's own standard deviation as the bar rather than a round number, five of
the sixteen books are at least that steady, and the best of them averages
35.6%, six points below the disclosure. Eight books average 40% or more, and
the steadiest of those varies by 3.68 points a year, three quarters again as
much as Goldman. Nothing in the set does both.

That is the central finding. The level is easy and the steadiness is not. A
static four-sleeve book with fixed signs cannot hold a diversification ratio
near 42% through both 2021 and 2023, because the correlation structure
underneath it changed and the book did not. Goldman's did hold, which implies
something the proxy lacks: a far larger and more independent factor set,
exposures that move, or both. The filings support the second. Goldman's own
commentary attributes year-over-year VaR changes to exposure changes as well as
volatility, and the Q1 2023 scope change shows them moving positions in and out
of the measure.

The obvious objection is that the gap is an artifact of a cruder method than
Goldman's. Section 6 tests that directly, by adopting the disclosed window and
then the disclosed age weighting. Neither closes the gap, and the weighting
widens it while making the engine a demonstrably better risk model. The gap
survives being handed the bank's own methodology, which is the strongest
version of this result the public data supports.

### Does the model's VaR move when Goldman's does?

The fixed book answers this one, because its exposures never change and its
VaR therefore responds only to the market.

| Year | Model average VaR | Change | Goldman | Change | Same direction |
|---|---|---|---|---|---|
| 2016 | 60.8 | | 63 | | |
| 2017 | 56.2 | −7.6% | 54 | −14.3% | yes |
| 2018 | 55.4 | −1.5% | 60 | +11.1% | no |
| 2019 | 52.7 | −4.8% | 56 | −6.7% | yes |
| 2020 | 56.3 | +6.7% | 94 | +67.9% | yes |
| 2021 | 52.9 | −5.9% | 86 | −8.5% | yes |
| 2022 | 63.1 | +19.3% | 114 | +32.6% | yes |
| 2023 | 89.1 | +41.0% | 99 | −13.2% | no |
| 2024 | 97.0 | +9.0% | 92 | −7.1% | no |
| 2025 | 102.4 | +5.5% | 90 | −2.2% | no |

Five of nine years agree on direction. Pearson correlation on the changes is
0.07 (p = 0.86) and Spearman's rank correlation is 0.32 (p = 0.41). There is
no relationship worth reporting, and the average gap between the two
percentage changes is 20 points.

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
exactly that: model VaR rose 41% as the 2022 scenarios sat in the window,
while Goldman's fell 13% as volatility subsided and they added exposure into
it. The five-year window makes the divergence worse rather than better, since
the 2022 scenarios stay in the set through 2025 and the model's VaR is still
climbing in the last year of the sample while Goldman's drifts down. The ten
extracted sentences are in `data/processed/disclosed_var_commentary.csv`.

### Regimes

| Regime | Days | Mean VaR | Diversification | Realised P&L sd | Exception rate | Equity vol (ann.) | 10y vol (bp/day) |
|---|---|---|---|---|---|---|---|
| calm 2017-2019 | 687 | 54.8 | 44.8% | 28.7 | 3.5% | 12.7% | 4.0 |
| COVID shock 2020 | 82 | 56.8 | 45.4% | 67.9 | 11.0% | 57.2% | 8.8 |
| recovery 2021 | 231 | 52.9 | 45.8% | 31.0 | 4.8% | 13.7% | 4.5 |
| rate shock 2022 | 195 | 64.9 | 42.3% | 94.9 | 32.3% | 25.4% | 8.4 |
| after the shock 2024-2025 | 452 | 99.7 | 32.1% | 49.2 | 3.3% | 16.7% | 5.8 |

The COVID window illustrates the lag. Equity volatility ran at 57% annualised
and realised profit and loss had a standard deviation of 67.9, while VaR
averaged 56.8, barely above its calm-period level of 54.8, because the shock
was six weeks old and the window held five years of mostly quiet data. One day
in nine was an exception.

The rate shock of 2022 is worse, and it is the clearest cost of the disclosed
window run without the disclosed weighting. Nearly a third of days breached.
Five years of scenarios in early 2022 reach back to 2017, a period containing
almost no rate volatility, so the engine entered the fastest tightening cycle
in four decades carrying a scenario set that had never seen one.

The last row is the mirror image, and it is where the downward drift in the
diversification ratio shows up. Mean VaR sits at its sample peak of 99.7 with
volatility back to ordinary levels, the exception rate collapses to 3.3%
against a nominal 5%, and the measured diversification has fallen to 32.1%
from 44.8% in the calm years — not because the book changed, but because the
window now holds 2022 and will not let go of it.

### Backtesting

Fixed book, scored on its own realised profit and loss, out of sample with
respect to sizing from 2020 onward.

| Model | Confidence | Period | Days | Exceptions | Rate | Kupiec p | Independence p | Joint p | Worst Basel zone |
|---|---|---|---|---|---|---|---|---|---|
| Historical simulation | 95% | 2016-2025 | 2293 | 160 | 6.98% | <0.0001 | <0.0001 | <0.0001 | red |
| Historical simulation | 95% | 2020-2025 | 1373 | 127 | 9.25% | <0.0001 | <0.0001 | <0.0001 | red |
| Volatility weighted | 95% | 2016-2025 | 2293 | 117 | 5.10% | 0.822 | 0.110 | 0.272 | yellow |
| Volatility weighted | 95% | 2020-2025 | 1373 | 70 | 5.10% | 0.868 | 0.213 | 0.454 | yellow |
| Historical simulation | 99% | 2016-2025 | 2293 | 45 | 1.96% | <0.0001 | <0.0001 | <0.0001 | red |
| Historical simulation | 99% | 2020-2025 | 1373 | 44 | 3.20% | <0.0001 | <0.0001 | <0.0001 | red |
| Volatility weighted | 99% | 2016-2025 | 2293 | 19 | 0.83% | 0.395 | 0.573 | 0.594 | green |
| Volatility weighted | 99% | 2020-2025 | 1373 | 13 | 0.95% | 0.842 | 0.618 | 0.866 | green |

H3 fails for plain historical simulation, and at the disclosed window it fails
on every test rather than only on clustering. The exception rate is 6.98% over
the full sample against a nominal 5%, which Kupiec rejects outright, and 9.25%
from 2020. The model spends 18.2% of days in the Basel red zone at 95% and the
same at 99%, peaking at 73 exceptions in a 250-day window against a red
threshold of 27.

This is worse than the two-year window produced, and the reason is the point of
the exercise. A five-year equally weighted window is slow. Year by year:

| Year | Mean VaR | Realised P&L std dev | VaR ÷ 1.645 σ | Exceptions | Days |
|---|---|---|---|---|---|
| 2019 | 52.7 | 30.0 | 1.07 | 8 | 225 |
| 2020 | 56.3 | 46.1 | 0.74 | 12 | 227 |
| 2021 | 52.9 | 31.0 | 1.04 | 11 | 231 |
| 2022 | 63.1 | 90.8 | 0.42 | 70 | 230 |
| 2023 | 89.1 | 78.8 | 0.69 | 19 | 233 |
| 2024 | 97.0 | 55.1 | 1.07 | 11 | 228 |
| 2025 | 102.4 | 42.4 | 1.47 | 4 | 224 |

In 2022 the model carried a VaR of 63.1 against profit and loss with a standard
deviation of 90.8, which is 58% short of what contemporaneous volatility called
for, and 70 of 230 days breached. Then it overshoots: by 2025 it runs at 1.47
times the normal benchmark with four exceptions all year, because the 2022
observations are still in the window and will stay there until 2027. Historical
simulation is late in both directions and the long window makes it later. The
second error is a ghost — VaR stays high because of days that remain in the
sample, not because of anything happening in the market.

Goldman's disclosure anticipates exactly this. It weights its scenarios toward
recent observations, and section 6 shows that doing the same rescues the
coverage this table fails.

The five worst days all correspond to real events, which is a check that the
engine is marking the book sensibly rather than a finding:

| Date of loss | Loss | VaR the day before | Multiple |
|---|---|---|---|
| 2022-06-13 | −355.0 | 58.7 | 6.05 |
| 2020-03-18 | −311.4 | 55.6 | 5.60 |
| 2022-09-26 | −302.3 | 69.3 | 4.36 |
| 2020-03-12 | −242.6 | 54.8 | 4.43 |
| 2023-03-14 | −226.0 | 86.0 | 2.63 |

The June 2022 CPI print and the Federal Reserve's 75 basis point response, the
COVID crash, the gilt crisis, and the week Silicon Valley Bank failed.

### The volatility-weighted variant

Hull and White's correction rescales each historical return by the ratio of
today's conditional volatility to the volatility in force when the return
happened, so the scenario set is restated in today's units before the percentile
is taken. Volatility is estimated by exponentially weighted variance with the
RiskMetrics decay of 0.94, which is causal by construction: the estimate stamped
with date t uses only moves up to t.

The correction does most of the work that the long window leaves undone. At 99%
the rescaled model is not rejected by any of the three tests and stays green
throughout, peaking at 4 exceptions in a 250-day window against a yellow
threshold of 5. At 95% it is not rejected either: the exception rate falls from
6.98% to 5.10%, Kupiec gives p = 0.82, and independence now passes at p = 0.11
with the statistic down from 37.7 to 2.6. It reaches the yellow zone but never
red.

The reading is that the engine's coverage failures are a volatility-timing
problem rather than a specification problem. Restating the scenario set in
today's volatility units fixes them. What it does not fix is the diversification
ratio, which is a correlation question rather than a scale question: rescaling
every factor by its own volatility leaves the correlation structure of the
window untouched.

### What full revaluation is worth

The rate sleeve was priced twice on identical scenarios: once by discounting the
cashflows again at the shocked yield, once by multiplying by modified duration.

| Year | Full revaluation vs duration | Largest single day |
|---|---|---|
| 2019 | −0.31% | 0.65% |
| 2022 | −0.29% | 0.67% |
| 2024 | −0.29% | 0.56% |

The gap never reaches six tenths of a percent on an annual average, and 1.55%
on the worst single day of the sample. The sign is right (convexity means a long
bond loses less than duration predicts, so the left tail is less bad and VaR is
lower) but the magnitude is small, and it should be said plainly rather than
dressed up. Over a one-day horizon with a daily yield move of about five basis
points, convexity is a second-order term. Full revaluation earns its cost on
instruments whose value is a sharply non-linear function of the factor, which
means options, and on longer horizons and larger shocks. On vanilla bonds at one
day it buys three tenths of a percent.

### Comparison against Goldman's own exception counts

| Year | Model exceptions (95%) | Model days | Model rate | Goldman |
|---|---|---|---|---|
| 2016 | 9 | 233 | 3.9% | 0 |
| 2018 | 11 | 230 | 4.8% | 2 |
| 2020 | 12 | 227 | 5.3% | 2 |
| 2022 | 70 | 230 | 30.4% | 2 |
| 2024 | 11 | 228 | 4.8% | 2 |

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

**Lookback window.** The disclosed five years is the baseline; one, two and
three years are run beside it to measure what the length is worth.

| Window | Mean ratio | Year-to-year std dev | Exception rate | Kupiec p |
|---|---|---|---|---|
| 252 days | 38.2% | 10.23 | 5.58% | 0.209 |
| 502 days | 39.0% | 8.87 | 5.58% | 0.209 |
| 756 days | 39.6% | 8.36 | 5.89% | 0.058 |
| **1,260 days (disclosed)** | **41.6%** | **6.33** | **6.98%** | **<0.0001** |
| *Goldman* | *42.0%* | *2.08* | *0.40%* | |

Lengthening the window moves the result in the right direction on both counts:
the level climbs toward the disclosure and the year-to-year variation falls
from 10.23 to 6.33. It does not arrive. At the disclosed length the ratio still
moves three times as much as Goldman's, and the coverage gets worse, because a
five-year equally weighted scenario set is slow to notice a new regime.

**Scenario age weighting.** This is the sweep that matters. Goldman states that
the importance of its historical data reduces over time, which is the one
methodological detail in the filings that bears directly on how steady a
measured diversification ratio will be. Implementing it, at the disclosed
window, gives:

| Age decay | Half-life | Mean ratio | Year-to-year std dev | Exception rate | Kupiec p |
|---|---|---|---|---|---|
| 1.00 (equal) | — | 41.6% | 6.33 | 6.98% | <0.0001 |
| 0.99 | 69 days | 39.9% | 10.04 | 5.45% | 0.328 |
| 0.97 | 23 days | 42.0% | 9.46 | 5.63% | 0.177 |
| *Goldman* | | *42.0%* | *2.08* | *0.40%* | |

Two things happen at once, and they point in opposite directions.

The weighting fixes the model. Coverage goes from decisively rejected to not
rejected: the exception rate drops from 6.98% to 5.45% and Kupiec's p-value
rises from below 0.0001 to 0.328. At a 23-day half-life the independence test
passes as well (p = 0.305). Weighting toward recent data is the correct
specification for a historical simulation engine, and the filings say so in
plain terms.

And it makes the diversification ratio *less* steady, not more: the year-to-year
standard deviation rises from 6.33 to between 9.46 and 10.04, four to five times
Goldman's 2.08. Faster decay means the effective scenario set turns over faster,
so the correlation structure the engine measures swings more.

That result is the strongest form of the central finding. The gap between the
disclosed steadiness and the reproduced steadiness is not an artifact of this
replication using a cruder method than the bank. Hand the engine the bank's own
disclosed window and the bank's own disclosed weighting, and the gap widens
while the engine becomes a better risk model by every coverage test applied to
it. Whatever holds Goldman's diversification ratio at 42% through this decade
is not in the methodology it discloses.

**Percentile convention.** Linear interpolation and the discrete order statistic
differ by 0.30% of the VaR level, 160 exceptions against 157, and 41.60% against
41.54% on the mean ratio.

**Sleeve signs.** Reported in section 4. Along with the age weighting, this is
the specification choice that moves the headline result, which is why all
sixteen were run rather than sampled.

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
and it understates true rate variability slightly in the 2010-2021 window.

The recalibrated book uses figures published after the year it sizes. That is
appropriate for a structural comparison and would be indefensible for a
forecast, which is why the backtest uses the fixed book only.

The age-decay rate is not disclosed. Two values are run, bracketing a range
that spans half-lives of three weeks to three months, and the direction of the
effect on the diversification ratio is the same at both. The disclosed scheme
is therefore tested in kind but not at Goldman's own rate, which is unknowable
from the filings.

## 8. What the exercise shows

Goldman's methodology description is specific enough to be reimplemented — down
to the five-year window and the decay on older observations — and reimplementing
it on seventeen public factors lands the average diversification benefit within
half a point of theirs. That much transfers.

The steadiness does not, and it does not transfer under the bank's own settings.
Their disclosed ratio moved by 2.08 points a year through a pandemic and a rate
shock. At the disclosed five-year window a static book moves by 6.33, and adding
the disclosed age weighting raises that to between 9.46 and 10.04 — while the
same weighting takes the engine from decisively failing its coverage tests to
passing them. The replication is not losing to Goldman because it uses a blunter
method. It uses Goldman's method, and the steadiness still is not there.

Nor can sleeve direction recover it. Across all sixteen sign configurations the
level and the steadiness trade off against each other: five books are at least
as steady as the disclosure and none of those averages above 35.6%, while eight
average 40% or more and the steadiest of those moves by 3.68 points a year.
Nothing does both.

What is left is what the proxy structurally lacks: a far larger set of
independent risk sources, and exposures that are repositioned daily rather than
held fixed. The filings support the second directly, since Goldman explains its
own year-over-year VaR changes in terms of exposure moves as well as volatility
in four consecutive years.

On the engine itself, the backtest says something a count alone would miss. The
disclosed window run with equal weights fails on count and on arrangement, with
70 breaches in 230 days during 2022 and a fifth of all days in the Basel red
zone. Two different corrections repair it — Goldman's own age weighting, and
Hull-White volatility rescaling, which reaches green at 99% and is rejected by
none of the three tests. Both are cheap. Neither touches the diversification
result, because both change the scale of the scenario set and neither changes
its correlation structure.

## References

Citations, accession numbers and access dates are in
`../references/references.md`. The market risk section of each filing is
preserved verbatim under `../references/sec_filings/`.
