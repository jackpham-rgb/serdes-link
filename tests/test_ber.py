import numpy as np

from serdeslink.analysis import ber


def test_optimal_threshold_is_zero_for_symmetric_channel():
    t = ber.optimal_threshold(-1.0, 1.0, 1.0, 1.0)
    assert abs(t) < 1e-12


def test_optimal_threshold_shifts_under_asymmetric_levels():
    """Duty-cycle-distortion-like case: equal noise, but the '0' level
    isn't the exact mirror of the '1' level. With equal variance the
    likelihood-ratio threshold has an exact closed form: the weighted
    midpoint (mu0+mu1)/2."""
    mu0, mu1, sigma = -0.7, 1.0, 0.2
    t = ber.optimal_threshold(mu0, sigma, mu1, sigma)
    assert abs(t - (mu0 + mu1) / 2) < 1e-9
    assert t != 0.0


def test_optimal_threshold_beats_naive_zero_under_heteroscedastic_noise():
    """When the two hypotheses have different noise sigma (even with
    symmetric +-1 means), threshold=0 is no longer optimal: the derived
    threshold must give a strictly lower total error probability."""
    mu0, sigma0, mu1, sigma1 = -1.0, 0.1, 1.0, 0.5
    t_opt = ber.optimal_threshold(mu0, sigma0, mu1, sigma1)
    assert t_opt != 0.0

    err_opt = ber.error_probability(t_opt, mu0, sigma0, mu1, sigma1)
    err_naive = ber.error_probability(0.0, mu0, sigma0, mu1, sigma1)
    assert err_opt < err_naive


def test_optimal_threshold_matches_grid_search():
    """Cross-check optimal_threshold against a brute-force grid search over
    error_probability, for a case with both asymmetric levels AND
    asymmetric noise (no closed form applies)."""
    mu0, sigma0, mu1, sigma1 = -0.6, 0.15, 0.9, 0.4
    t_opt = ber.optimal_threshold(mu0, sigma0, mu1, sigma1)

    grid = np.linspace(mu0, mu1, 20001)
    errs = [ber.error_probability(t, mu0, sigma0, mu1, sigma1) for t in grid]
    t_grid = grid[int(np.argmin(errs))]

    assert abs(t_opt - t_grid) < 1e-2
    assert ber.error_probability(t_opt, mu0, sigma0, mu1, sigma1) <= min(errs) + 1e-9


def test_error_probability_matches_bathtub_in_symmetric_case():
    """error_probability at threshold=0 for a symmetric channel should
    match bathtub()'s existing Q-function BER at the same threshold (the
    two are the same computation, just parameterized differently: bathtub
    works from ISI cursors, error_probability from a hypothesis's mean and
    sigma directly)."""
    sigma_rj = 0.05
    thresholds, ber_high, _ = ber.bathtub([], sigma_rj, thresholds=np.array([0.0]))
    bathtub_ber_at_zero = ber_high[0]

    generalized = ber.error_probability(0.0, -1.0, sigma_rj, 1.0, sigma_rj)
    assert abs(bathtub_ber_at_zero - generalized) < 1e-9
