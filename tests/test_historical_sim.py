"""Engine checks: percentile logic, sign conventions, scaling, and timing.

The timing test is the one that matters most. Every other failure mode in a
VaR engine announces itself as an implausible number; look-ahead announces
itself as an unusually good backtest, which is easy to mistake for success.
"""

import numpy as np
import pandas as pd
import pytest

from gsvar import book
from gsvar import historical_sim as hs


def constant_frame(values, columns, start="2020-01-01"):
    index = pd.bdate_range(start, periods=len(values))
    return pd.DataFrame({column: values for column in columns}, index=index)


def test_percentile_on_a_hand_built_scenario_set():
    """Twenty scenarios, so the 5% point is the single worst one.

    Losses of 1 through 20 against a position of one unit: the ordered profit
    and loss is -20 up to -1, and the 5% quantile of twenty points sits exactly
    on the worst. Both conventions have to agree here, which is what makes
    this a usable anchor.
    """
    pnl = -np.arange(1, 21, dtype=float)
    interpolated = hs.var_from_scenarios(pnl, hs.Settings(quantile=0.05, interpolate=True))
    discrete = hs.var_from_scenarios(pnl, hs.Settings(quantile=0.05, interpolate=False))
    assert interpolated == pytest.approx(19.05)
    assert discrete == pytest.approx(20.0)


def test_var_is_reported_as_a_positive_loss():
    pnl = np.array([-5.0, -3.0, 1.0, 2.0, 4.0])
    assert hs.var_from_scenarios(pnl, hs.Settings(quantile=0.2)) > 0


def test_discrete_convention_is_never_less_conservative():
    rng = np.random.default_rng(11)
    for _ in range(50):
        pnl = rng.normal(size=502)
        settings_in = hs.Settings(interpolate=True)
        settings_out = hs.Settings(interpolate=False)
        assert hs.var_from_scenarios(pnl, settings_out) >= hs.var_from_scenarios(pnl, settings_in) - 1e-12


def toy_inputs(days=600, seed=3):
    rng = np.random.default_rng(seed)
    columns = ["equity_us", "fx_eurusd", "commodity_gold", "us_10y"]
    index = pd.bdate_range("2018-01-01", periods=days)
    moves = pd.DataFrame(
        {
            "equity_us": rng.normal(0, 0.01, days),
            "fx_eurusd": rng.normal(0, 0.005, days),
            "commodity_gold": rng.normal(0, 0.009, days),
            "us_10y": rng.normal(0, 0.05, days),
        },
        index=index,
    )
    levels = pd.DataFrame(
        {c: np.full(days, 100.0 if c != "us_10y" else 3.0) for c in columns}, index=index
    )
    positions = [
        book.Position("equity_us", "equity_prices", book.LINEAR, 100.0),
        book.Position("fx_eurusd", "currency_rates", book.LINEAR, 100.0),
        book.Position("commodity_gold", "commodity_prices", book.LINEAR, 100.0),
        book.Position("us_10y", "interest_rates", book.PAR_BOND, 100.0, 10.0),
    ]
    return positions, moves, levels


def test_diversification_effect_is_never_positive():
    """Four sleeves summed cannot be smaller than the book that holds them.

    Adding standalone VaRs assumes the categories lose together. A simulation
    that lets them move as they actually did can only do better, so the
    difference has to come out negative or zero.
    """
    positions, moves, levels = toy_inputs()
    result = hs.run(positions, moves, levels, hs.Settings(window=250))
    assert (result["diversification_effect"] <= 1e-9).all()
    assert (result["var_total"] <= result["sum_category_var"] + 1e-9).all()


def test_perfectly_correlated_sleeves_leave_nothing_to_diversify():
    """One factor driving every sleeve should collapse the effect to zero."""
    days = 400
    index = pd.bdate_range("2019-01-01", periods=days)
    rng = np.random.default_rng(7)
    shared = rng.normal(0, 0.01, days)
    moves = pd.DataFrame({name: shared for name in "abcd"}, index=index)
    levels = pd.DataFrame({name: np.full(days, 50.0) for name in "abcd"}, index=index)
    positions = [
        book.Position("a", "interest_rates", book.LINEAR, 100.0),
        book.Position("b", "equity_prices", book.LINEAR, 100.0),
        book.Position("c", "currency_rates", book.LINEAR, 100.0),
        book.Position("d", "commodity_prices", book.LINEAR, 100.0),
    ]
    result = hs.run(positions, moves, levels, hs.Settings(window=250))
    relative = (result["diversification_effect"] / result["sum_category_var"]).abs()
    assert relative.max() < 1e-9


