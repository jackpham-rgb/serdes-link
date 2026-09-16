"""Load a differential channel from a 4-port single-ended Touchstone file and
derive its impulse / pulse response.

Port map assumed (must match whatever wrote the .sNp file, including
data/touchstone/make_synthetic_channel.py):
    port 1 = TX+   port 2 = TX-   port 3 = RX+   port 4 = RX-
This is scikit-rf's se2gmm(p=2) NATIVE port order for a 4-port: (in+, in-,
out+, out-) — i.e. grouped by near-end/far-end, not by polarity. It is easy
to get this backwards (grouped by polarity: TX+, RX+, TX-, RX-) and get
numerically-plausible-looking garbage out of se2gmm. If you load a measured
file with a different physical port map, renumber it to this order first
(skrf.Network.renumber) — do not silently trust the file's own port labels.
"""
from __future__ import annotations

import numpy as np
import skrf as rf


def load(path: str):
    """Load a 4-port single-ended Touchstone file and return the
    differential-mode (SDD21) impulse response.

    Returns
    -------
    t : ndarray, seconds, uniform grid starting at 0
    h : ndarray, impulse response h(t), same length as t
    freq : ndarray, Hz, frequency grid SDD21 was measured/extrapolated on
    sdd21 : ndarray, complex, differential insertion loss on `freq`
    """
    ntwk = rf.Network(path)
    if ntwk.nports != 4:
        raise ValueError(
            f"{path}: expected a 4-port single-ended Touchstone file, got {ntwk.nports} ports"
        )

    gmm = ntwk.copy()
    gmm.se2gmm(p=2)
    # After se2gmm(p=2) with input order (TX+, TX-, RX+, RX-), differential
    # ports are [DM_TX, DM_RX] (indices 0, 1); SDD21 = DM_RX <- DM_TX.
    sdd21 = gmm.s[:, 1, 0]
    freq = gmm.f

    freq_dc, sdd21_dc = _extrapolate_to_dc(freq, sdd21)
    t, h = _to_impulse_response(freq_dc, sdd21_dc)
    return t, h, freq_dc, sdd21_dc


def _extrapolate_to_dc(freq: np.ndarray, sdd21: np.ndarray):
    """S-parameters rarely include a DC point. Extrapolate the first two
    measured points linearly in magnitude (dB) down to 0 Hz, and force the
    DC point to be real and positive (a physical passive reciprocal channel
    has zero phase shift at DC)."""
    if freq[0] == 0:
        return freq, sdd21
    mag_db = 20 * np.log10(np.abs(sdd21))
    slope = (mag_db[1] - mag_db[0]) / (freq[1] - freq[0])
    mag_db0 = mag_db[0] - slope * freq[0]
    freq_dc = np.concatenate(([0.0], freq))
    sdd21_dc = np.concatenate(([10 ** (mag_db0 / 20)], sdd21))
    return freq_dc, sdd21_dc


def _to_impulse_response(freq: np.ndarray, sdd21: np.ndarray, n_freq: int = 4096):
    """Uniform-resample SDD21 onto [0, fmax] and IFFT (via irfft, which
    enforces conjugate symmetry for us) to a real time-domain impulse
    response. Magnitude and unwrapped phase are interpolated separately so we
    never interpolate straight across a phase-wrap branch cut."""
    f_uniform = np.linspace(freq[0], freq[-1], n_freq)
    mag = np.interp(f_uniform, freq, np.abs(sdd21))
    phase = np.interp(f_uniform, freq, np.unwrap(np.angle(sdd21)))
    h_freq = mag * np.exp(1j * phase)

    h_time = np.fft.irfft(h_freq)
    fs = 2 * f_uniform[-1]
    dt = 1.0 / fs
    t = np.arange(len(h_time)) * dt
    return t, h_time


def causality_energy_fraction(h: np.ndarray, guard_samples: int = 8) -> float:
    """Fraction of impulse-response energy that appears more than
    `guard_samples` before the main peak. Small for a well-behaved channel;
    large usually means a DC-extrapolation or phase-unwrap bug (see
    _extrapolate_to_dc / _to_impulse_response)."""
    peak = int(np.argmax(np.abs(h)))
    if peak <= guard_samples:
        return 0.0
    energy_before = float(np.sum(h[: peak - guard_samples] ** 2))
    energy_total = float(np.sum(h ** 2))
    return energy_before / energy_total if energy_total > 0 else 0.0


def pulse_response(h: np.ndarray, dt: float, ui_sec: float) -> np.ndarray:
    """p(t) = h(t) * rect_UI(t): the single-bit pulse response, used for
    cursor/ISI analysis (see cursor_amplitudes) and TX eye-diagram figures."""
    n_ui_samples = max(1, int(round(ui_sec / dt)))
    rect = np.ones(n_ui_samples)
    return np.convolve(h, rect, mode="full") * dt


def cursor_amplitudes(p: np.ndarray, dt: float, ui_sec: float,
                       n_precursors: int = 2, n_postcursors: int = 4):
    """Sample the pulse response at UI spacing around its peak. Returns
    (main_cursor, isi_cursors) where isi_cursors is precursors then
    postcursors, each normalized by the main cursor amplitude — the form
    analysis.ber.isi_pdf expects."""
    ui_samples = max(1, int(round(ui_sec / dt)))
    peak = int(np.argmax(np.abs(p)))
    main = p[peak]
    isi = []
    for k in range(-n_precursors, 0):
        idx = peak + k * ui_samples
        isi.append(float(p[idx] / main) if 0 <= idx < len(p) else 0.0)
    for k in range(1, n_postcursors + 1):
        idx = peak + k * ui_samples
        isi.append(float(p[idx] / main) if 0 <= idx < len(p) else 0.0)
    return float(main), isi
