"""Backtests for a one-day VaR model.

Three tests, asking three different questions.

Kupiec's proportion-of-failures test asks whether the model breaks as often as
it should. A 95% model should be exceeded on about one day in twenty, and the
test is a likelihood ratio against that binomial null.

Christoffersen's independence test asks whether the breaks arrive
independently. A model can have exactly the right number of exceptions and
still be badly wrong if they all land in the same fortnight, which is what
happens when a volatility regime changes faster than the model does. The two
statistics add to a joint test of conditional coverage.

The Basel traffic light sorts an exception count into a capital-multiplier
zone. The published green, yellow and red boundaries of nought-to-four,
five-to-nine and ten-or-more are specific to a 99% model scored over 250 days,
and carrying them across to a 95% model would be meaningless, since a
well-behaved 95% model is *expected* to produce about twelve exceptions in
250 days and would be in the red zone on day one. The zones are therefore
rederived here from the binomial distribution the committee used to set them,
which reproduces the published numbers at 99% and gives the right ones
elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class TestResult:
    name: str
    statistic: float
    p_value: float
    degrees_of_freedom: int

    def reject_at(self, level: float = 0.05) -> bool:
        return self.p_value < level


def exceptions(pnl: pd.Series, var: pd.Series) -> pd.Series:
    """Days on which the loss was larger than the VaR forecast for that day.

    VaR is a positive loss figure and profit and loss is signed, so an
    exception is a profit and loss below minus VaR. The two series must
    already be aligned so that each VaR is the one struck at the close of the
    previous business day; this function does not shift anything, because a
    shift hidden inside a helper is exactly how look-ahead gets into a
    backtest.
    """
    if not pnl.index.equals(var.index):
        raise ValueError("profit and loss and VaR must share an index")
    return (pnl < -var).astype(int)


def kupiec_pof(breaches: pd.Series, coverage: float = 0.05) -> TestResult:
    """Unconditional coverage: does the model break at the advertised rate?

    With no exceptions at all the observed failure rate is zero and the
    likelihood ratio collapses to -2T ln(1-p), which is finite and large. That
    case is not a numerical accident to be guarded against; it is the test
    correctly reporting that a model which never breaks in a thousand days is
    not a 95% model.
    """
    observations = int(len(breaches))
    failures = int(breaches.sum())
    if observations == 0:
        raise ValueError("no observations to test")

    rate = failures / observations
    log_null = (observations - failures) * np.log1p(-coverage)
    if failures > 0:
        log_null += failures * np.log(coverage)

    if failures == 0:
        log_alt = 0.0
    elif failures == observations:
        log_alt = 0.0
    else:
        log_alt = (observations - failures) * np.log1p(-rate) + failures * np.log(rate)

    statistic = float(-2.0 * (log_null - log_alt))
    return TestResult("kupiec_pof", statistic, float(stats.chi2.sf(statistic, 1)), 1)


def christoffersen_independence(breaches: pd.Series) -> TestResult:
    """Do exceptions cluster, given how many there are?

    Fits a first-order Markov chain to the exception indicator and tests the
    transition probabilities for equality. Undefined when no exception is ever
    followed by anything, so a degenerate sample returns a zero statistic and
    a p-value of one rather than a division by zero.
    """
    values = breaches.to_numpy()
    previous, current = values[:-1], values[1:]

    n00 = int(((previous == 0) & (current == 0)).sum())
    n01 = int(((previous == 0) & (current == 1)).sum())
    n10 = int(((previous == 1) & (current == 0)).sum())
    n11 = int(((previous == 1) & (current == 1)).sum())

    total = n00 + n01 + n10 + n11
    if total == 0 or (n01 + n11) == 0:
        return TestResult("christoffersen_independence", 0.0, 1.0, 1)

    pi = (n01 + n11) / total
    pi_01 = n01 / (n00 + n01) if (n00 + n01) else 0.0
    pi_11 = n11 / (n10 + n11) if (n10 + n11) else 0.0

    log_null = _binomial_loglik(n00 + n10, n01 + n11, pi)
    log_alt = _binomial_loglik(n00, n01, pi_01) + _binomial_loglik(n10, n11, pi_11)

    statistic = float(-2.0 * (log_null - log_alt))
    statistic = max(statistic, 0.0)
    return TestResult("christoffersen_independence", statistic, float(stats.chi2.sf(statistic, 1)), 1)


def conditional_coverage(breaches: pd.Series, coverage: float = 0.05) -> TestResult:
    """Kupiec and Christoffersen combined, on two degrees of freedom."""
    pof = kupiec_pof(breaches, coverage)
    independence = christoffersen_independence(breaches)
    statistic = pof.statistic + independence.statistic
    return TestResult("conditional_coverage", statistic, float(stats.chi2.sf(statistic, 2)), 2)


def _binomial_loglik(zeros: int, ones: int, probability: float) -> float:
    total = 0.0
    if zeros:
        total += zeros * np.log1p(-probability) if probability < 1 else -np.inf
    if ones:
        total += ones * np.log(probability) if probability > 0 else -np.inf
    return float(total)


def basel_zone_bounds(coverage: float, observations: int) -> tuple[int, int]:
    """Exception counts at which the yellow and red zones begin.

    The committee set its boundaries from the cumulative binomial: the yellow
    zone opens at the first count whose cumulative probability under a correct
    model reaches 95%, and the red zone at the first that reaches 99.99%. At a
    1% coverage rate over 250 days this returns 5 and 10, which are the
    published figures, so the derivation can be checked against something
    external rather than taken on trust.
    """
    distribution = stats.binom(observations, coverage)
    counts = np.arange(observations + 1)
    cumulative = distribution.cdf(counts)

    yellow = int(counts[np.argmax(cumulative >= 0.95)])
    red = int(counts[np.argmax(cumulative >= 0.9999)])
    return yellow, red


def basel_zone(failures: int, coverage: float, observations: int) -> str:
    yellow, red = basel_zone_bounds(coverage, observations)
    if failures >= red:
        return "red"
    if failures >= yellow:
        return "yellow"
    return "green"


def rolling_zone(breaches: pd.Series, coverage: float, window: int = 250) -> pd.DataFrame:
    """Traffic-light classification on a rolling window, as a supervisor sees it."""
    counts = breaches.rolling(window).sum()
    yellow, red = basel_zone_bounds(coverage, window)

    zones = pd.Series(pd.NA, index=breaches.index, dtype="object")
    valid = counts.notna()
    zones[valid & (counts < yellow)] = "green"
    zones[valid & (counts >= yellow) & (counts < red)] = "yellow"
    zones[valid & (counts >= red)] = "red"

    return pd.DataFrame({"exceptions_in_window": counts, "zone": zones})


def summary(pnl: pd.Series, var: pd.Series, coverage: float = 0.05) -> dict[str, object]:
    """Everything the report needs about one model on one sample."""
    breaches = exceptions(pnl, var)
    observations = int(len(breaches))
    failures = int(breaches.sum())

    pof = kupiec_pof(breaches, coverage)
    independence = christoffersen_independence(breaches)
    joint = conditional_coverage(breaches, coverage)
    yellow, red = basel_zone_bounds(coverage, min(250, observations))

    # Reporting only the final 250-day window would describe whichever market
    # the sample happens to end in. A supervisor sees the classification every
    # day, so what matters is the worst one reached and how long it was held.
    rolling = rolling_zone(breaches, coverage)
    observed = rolling["zone"].dropna()
    severity = {"green": 0, "yellow": 1, "red": 2}
    worst = max(observed, key=lambda z: severity[z]) if len(observed) else None
    shares = {
        f"days_{zone}_pct": float((observed == zone).mean() * 100.0) if len(observed) else float("nan")
        for zone in ("green", "yellow", "red")
    }

    return {
        "basel_worst_zone": worst,
        "basel_peak_window_exceptions": float(rolling["exceptions_in_window"].max()),
        **shares,
        "observations": observations,
        "exceptions": failures,
        "exception_rate_pct": failures / observations * 100.0,
        "expected_rate_pct": coverage * 100.0,
        "expected_exceptions": coverage * observations,
        "kupiec_statistic": pof.statistic,
        "kupiec_p_value": pof.p_value,
        "kupiec_rejects_5pct": pof.reject_at(),
        "independence_statistic": independence.statistic,
        "independence_p_value": independence.p_value,
        "independence_rejects_5pct": independence.reject_at(),
        "conditional_coverage_statistic": joint.statistic,
        "conditional_coverage_p_value": joint.p_value,
        "basel_zone_250d": basel_zone(
            int(breaches.tail(250).sum()), coverage, min(250, observations)
        ),
        "basel_yellow_at": yellow,
        "basel_red_at": red,
        "worst_loss": float(pnl.min()),
        "largest_exception_multiple": float(
            (-pnl / var)[breaches == 1].max() if failures else np.nan
        ),
    }
