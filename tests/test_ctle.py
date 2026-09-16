import numpy as np

from serdeslink import ctle


def test_dc_gain_matches_setting():
    freq = np.linspace(0, 20e9, 4001)
    h = ctle.ctle_response(freq, dc_gain_db=3.0, zero_hz=1e9, pole1_hz=5e9, pole2_hz=15e9)
    dc_gain_db = 20 * np.log10(np.abs(h[0]))
    assert abs(dc_gain_db - 3.0) < 0.05


def test_peaking_increases_as_zero_moves_lower():
    freq = np.linspace(1e6, 20e9, 4001)
    peaks = []
    for zero_hz in (3e9, 1e9, 0.3e9):
        h = ctle.ctle_response(freq, dc_gain_db=0.0, zero_hz=zero_hz, pole1_hz=5e9, pole2_hz=15e9)
        peaks.append(ctle.peaking_db(freq, h))
    assert peaks[0] < peaks[1] < peaks[2]
