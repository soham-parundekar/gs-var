"""Position sizing and the volatility estimators used by the Hull-White variant."""

import numpy as np
import pandas as pd
import pytest

from gsvar import book, volatility
from gsvar import historical_sim as hs


def toy_inputs(days=600, seed=5):
    rng = np.random.default_rng(seed)
    index = pd.bdate_range("2018-01-01", periods=days)
    moves = pd.DataFrame(
        {
            "equity_us": rng.normal(0, 0.012, days),
            "equity_japan": rng.normal(0, 0.015, days),
            "fx_eurusd": rng.normal(0, 0.005, days),
            "commodity_gold": rng.normal(0, 0.010, days),
            "us_2y": rng.normal(0, 0.04, days),
            "us_30y": rng.normal(0, 0.05, days),
        },
        index=index,
    )
    levels = pd.DataFrame(
        {c: np.full(days, 3.0 if c.startswith("us_") else 100.0) for c in moves.columns},
        index=index,
    )
    positions = [
        book.Position("equity_us", "equity_prices", book.LINEAR, 1.0),
        book.Position("equity_japan", "equity_prices", book.LINEAR, 1.0),
        book.Position("fx_eurusd", "currency_rates", book.LINEAR, 1.0),
        book.Position("commodity_gold", "commodity_prices", book.LINEAR, 1.0),
        book.Position("us_2y", "interest_rates", book.PAR_BOND, 1.0, 2.0),
        book.Position("us_30y", "interest_rates", book.PAR_BOND, 1.0, 30.0),
    ]
    return positions, moves, levels


def test_equal_risk_weighting_equalises_standalone_risk():
    """A thirty-year bond must end up far smaller than a two-year note."""
    positions, moves, levels = toy_inputs()
    weighted = book.equal_risk_weights(positions, moves, levels, window=250, quantile=0.05)

    window = moves.iloc[-250:]
    base = levels.loc[window.index[-1]]
    risks = [
        -np.percentile(p.notional * book.scenario_returns(p, window, base), 5) for p in weighted
    ]
    assert np.allclose(risks, risks[0], rtol=1e-9)

    sized = {p.factor: p.notional for p in weighted}
    assert sized["us_2y"] > 5 * sized["us_30y"]


def test_rescaling_lands_exactly_on_the_targets():
    positions, moves, levels = toy_inputs()
    settings = hs.Settings(window=250)
    weighted = book.equal_risk_weights(positions, moves, levels, settings.window, settings.quantile)

    trial = hs.run(weighted, moves, levels, settings)
    realised = pd.Series({c: trial[f"var_{c}"].mean() for c in book.CATEGORIES})
    targets = pd.Series(
        {"interest_rates": 46.0, "equity_prices": 27.0, "currency_rates": 11.0, "commodity_prices": 12.0}
    )

    sized = book.rescale_to_targets(weighted, realised, targets)
    achieved = hs.run(sized, moves, levels, settings)
    for category, target in targets.items():
        assert achieved[f"var_{category}"].mean() == pytest.approx(target, rel=1e-10)


def test_sign_variants_cover_the_whole_space_and_leave_sleeve_risk_alone():
    positions, moves, levels = toy_inputs()
    variants = book.sign_variants(positions)
    assert len(variants) == 16
    assert "++++" in variants and "----" in variants

    settings = hs.Settings(window=250)
    longs = hs.run(variants["++++"], moves, levels, settings)
    flipped = hs.run(variants["+-++"], moves, levels, settings)

    # Flipping one sleeve leaves the other sleeves' standalone VaR untouched.
    for category in ("interest_rates", "currency_rates", "commodity_prices"):
        assert longs[f"var_{category}"].equals(flipped[f"var_{category}"])


def test_ewma_forecast_uses_only_past_information():
    """Change tomorrow and today's forecast must not move."""
    _, moves, _ = toy_inputs(days=500)
    cutoff = moves.index[300]

    tampered = moves.copy()
    tampered.loc[tampered.index > cutoff] *= 30.0

    original = volatility.ewma_forecast(moves)
    altered = volatility.ewma_forecast(tampered)
    pd.testing.assert_frame_equal(original.loc[:cutoff], altered.loc[:cutoff])


def test_ewma_responds_to_a_volatility_jump_within_a_few_weeks():
    index = pd.bdate_range("2020-01-01", periods=600)
    series = np.concatenate([np.full(400, 0.005), np.full(200, 0.05)])
    rng = np.random.default_rng(1)
    moves = pd.DataFrame({"x": rng.normal(0, 1, 600) * series}, index=index)

    forecast = volatility.ewma_forecast(moves)["x"]
    calm = forecast.iloc[380]
    after = forecast.iloc[430]  # about six weeks past the jump
    assert after > 4 * calm


def test_rescaling_scenarios_restates_them_in_todays_volatility():
    index = pd.bdate_range("2021-01-01", periods=5)
    window = pd.DataFrame({"x": [0.01, -0.02, 0.03, -0.01, 0.02]}, index=index)
    applied = pd.DataFrame({"x": [0.01] * 5}, index=index)
    current = pd.Series({"x": 0.02})

    scaled = volatility.rescaled_scenarios(window, applied, current)
    assert scaled["x"].to_numpy() == pytest.approx(window["x"].to_numpy() * 2.0)


def test_missing_volatility_over_the_window_is_an_error_not_a_silent_nan():
    index = pd.bdate_range("2021-01-01", periods=3)
    window = pd.DataFrame({"x": [0.01, 0.02, 0.03]}, index=index)
    applied = pd.DataFrame({"x": [0.01, np.nan, 0.01]}, index=index)
    with pytest.raises(ValueError):
        volatility.rescaled_scenarios(window, applied, pd.Series({"x": 0.02}))