def test_var_scales_exactly_with_notional():
    """The calibration divides once instead of searching, and relies on this."""
    positions, moves, levels = toy_inputs()
    settings = hs.Settings(window=250)
    base = hs.run(positions, moves, levels, settings)
    doubled = hs.run([p.scaled(2.0) for p in positions], moves, levels, settings)
    assert doubled["var_total"].to_numpy() == pytest.approx(
        2.0 * base["var_total"].to_numpy(), rel=1e-12
    )


def test_var_does_not_depend_on_anything_after_its_own_date():
    """Rewrite the future and the past must not move.

    Every move after a cut-off is replaced with an extreme value. VaR stamped
    on or before the cut-off has to be identical to what it was, because it is
    only allowed to see scenarios up to its own date. The realised profit and
    loss column is excluded from the comparison, since that one is supposed to
    change: it is the next day's outcome.
    """
    positions, moves, levels = toy_inputs(days=700)
    settings = hs.Settings(window=250)

    cutoff = moves.index[500]
    tampered = moves.copy()
    tampered.loc[tampered.index > cutoff] *= 25.0

    original = hs.run(positions, moves, levels, settings)
    altered = hs.run(positions, tampered, levels, settings)

    columns = [c for c in original.columns if c not in ("realised_pnl_next", "pnl_date")]
    before = original.loc[:cutoff, columns]
    after = altered.loc[:cutoff, columns]
    pd.testing.assert_frame_equal(before, after)


def test_realised_pnl_is_the_next_days_move_not_todays():
    """Guards the off-by-one that would make the backtest meaningless."""
    positions, moves, levels = toy_inputs(days=400)
    settings = hs.Settings(window=250)
    result = hs.run(positions, moves, levels, settings)

    date = result.index[10]
    following = moves.index[moves.index.get_loc(date) + 1]
    assert result.loc[date, "pnl_date"] == following

    expected = sum(
        p.notional * book.scenario_returns(p, moves.loc[[following]], levels.loc[date])[0]
        for p in positions
    )
    assert result.loc[date, "realised_pnl_next"] == pytest.approx(expected, rel=1e-12)


def test_a_book_that_does_not_use_every_category_still_runs():
    """A sleeve with no positions has zero VaR, which is not an error."""
    _, moves, levels = toy_inputs(days=400)
    positions = [book.Position("equity_us", "equity_prices", book.LINEAR, 100.0)]
    result = hs.run(positions, moves, levels, hs.Settings(window=250))
    assert (result["var_equity_prices"] > 0).all()
    assert (result["var_interest_rates"] == 0).all()
    assert result["var_total"].equals(result["var_equity_prices"])


def synthetic_result(positive_days: int, total_days: int = 500) -> pd.DataFrame:
    index = pd.bdate_range("2019-01-01", periods=total_days)
    frame = pd.DataFrame(
        {f"var_{category}": 10.0 for category in hs.CATEGORIES}, index=index
    )
    frame["sum_category_var"] = 40.0
    frame["var_total"] = 30.0
    frame.iloc[:positive_days, frame.columns.get_loc("var_total")] = 45.0
    frame["diversification_effect"] = frame["var_total"] - frame["sum_category_var"]
    return frame


def test_the_subadditivity_guard_allows_a_few_days_and_rejects_many():
    """A handful of positive days is the measure; a flood of them is a bug.

    Driving this through the engine would need positions with jump risk,
    which this instrument set cannot express, so the guard is exercised on a
    constructed result instead. Everything up to the one-in-a-hundred
    threshold passes; past it the run is refused.
    """
    populated = set(hs.CATEGORIES)
    hs._check(synthetic_result(positive_days=4), populated)

    with pytest.raises(ValueError, match="sign error"):
        hs._check(synthetic_result(positive_days=60), populated)


