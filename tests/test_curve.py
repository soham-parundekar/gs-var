"""Bond pricing checks against values worked out by hand.

A pricing error here would not raise anything. It would produce a plausible
VaR that is simply wrong, which is why these compare against arithmetic done
outside the module rather than against the module's own output.
"""

import numpy as np
import pytest

from gsvar import curve


@pytest.mark.parametrize("yield_pct", [-0.40, 0.5, 2.0, 4.25, 6.0])
@pytest.mark.parametrize("maturity", [2, 5, 10, 30])
def test_par_bond_prices_to_par_at_its_own_yield(yield_pct, maturity):
    assert curve.price_par_bond(yield_pct, yield_pct, maturity) == pytest.approx(100.0, abs=1e-9)


def test_coupon_bond_matches_hand_calculation():
    # 10 years, 5% semiannual coupon, 6% yield: twenty periods of 2.5 at 3%.
    # Computed to thirty significant figures with the decimal module, the
    # price is 92.5612625697722..., so the bond trades below par because its
    # coupon is a point under its yield.
    assert curve.price_par_bond(5.0, 6.0, 10) == pytest.approx(92.5612626, abs=1e-7)


def test_zero_matches_hand_calculation():
    assert curve.price_zero(3.0, 10) == pytest.approx(100.0 / 1.03**10, abs=1e-12)


@pytest.mark.parametrize("yield_pct", [1.0, 4.0, 7.0])
@pytest.mark.parametrize("maturity", [2, 10, 30])
def test_modified_duration_matches_numerical_derivative(yield_pct, maturity):
    analytic = curve.modified_duration_par_bond(yield_pct, maturity)
    step = 1e-5
    up = curve.price_par_bond(yield_pct, yield_pct + step, maturity)
    down = curve.price_par_bond(yield_pct, yield_pct - step, maturity)
    numerical = -(up - down) / (2 * step)  # price starts at 100, so this is already modified duration
    assert analytic == pytest.approx(numerical, abs=1e-5)


@pytest.mark.parametrize("shock", [0.25, 1.0, 4.0])
def test_convexity_has_the_right_sign_in_both_directions(shock):
    """A long bond loses less than duration says and gains more than it says."""
    for signed in (shock, -shock):
        full = curve.par_bond_return(4.0, signed, 10)
        linear = curve.duration_approximation_return(4.0, signed, 10)
        assert full > linear


def test_vectorised_pricing_matches_the_scalar_version():
    shocks = np.array([-0.57, -0.1, 0.0, 0.07, 0.34])
    vectorised = curve.par_bond_return_vector(3.8, shocks, 10)
    scalar = [curve.par_bond_return(3.8, s, 10) for s in shocks]
    assert vectorised == pytest.approx(scalar, abs=1e-14)

    vectorised_zero = curve.zero_bond_return_vector(-0.4, shocks, 5)
    scalar_zero = [curve.zero_bond_return(-0.4, s, 5) for s in shocks]
    assert vectorised_zero == pytest.approx(scalar_zero, abs=1e-14)


def test_negative_yields_are_priced_not_rejected():
    """The euro curve was below zero for years; that is data, not an error."""
    assert curve.price_zero(-0.40, 5) > 100.0
    assert curve.zero_bond_return(-0.40, 0.25, 5) < 0.0


def test_discount_factor_blowing_up_is_refused():
    with pytest.raises(ValueError):
        curve.price_zero(-120.0, 5)


def test_a_zero_has_longer_duration_than_a_par_bond_of_the_same_maturity():
    par = curve.modified_duration_par_bond(3.0, 10)
    zero = 10 / 1.03
    assert zero > par
