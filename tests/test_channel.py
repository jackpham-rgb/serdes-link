import numpy as np
import pytest
import skrf as rf

from serdeslink import channel


def _make_two_uncoupled_lines_s4p(tmp_path, length_m=0.05):
    """Build the same block-diagonal 4-port construction as
    data/touchstone/make_synthetic_channel.py, but short and fast, purely for
    testing channel.load()'s mixed-mode extraction against a known input."""
    freq = rf.Frequency(0.05, 15, 301, unit="GHz")
    media = rf.media.MLine(frequency=freq, z0=50, w=0.127e-3, h=0.127e-3,
                            t=0.035e-3, ep_r=4.3, rho=1.7e-8, tand=0.02,
                            model="hammerstadjensen", diel="frequencyinvariant")
    line = media.line(length_m, unit="m", name="line")
    s2 = line.s
    n = s2.shape[0]
    s4 = np.zeros((n, 4, 4), dtype=complex)
    # se2gmm(p=2) native order: (port0=TX+, port1=TX-, port2=RX+, port3=RX-)
    s4[:, 0, 0] = s2[:, 0, 0]
    s4[:, 0, 2] = s2[:, 0, 1]
    s4[:, 2, 0] = s2[:, 1, 0]
    s4[:, 2, 2] = s2[:, 1, 1]

    s4[:, 1, 1] = s2[:, 0, 0]
    s4[:, 1, 3] = s2[:, 0, 1]
    s4[:, 3, 1] = s2[:, 1, 0]
    s4[:, 3, 3] = s2[:, 1, 1]
    ntwk = rf.Network(frequency=freq, s=s4, z0=50)
    path = tmp_path / "test_channel.s4p"
    ntwk.write_touchstone(str(path), form="ri")
    return str(path), line


def test_sdd21_matches_single_ended_line(tmp_path):
    """For two IDENTICAL, UNCOUPLED single-ended lines, the differential
    transfer function SDD21 must equal the single line's S21 — this is a
    white-box check that se2gmm + our port-map assumption in channel.load()
    are wired correctly."""
    path, line = _make_two_uncoupled_lines_s4p(tmp_path)
    t, h, freq, sdd21 = channel.load(path)

    expected_s21 = np.interp(freq, line.f, np.abs(line.s[:, 1, 0]))
    np.testing.assert_allclose(np.abs(sdd21), expected_s21, rtol=0.05, atol=1e-3)


def test_impulse_response_is_real_and_causal(tmp_path):
    path, _ = _make_two_uncoupled_lines_s4p(tmp_path)
    t, h, freq, sdd21 = channel.load(path)
    assert np.isrealobj(h)
    frac = channel.causality_energy_fraction(h)
    assert frac < 0.05


def test_pulse_response_and_cursors(tmp_path):
    path, _ = _make_two_uncoupled_lines_s4p(tmp_path)
    t, h, freq, sdd21 = channel.load(path)
    dt = t[1] - t[0]
    ui_sec = 200e-12  # 5 Gb/s
    p = channel.pulse_response(h, dt, ui_sec)
    main, isi = channel.cursor_amplitudes(p, dt, ui_sec)
    assert main > 0
    # a lossy-but-not-crazy 2" line shouldn't produce ISI cursors bigger than the main cursor
    assert all(abs(c) < 1.0 for c in isi)


def test_rejects_non_4port(tmp_path):
    freq = rf.Frequency(1, 10, 21, unit="GHz")
    media = rf.media.DefinedGammaZ0(frequency=freq, z0=50)
    ntwk = media.line(0.01, unit="m")
    path = tmp_path / "twoport.s2p"
    ntwk.write_touchstone(str(path), form="ri")
    with pytest.raises(ValueError):
        channel.load(str(path))
