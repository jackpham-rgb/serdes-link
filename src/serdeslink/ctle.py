"""Continuous-time linear equalizer: one zero, two poles.

    H(jf) = A_dc * (1 + jf/fz) / ((1 + jf/fp1) * (1 + jf/fp2))

Exposed knobs are DC gain and the zero/pole placement. Peaking is a *result*
of that placement, reported by `peaking_db`, not force-fit to a target.
Over-peaking has a real, honest cost; see the sweep in
scripts/sweep_ctle.py.
"""
from __future__ import annotations

import numpy as np


def ctle_response(freq: np.ndarray, dc_gain_db: float = 0.0,
                   zero_hz: float = 1e9, pole1_hz: float = 5e9,
                   pole2_hz: float = 15e9) -> np.ndarray:
    s = 1j * freq
    h_shape = (1 + s / zero_hz) / ((1 + s / pole1_hz) * (1 + s / pole2_hz))
    a_dc = 10 ** (dc_gain_db / 20)
    return a_dc * h_shape


def peaking_db(freq: np.ndarray, h: np.ndarray) -> float:
    """Peak gain minus DC gain, in dB (how much high-frequency boost this
    setting actually applies)."""
    mag_db = 20 * np.log10(np.abs(h) + 1e-30)
    return float(np.max(mag_db) - mag_db[0])
