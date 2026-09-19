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
    length. taps[0] is the precursor tap, meaning it looks at the *next*
    symbol; this convolution already encodes that via tap ordering
    [c-1, c0, c1, ...] applied to the symbol stream."""
    return np.convolve(symbols, taps, mode="full")[: len(symbols)]


def rise_fall_shape(symbols: np.ndarray, ui: float, samples_per_ui: int,
                     rise_frac: float = 0.2) -> np.ndarray:
    """Zero-order-hold each symbol for one UI, then smooth with a finite
    rise/fall time (`rise_frac` of a UI) instead of an ideal rectangle.
    Real TX drivers don't have infinite bandwidth."""
    n = len(symbols) * samples_per_ui
    zoh = np.repeat(symbols, samples_per_ui)
    rise_samples = max(1, int(round(rise_frac * samples_per_ui)))
    window = np.hanning(2 * rise_samples + 1)
    window /= window.sum()
    shaped = np.convolve(zoh, window, mode="same")
    return shaped[:n]


def apply_supply_jitter(waveform: np.ndarray, samples_per_ui: int, ui_sec: float,
                         kvs_ps_per_mv: float, ripple_mv: float, ripple_freq_hz: float,
                         phase: float = 0.0) -> np.ndarray:
    """Power-supply-induced jitter (PSIJ): a driver's supply-delay
    sensitivity Kvs (ps of edge-timing shift per mV of supply ripple) turns
    supply ripple Vn(t) into a timing modulation dt(t) = Kvs * Vn(t). Model
    that directly as a time warp of the already-shaped TX waveform: the
    sample that should land at physical time t instead reads the ideal
    waveform's value from time (t - dt(t)), exactly what "the edge arrived
    dt(t) early/late" means.

    `waveform` must be sampled on a uniform grid at `samples_per_ui`
    samples/UI (i.e. the output of `rise_fall_shape`, before channel
    convolution). `ripple_mv` is the ripple's peak amplitude, not RMS.
    `kvs_ps_per_mv` and `ripple_mv` are amplitudes (not already a dt); at
    ripple_mv=0 this returns `waveform` unchanged (checked in tests).
    """
    n = len(waveform)
    dt_sample = ui_sec / samples_per_ui
    t = np.arange(n) * dt_sample

    vn = ripple_mv * np.sin(2 * np.pi * ripple_freq_hz * t + phase)
    dt_shift = kvs_ps_per_mv * 1e-12 * vn  # ps/mV * mV -> ps -> s

    query_t = t - dt_shift
    return np.interp(query_t, t, waveform)
