"""Jitter tolerance (JTOL) and CDR lock-acquisition demo.

JTOL uses a linearized, continuous-time small-signal model of the bang-bang
loop (standard textbook 2nd-order PLL approximation) to get the CEI/OIF-style
JTOL *shape* — ~20 dB/decade rolloff above the loop bandwidth, flattening to
the eye margin at high frequency. This is NOT a claim of compliance to any
spec mask, just the same functional form (see the project honesty line).
Lock acquisition instead uses the real bit-level `cdr.run_cdr` on a synthetic
oversampled waveform, so at least one CDR figure comes from the actual
(nonlinear) implementation, not the linearization.
"""
from __future__ import annotations

import numpy as np

from .. import cdr as cdr_mod
from .. import prbs as prbs_mod
from .. import tx as tx_mod


def loop_natural_freq_and_damping(kp: float, ki: float, ui_rate_hz: float):
    """Linearize the digital bang-bang loop filter (kp, ki, one update per UI)
    as a continuous-time type-II PLL. Standard small-signal relations."""
    wn_ui = np.sqrt(ki)
    zeta = kp / (2 * np.sqrt(ki))
    wn_hz = wn_ui * ui_rate_hz / (2 * np.pi)
    return wn_hz, zeta


def jitter_transfer(freq_hz, wn_hz: float, zeta: float):
    """Closed-loop jitter TRACKING transfer function (low-pass): how much
    input phase jitter at freq_hz the CDR follows."""
    w = 2 * np.pi * np.asarray(freq_hz, dtype=float)
    wn = 2 * np.pi * wn_hz
    num = 2 * zeta * wn * 1j * w + wn ** 2
    den = -(w ** 2) + 2 * zeta * wn * 1j * w + wn ** 2
    return num / den


def jitter_tolerance(freq_hz, kp: float, ki: float, ui_rate_hz: float,
                      ui_margin: float, cap: float = 0.5):
    """JTOL(f) = ui_margin / |1 - H(f)|: the input sinusoidal-jitter amplitude
    (in UI) that exactly consumes the eye margin at the sampler once the loop
    has tracked what it can. Capped at `cap` UI (a real loop's tolerance
    can't actually go to infinity near DC)."""
    wn_hz, zeta = loop_natural_freq_and_damping(kp, ki, ui_rate_hz)
    h = jitter_transfer(freq_hz, wn_hz, zeta)
    residual_gain = np.maximum(np.abs(1 - h), ui_margin / cap)
    return ui_margin / residual_gain


def demo_lock_acquisition(samples_per_ui: int = 32, n_bits: int = 4000,
                           ppm: float = 200.0, order: int = 15,
                           kp: float = 0.05, ki: float = 0.001,
                           pi_steps_per_ui: int = 64):
    """Build a PRBS-driven NRZ waveform and run the real bit-level bang-bang
    CDR (cdr.run_cdr) on it with an injected TX/RX frequency offset. Returns
    the phase trace so a caller can plot lock acquisition and check the
    settled ramp rate against the injected ppm."""
    bits = prbs_mod.prbs(order, n_bits)
    symbols = tx_mod.nrz_symbols(bits)
    waveform = tx_mod.rise_fall_shape(symbols, ui=1.0, samples_per_ui=samples_per_ui,
                                       rise_frac=0.15)
    phase_ui, data_bits, pd_out = cdr_mod.run_cdr(
        waveform, samples_per_ui, ppm=ppm, kp=kp, ki=ki,
        pi_steps_per_ui=pi_steps_per_ui,
    )
    return phase_ui, data_bits, pd_out
