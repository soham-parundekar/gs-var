"""Backtest statistics checked against published values and analytic limits.

The Kupiec cases come from MathWorks' documented `varbacktest.pof` outputs,
which is an implementation independent of this one. The Basel bounds are
checked against the boundaries the Basel Committee published in 1996, which
this module rederives from the binomial rather than hard-coding.
"""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from gsvar import backtest as bt


def indicator(failures: int, observations: int) -> pd.Series:
    return pd.Series([1] * failures + [0] * (observations - failures))


@pytest.mark.parametrize(
    "observations,failures,coverage,statistic,p_value",
    [
        (1043, 57, 0.05, 0.46147, 0.49694),
        (1043, 17, 0.01, 3.51180, 0.060933),
    ],
)
def test_kupiec_matches_an_independent_implementation(
    observations, failures, coverage, statistic, p_value
):
    result = bt.kupiec_pof(indicator(failures, observations), coverage)
    assert result.statistic == pytest.approx(statistic, abs=1e-4)
    assert result.p_value == pytest.approx(p_value, abs=1e-5)


def test_kupiec_is_zero_when_the_rate_is_exactly_right():
    assert bt.kupiec_pof(indicator(50, 1000), 0.05).statistic == pytest.approx(0.0, abs=1e-12)


def test_kupiec_with_no_exceptions_takes_its_analytic_value():
    """A model that never breaks is still testable, and still rejected."""
    result = bt.kupiec_pof(indicator(0, 1000), 0.05)
    assert result.statistic == pytest.approx(-2 * 1000 * np.log(0.95), abs=1e-9)
    assert result.p_value < 1e-10


def test_kupiec_rejects_in_both_directions():
    assert bt.kupiec_pof(indicator(5, 1000), 0.05).reject_at(0.05)
    assert bt.kupiec_pof(indicator(200, 1000), 0.05).reject_at(0.05)
    assert not bt.kupiec_pof(indicator(48, 1000), 0.05).reject_at(0.05)


def test_basel_bounds_reproduce_the_published_zones():
    """Yellow at five and red at ten, for a 99% model over 250 days."""
    assert bt.basel_zone_bounds(0.01, 250) == (5, 10)
    assert bt.basel_zone(4, 0.01, 250) == "green"
    assert bt.basel_zone(5, 0.01, 250) == "yellow"
    assert bt.basel_zone(10, 0.01, 250) == "red"


def test_basel_bounds_move_with_the_confidence_level():
    """A 95% model is expected to break far more often, so the zones shift.

    Carrying the published 99% boundaries across to a 95% model would put a
    correctly calibrated model in the red zone, which is the mistake this
    rederivation exists to avoid.
    """
    yellow, red = bt.basel_zone_bounds(0.05, 250)
    assert yellow > 5 and red > 10
    assert bt.basel_zone(12, 0.05, 250) == "green"


def test_independence_catches_clustering_the_coverage_test_misses():
    """Same number of exceptions, opposite verdicts."""
    clustered = pd.Series([0] * 500 + [1] * 10 + [0] * 490)
    spread = pd.Series(([0] * 99 + [1]) * 10)

    assert bt.kupiec_pof(clustered, 0.01).statistic == pytest.approx(0.0, abs=1e-9)
    assert bt.kupiec_pof(spread, 0.01).statistic == pytest.approx(0.0, abs=1e-9)

    assert bt.christoffersen_independence(clustered).reject_at(0.01)
    assert not bt.christoffersen_independence(spread).reject_at(0.05)


def test_independence_is_defined_when_there_are_no_exceptions():
    result = bt.christoffersen_independence(pd.Series([0] * 500))
    assert result.statistic == 0.0
    assert result.p_value == 1.0


def test_conditional_coverage_is_the_sum_on_two_degrees_of_freedom():
    breaches = pd.Series([0] * 480 + [1] * 20)
    joint = bt.conditional_coverage(breaches, 0.05)
    parts = bt.kupiec_pof(breaches, 0.05).statistic + bt.christoffersen_independence(breaches).statistic
    assert joint.statistic == pytest.approx(parts)
    assert joint.degrees_of_freedom == 2


def test_exceptions_require_aligned_inputs():
    pnl = pd.Series([1.0, -2.0], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    var = pd.Series([1.0, 1.0], index=pd.to_datetime(["2020-01-02", "2020-01-03"]))
    with pytest.raises(ValueError):
        bt.exceptions(pnl, var)


def test_an_exception_is_a_loss_larger_than_var():
    index = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    pnl = pd.Series([-0.9, -1.1, 5.0], index=index)
    var = pd.Series([1.0, 1.0, 1.0], index=index)
    assert bt.exceptions(pnl, var).tolist() == [0, 1, 0]


def test_kupiec_statistic_has_roughly_the_right_size_under_the_null():
    """A correctly specified model should be rejected about 5% of the time.

    The statistic is discrete, so its distribution cannot match a continuous
    chi-square exactly and a goodness-of-fit test on the whole distribution
    would fail for the wrong reason. Size at the nominal level is the
    property that actually matters.
    """
    rng = np.random.default_rng(20260109)
    critical = stats.chi2.ppf(0.95, 1)
    rejections = sum(
        bt.kupiec_pof(pd.Series((rng.random(1000) < 0.05).astype(int)), 0.05).statistic > critical
        for _ in range(1500)
    )
    assert 0.03 < rejections / 1500 < 0.08
