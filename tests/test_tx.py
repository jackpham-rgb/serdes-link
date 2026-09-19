import numpy as np

from serdeslink import tx


def test_apply_supply_jitter_is_identity_at_zero_ripple():
    rng = np.random.default_rng(0)
    waveform = rng.standard_normal(2000)
    out = tx.apply_supply_jitter(waveform, samples_per_ui=32, ui_sec=200e-12,
                                  kvs_ps_per_mv=5.0, ripple_mv=0.0, ripple_freq_hz=100e6)
    assert np.array_equal(out, waveform)


def test_apply_supply_jitter_matches_hand_computed_time_warp():
    samples_per_ui, ui_sec = 32, 200e-12
    n = 5000
    dt_sample = ui_sec / samples_per_ui
    t = np.arange(n) * dt_sample
    signal = np.sin(2 * np.pi * 50e6 * t)

    kvs, ripple_mv, ripple_freq_hz = 8.0, 3.0, 20e6
    out = tx.apply_supply_jitter(signal, samples_per_ui, ui_sec, kvs, ripple_mv, ripple_freq_hz)

    vn = ripple_mv * np.sin(2 * np.pi * ripple_freq_hz * t)
    dt_shift = kvs * 1e-12 * vn
    expected = np.interp(t - dt_shift, t, signal)

    assert np.allclose(out, expected)
