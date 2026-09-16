import numpy as np

from serdeslink import dfe


def test_single_tap_converges_to_known_postcursor():
    rng = np.random.default_rng(0)
    n = 20000
    true_bits = rng.choice([-1.0, 1.0], size=n)
    c1 = 0.3  # single dominant postcursor, as a fraction of main cursor
    samples = true_bits.copy()
    samples[1:] += c1 * true_bits[:-1]

    decisions, taps_history, residual = dfe.run_dfe(samples, n_taps=1, mu=5e-3)

    settled_tap = taps_history[-2000:].mean()
    assert abs(settled_tap - c1) < 0.05

    # decisions should mostly match the transmitted bits once the tap has settled
    agree = np.mean(decisions[-2000:] == true_bits[-2000:])
    assert agree > 0.95


def test_residual_smaller_than_raw_when_isi_present():
    rng = np.random.default_rng(1)
    n = 20000
    true_bits = rng.choice([-1.0, 1.0], size=n)
    c1 = 0.35
    samples = true_bits.copy()
    samples[1:] += c1 * true_bits[:-1]

    decisions, taps_history, residual = dfe.run_dfe(samples, n_taps=1, mu=5e-3)

    raw_spread = samples[-2000:].std()
    residual_spread = residual[-2000:].std()
    assert residual_spread < raw_spread
