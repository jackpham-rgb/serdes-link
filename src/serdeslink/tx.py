"""TX-side signal path: PRBS bits -> NRZ symbols -> FFE -> finite-rise pulse
shaping. Everything here is a pure array function; no plotting or file I/O.
"""
from __future__ import annotations

import numpy as np


def nrz_symbols(bits: np.ndarray) -> np.ndarray:
    """Map {0,1} bits to NRZ symbols {-1, +1}."""
    return 2.0 * bits.astype(float) - 1.0


def ffe_taps(precursor: float, main: float, postcursors) -> np.ndarray:
    """Assemble a TX FFE tap vector [c-1, c0, c1, c2, ...], power-normalized
    so sum(|tap|) == 1 (a real TX has a fixed output swing budget to split
    across taps)."""
    taps = np.array([precursor, main, *postcursors], dtype=float)
    return taps / np.sum(np.abs(taps))


def apply_ffe(symbols: np.ndarray, taps: np.ndarray) -> np.ndarray:
    """Convolve symbols with the FFE tap vector, truncated back to the input
    length (taps[0] is the precursor tap, i.e. it looks at the *next* symbol
    — this convolution already encodes that via tap ordering [c-1, c0, c1,...]
    applied to the symbol stream)."""
    return np.convolve(symbols, taps, mode="full")[: len(symbols)]


def rise_fall_shape(symbols: np.ndarray, ui: float, samples_per_ui: int,
                     rise_frac: float = 0.2) -> np.ndarray:
    """Zero-order-hold each symbol for one UI, then smooth with a finite
    rise/fall time (`rise_frac` of a UI) instead of an ideal rectangle —
    real TX drivers don't have infinite bandwidth."""
    n = len(symbols) * samples_per_ui
    zoh = np.repeat(symbols, samples_per_ui)
    rise_samples = max(1, int(round(rise_frac * samples_per_ui)))
    window = np.hanning(2 * rise_samples + 1)
    window /= window.sum()
    shaped = np.convolve(zoh, window, mode="same")
    return shaped[:n]
