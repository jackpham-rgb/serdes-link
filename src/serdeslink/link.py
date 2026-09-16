"""End-to-end link pipeline wiring: channel -> TX (PRBS + FFE + shaping) ->
channel convolution -> CTLE -> UI-center sampling -> (DFE / CDR live in their
own pure modules). This module does bookkeeping/resampling; real plotting
stays in analysis/ and scripts/.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve

from . import channel as channel_mod
from . import ctle as ctle_mod
from . import prbs as prbs_mod
from . import tx as tx_mod


def load_channel(path: str):
    return channel_mod.load(path)


def generate_tx_waveform(n_bits: int, samples_per_ui: int, order: int = 15,
                          ffe=(0.0, 1.0, ())):
    bits = prbs_mod.prbs(order, n_bits)
    symbols = tx_mod.nrz_symbols(bits)
    precursor, main, postcursors = ffe
    taps = tx_mod.ffe_taps(precursor, main, postcursors)
    eq_symbols = tx_mod.apply_ffe(symbols, taps)
    waveform = tx_mod.rise_fall_shape(eq_symbols, ui=1.0, samples_per_ui=samples_per_ui)
    return bits, waveform


def drive_channel(waveform: np.ndarray, h_channel: np.ndarray, dt_channel: float,
                   samples_per_ui: int, ui_sec: float) -> np.ndarray:
    """Resample the channel impulse response onto the TX's sample grid and
    convolve. Energy is rescaled to account for the change in sample spacing
    (an impulse response's DISCRETE samples represent h(t)*dt; changing dt
    without rescaling silently changes the channel's DC gain)."""
    dt_tx = ui_sec / samples_per_ui
    t_channel = np.arange(len(h_channel)) * dt_channel
    t_resampled = np.arange(0, t_channel[-1], dt_tx)
    h_resampled = np.interp(t_resampled, t_channel, h_channel) * (dt_tx / dt_channel)
    return fftconvolve(waveform, h_resampled, mode="full")[: len(waveform)]


def apply_ctle_time_domain(waveform: np.ndarray, samples_per_ui: int, ui_sec: float,
                            **ctle_kwargs) -> np.ndarray:
    """Apply the CTLE in the frequency domain to a time-domain waveform."""
    dt = ui_sec / samples_per_ui
    n = len(waveform)
    freq = np.fft.rfftfreq(n, dt)
    h = ctle_mod.ctle_response(freq, **ctle_kwargs)
    spec = np.fft.rfft(waveform) * h
    return np.fft.irfft(spec, n=n)


def sample_ui_centers(waveform: np.ndarray, samples_per_ui: int,
                       phase_offset_ui: float = 0.5) -> np.ndarray:
    """Downsample a continuous waveform to one sample per UI at a fixed
    phase — used ahead of the DFE once a timing reference is assumed. The
    CDR-driven closed-loop sampling lives in cdr.run_cdr."""
    offset = int(round(phase_offset_ui * samples_per_ui))
    return waveform[offset::samples_per_ui]
