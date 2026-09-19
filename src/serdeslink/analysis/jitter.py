"""Jitter tolerance (JTOL) and CDR lock-acquisition demo.

JTOL uses a linearized, continuous-time small-signal model of the bang-bang
loop (standard textbook 2nd-order PLL approximation) to get the CEI/OIF-style
JTOL *shape*: about a 20 dB/decade rolloff above the loop bandwidth,
flattening to the eye margin at high frequency. This is NOT a claim of
compliance to any
spec mask, just the same functional form (see the project honesty line).
Lock acquisition instead uses the real bit-level `cdr.run_cdr` on a synthetic
oversampled waveform, so at least one CDR figure comes from the actual
(nonlinear) implementation, not the linearization.
"""
from __future__ import annotations

import numpy as np

from .. import cdr as cdr_mod
from .. import link as link_mod
from .. import prbs as prbs_mod
from .. import tx as tx_mod
from . import eye as eye_mod


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


# ── Power-supply-induced jitter (PSIJ) ──────────────────────────────────────
#
# A driver/clock buffer's supply-delay sensitivity Kvs (ps of edge-timing
# shift per mV of supply ripple) turns periodic supply ripple into periodic
# (deterministic) edge jitter: tx.apply_supply_jitter time-warps the TX
# waveform by dt(t) = Kvs * Vn(t). What happens next depends on the ripple
# frequency relative to the CDR's OWN loop bandwidth (loop_natural_freq_and_
# damping / jitter_transfer, above): ripple below the loop bandwidth gets
# tracked out by the loop (same tracking transfer function JTOL already
# uses); ripple above it passes through as residual sampling-instant error
# and shows up directly as eye closure / raised BER. Both regimes are worth
# showing, not just "ripple closes the eye."

def demo_psij_eye_sweep(samples_per_ui: int, ui_sec: float, ripple_mv_list,
                         ripple_freq_hz: float, kvs_ps_per_mv: float,
                         n_bits: int = 3000, order: int = 15,
                         h_channel=None, dt_channel=None, ctle_kwargs=None):
    """Sweep supply-ripple amplitude and measure the resulting HORIZONTAL
    (timing) eye closure. Uses `eye.crossing_jitter_ui`, NOT `eye.eye_height`:
    PSIJ is a timing effect, and eye_height measures the VERTICAL opening.

    By default (`h_channel=None`) this runs on the TX waveform alone, no
    channel: an isolated measurement of PSIJ's own contribution, which
    matches the injected `dt(t) = Kvs * Vn(t)` model exactly (checked in
    tests). Passing a channel's impulse response (`h_channel`/`dt_channel`,
    as returned by `channel.load`) routes through the full TX -> channel ->
    CTLE pipeline instead (same building blocks as scripts/run_link.py),
    which is more realistic but adds the channel's OWN data-dependent
    jitter as a baseline PSIJ has to be measured on top of -- found
    empirically to be large enough on this project's 12" FR4 channel
    (~0.4 UI of baseline crossing spread from ISI alone) that it swamps a
    clean PSIJ-only demonstration; the isolated (no-channel) case is the
    one this workstream validates against the Kvs model, and is why it's
    the default. See docs/05-power-integrity.md.

    Returns
    -------
    crossing_spread_ui : ndarray, one per entry in `ripple_mv_list`
    """
    # Built directly (matches demo_lock_acquisition's pattern), not via
    # link.generate_tx_waveform: that applies a TX FFE even for the
    # identity case (precursor=0, main=1), and apply_ffe's convolution
    # gives that a one-SAMPLE group delay by construction (a precursor tap
    # is only causal as an overall delay) plus a leading zero sample. That
    # delay doesn't matter to the rest of the link (everything downstream
    # samples the continuous waveform at a chosen phase), but it isn't
    # nothing here either: it was found to noticeably bias the isolated
    # zero-ripple baseline this function validates against an exact
    # formula, and there is no channel here for an FFE to equalize against
    # in the first place, so building the waveform directly avoids the
    # question entirely.
    bits = prbs_mod.prbs(order, n_bits)
    symbols = tx_mod.nrz_symbols(bits)
    tx_waveform = tx_mod.rise_fall_shape(symbols, ui=1.0, samples_per_ui=samples_per_ui, rise_frac=0.15)

    spreads = np.zeros(len(ripple_mv_list))
    for i, ripple_mv in enumerate(ripple_mv_list):
        jittered = tx_mod.apply_supply_jitter(
            tx_waveform, samples_per_ui, ui_sec, kvs_ps_per_mv, ripple_mv, ripple_freq_hz,
        )
        rx = jittered
        if h_channel is not None:
            rx = link_mod.drive_channel(rx, h_channel, dt_channel, samples_per_ui, ui_sec)
        if ctle_kwargs is not None:
            rx = link_mod.apply_ctle_time_domain(rx, samples_per_ui, ui_sec, **ctle_kwargs)
        t_ui, traces = eye_mod.build_eye_traces(rx, samples_per_ui)
        spread, _ = eye_mod.crossing_jitter_ui(traces, t_ui)
        spreads[i] = spread
    return spreads


def demo_psij_spectrum(samples_per_ui: int, ui_sec: float, ripple_mv: float,
                        ripple_freq_hz: float, kvs_ps_per_mv: float,
                        n_bits: int = 4000, order: int = 15,
                        kp: float = 0.05, ki: float = 0.001, pi_steps_per_ui: int = 64):
    """Inject supply ripple into a PRBS TX waveform (no channel: isolating
    the CDR's own response to the ripple), run the real bit-level CDR, and
    return the periodogram of its tracked phase correction. If the ripple
    frequency is inside the loop's tracking bandwidth, `phase_ui` should
    show a spur at `ripple_freq_hz`: the loop visibly chasing the supply
    ripple, exactly the "PSIJ shows up as a DJ spur" effect the ripple/PDN
    workstream is about.

    Returns
    -------
    freqs_hz : ndarray, one-sided FFT frequency axis for `phase_ui`
    spectrum : ndarray, |FFT(phase_ui - mean)|
    wn_hz, zeta : the loop's own natural frequency / damping (for marking
        the loop bandwidth on the same plot as the ripple frequency)
    """
    bits = prbs_mod.prbs(order, n_bits)
    symbols = tx_mod.nrz_symbols(bits)
    waveform = tx_mod.rise_fall_shape(symbols, ui=1.0, samples_per_ui=samples_per_ui, rise_frac=0.15)
    jittered = tx_mod.apply_supply_jitter(
        waveform, samples_per_ui, ui_sec, kvs_ps_per_mv, ripple_mv, ripple_freq_hz,
    )
    phase_ui, data_bits, pd_out = cdr_mod.run_cdr(
        jittered, samples_per_ui, ppm=0.0, kp=kp, ki=ki, pi_steps_per_ui=pi_steps_per_ui,
    )

    ui_rate_hz = 1.0 / ui_sec
    detrended = phase_ui - phase_ui.mean()
    freqs_hz = np.fft.rfftfreq(len(detrended), d=1.0 / ui_rate_hz)
    spectrum = np.abs(np.fft.rfft(detrended))

    wn_hz, zeta = loop_natural_freq_and_damping(kp, ki, ui_rate_hz)
    return freqs_hz, spectrum, wn_hz, zeta
