import numpy as np
import pytest

from serdeslink.analysis import jitter

RBIT = 5e9
UI_SEC = 1.0 / RBIT
SAMPLES_PER_UI = 32


@pytest.mark.parametrize("ripple_mv", [2.0, 4.0, 6.0, 8.0, 10.0])
def test_psij_eye_closure_matches_kvs_model(ripple_mv):
    """The isolated (no-channel) eye-crossing spread should match the
    injected dt(t) = Kvs * Vn(t) model exactly: peak-to-peak timing jitter
    of 2 * Kvs * ripple_mv, in UI."""
    kvs_ps_per_mv = 5.0
    spreads = jitter.demo_psij_eye_sweep(
        SAMPLES_PER_UI, UI_SEC, [0.0, ripple_mv], ripple_freq_hz=50e6,
        kvs_ps_per_mv=kvs_ps_per_mv, n_bits=3000,
    )
    expected_ui = 2 * kvs_ps_per_mv * ripple_mv * 1e-12 / UI_SEC
    assert spreads[0] == 0.0
    assert abs(spreads[1] - expected_ui) < 0.01


def test_psij_eye_closure_is_monotonic_in_ripple():
    ripple_list = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
    spreads = jitter.demo_psij_eye_sweep(
        SAMPLES_PER_UI, UI_SEC, ripple_list, ripple_freq_hz=50e6,
        kvs_ps_per_mv=5.0, n_bits=3000,
    )
    assert np.all(np.diff(spreads) > 0)


def test_psij_spectrum_shows_spur_below_loop_bandwidth():
    """A ripple frequency well inside the CDR's own loop bandwidth should
    show up as a clear spur in the loop's tracked phase-correction
    spectrum (the loop is chasing the ripple)."""
    ripple_freq_hz = 1e6
    freqs, spectrum, wn_hz, zeta = jitter.demo_psij_spectrum(
        SAMPLES_PER_UI, UI_SEC, ripple_mv=20.0, ripple_freq_hz=ripple_freq_hz,
        kvs_ps_per_mv=5.0, n_bits=8000,
    )
    assert ripple_freq_hz < wn_hz, "test assumes the ripple is below the loop bandwidth"

    peak_idx = int(np.argmax(spectrum[1:])) + 1  # skip the DC bin
    freq_resolution = freqs[1] - freqs[0]
    assert abs(freqs[peak_idx] - ripple_freq_hz) < 3 * freq_resolution

    noise_floor = np.median(spectrum)
    assert spectrum[peak_idx] > 50 * noise_floor
