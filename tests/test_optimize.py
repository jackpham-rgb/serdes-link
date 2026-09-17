import numpy as np

from serdeslink.analysis import optimize


def test_fit_optimal_peaking_recovers_known_parabola():
    true_opt = 10.0
    peaking = np.linspace(2, 20, 10)
    height = -1e-5 * (peaking - true_opt) ** 2 + 0.001

    x_opt, y_opt, coeffs = optimize.fit_optimal_peaking(peaking, height)

    assert x_opt is not None
    assert abs(x_opt - true_opt) < 0.5
    assert abs(y_opt - 0.001) < 1e-6


def test_fit_optimal_peaking_returns_none_when_not_concave():
    peaking = np.linspace(2, 20, 10)
    height = 0.001 + 0.0001 * peaking  # monotonic, no interior maximum

    x_opt, y_opt, coeffs = optimize.fit_optimal_peaking(peaking, height)

    assert x_opt is None
    assert y_opt is None