def test_real_runs_record_how_many_days_had_no_diversification_benefit():
    positions, moves, levels = toy_inputs()
    result = hs.run(positions, moves, levels, hs.Settings(window=250))
    assert result.attrs["days_without_diversification_benefit"] == 0


def test_window_longer_than_the_sample_is_refused():
    positions, moves, levels = toy_inputs(days=100)
    with pytest.raises(ValueError):
        hs.run(positions, moves, levels, hs.Settings(window=500))


def test_age_weights_normalise_and_favour_recent_scenarios():
    """Newest last, monotone in recency, summing to one."""
    weights = hs.age_weights(5, decay=0.9)
    assert weights.sum() == pytest.approx(1.0)
    assert np.all(np.diff(weights) > 0)  # oldest first, so weight rises
    # The newest scenario should outweigh the oldest by decay**(n-1).
    assert weights[0] / weights[-1] == pytest.approx(0.9**4)
    assert hs.age_weights(5, decay=1.0) == pytest.approx(np.full(5, 0.2))


@pytest.mark.parametrize("quantile", [0.01, 0.05, 0.10, 0.25])
@pytest.mark.parametrize("count", [20, 100, 251, 502])
def test_equal_weights_reproduce_the_unweighted_percentile(count, quantile):
    """The weighted estimator must collapse onto the unweighted one.

    This is the test that makes the age-weighted runs interpretable. If the
    two paths disagreed at equal weights, any difference between a weighted
    and an unweighted run would mix the weighting with a change of estimator,
    and the comparison the paper rests on would not be clean.
    """
    rng = np.random.default_rng(count * 1000 + int(quantile * 100))
    pnl = rng.standard_normal(count) * 3.0 - 0.1

    for interpolate in (True, False):
        settings = hs.Settings(
            window=count, quantile=quantile, interpolate=interpolate, age_decay=1.0
        )
        plain = hs.var_from_scenarios(pnl, settings)
        weighted = hs.var_from_scenarios(
            pnl, settings, hs.age_weights(count, decay=1.0)
        )
        assert weighted == pytest.approx(plain, rel=0, abs=1e-12)


def test_age_weighting_responds_to_where_the_loss_sits_in_the_window():
    """Same scenario set, one extreme loss moved from old to recent.

    Age weighting should raise VaR when the bad day is recent and lower it
    when the bad day is stale. A test on the level alone would pass for an
    estimator that ignored the ordering entirely, so the ordering is what is
    asserted here.
    """
    calm = -np.ones(99, dtype=float)
    stale = np.concatenate([[-50.0], calm])  # worst day is the oldest
    recent = np.concatenate([calm, [-50.0]])  # worst day is the newest

    # The quantile has to sit above the newest scenario's own weight for its
    # position in the window to bite at all: at 0.97 over 100 days the newest
    # day carries about 3.1% of the mass, so a 5% tail swallows it either way.
    settings = hs.Settings(window=100, quantile=0.02, age_decay=0.97)
    weights = hs.age_weights(100, decay=0.97)

    var_stale = hs.var_from_scenarios(stale, settings, weights)
    var_recent = hs.var_from_scenarios(recent, settings, weights)
    assert var_recent > var_stale

    # Unweighted, the position of the bad day is irrelevant.
    flat = hs.Settings(window=100, quantile=0.02)
    assert hs.var_from_scenarios(stale, flat) == pytest.approx(
        hs.var_from_scenarios(recent, flat)
    )


def test_engine_accepts_the_disclosed_window_and_weighting_together():
    """A smoke test that the two disclosed settings compose in `run`."""
    columns = ["equity_us"]
    rng = np.random.default_rng(7)
    moves = pd.DataFrame(
        rng.standard_normal(400) * 0.01,
        index=pd.bdate_range("2019-01-01", periods=400),
        columns=columns,
    )
    levels = pd.DataFrame(1.0, index=moves.index, columns=columns)
    positions = [book.Position("equity_us", "equity_prices", book.LINEAR, 1_000_000.0)]

    settings = hs.Settings(window=252, quantile=0.05, age_decay=0.97)
    frame = hs.run(positions, moves, levels, settings)
    assert len(frame) == 400 - 252  # one date lost to the next-day result
    assert (frame["var_equity_prices"] > 0).all()
