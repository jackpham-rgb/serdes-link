"""Bang-bang (Alexander) CDR: phase detector + 2nd-order digital loop filter +
finite-resolution phase interpolator, closing the loop on a real (oversampled)
waveform.

Pure array/scalar functions: no matplotlib, no file I/O. This is the Stage C
cocotb golden model.
"""
from __future__ import annotations

import numpy as np


def alexander_pd(edge_bit: int, early_bit: int, late_bit: int) -> int:
    """Classic bang-bang phase detector. If the two data bits either side of
    the edge sample agree, there was no transition and the PD abstains (0).
    Otherwise, if the edge sample already matches the bit AFTER the
    transition, the transition happened before our edge sample landed — i.e.
    the sampling clock is running LATE (+1). If it still matches the bit
    BEFORE the transition, the clock is EARLY (-1). Note: run_cdr applies
    NEGATIVE feedback to this (late -> decrease correction), consistent with
    "late" meaning the sample needs to move earlier."""
    if early_bit == late_bit:
        return 0
    return 1 if edge_bit == late_bit else -1


def _sample_at(waveform: np.ndarray, idx: float) -> float:
    """Linear interpolation into `waveform` at a fractional sample index
    (indices wrap, since the waveform is generated from a periodic PRBS)."""
    n = len(waveform)
    i0 = int(np.floor(idx)) % n
    i1 = (i0 + 1) % n
    frac = idx - np.floor(idx)
    return (1 - frac) * waveform[i0] + frac * waveform[i1]


def run_cdr(waveform: np.ndarray, samples_per_ui: int, ppm: float = 0.0,
            kp: float = 0.05, ki: float = 0.001, pi_steps_per_ui: int = 64,
            initial_phase_offset: float = 0.0, n_ui: int | None = None):
    """Closed-loop bang-bang CDR over a continuous, oversampled NRZ waveform.

    The RX free-running clock advances `samples_per_ui * (1 + ppm*1e-6)`
    samples per UI in the TX's sample-index space (modeling a TX/RX crystal
    frequency offset); the loop must steer a phase-interpolator correction to
    track it.

    Returns
    -------
    phase_ui : ndarray, accumulated PI correction in UI, per UI step
    data_bits : ndarray {-1,+1}, recovered decision per UI
    pd_out : ndarray {-1,0,1}, raw phase-detector output per UI
    """
    if n_ui is None:
        n_ui = int(len(waveform) / samples_per_ui) - 2

    step = samples_per_ui * (1.0 + ppm * 1e-6)
    pi_step_samples = samples_per_ui / pi_steps_per_ui

    correction = initial_phase_offset * samples_per_ui
    integrator = 0.0

    phase_ui = np.zeros(n_ui)
    data_bits = np.zeros(n_ui)
    pd_out = np.zeros(n_ui)

    prev_bit = None
    for i in range(n_ui):
        # `center` targets the middle of UI i (a data sample); `boundary` is
        # the transition instant between UI i-1 and UI i (the edge sample).
        center = i * step + samples_per_ui / 2 + correction
        boundary = i * step + correction

        data_val = _sample_at(waveform, center)
        edge_val = _sample_at(waveform, boundary)

        bit = 1 if data_val >= 0 else -1
        edge_bit = 1 if edge_val >= 0 else -1

        pd = 0 if prev_bit is None else alexander_pd(edge_bit, prev_bit, bit)
        pd_out[i] = pd

        # kp/ki are gains in UI (fraction of a UI the loop moves per PD
        # firing); convert to samples before quantizing to the PI's step
        # size. Feedback is NEGATIVE on pd: "late" (+1) must DECREASE the
        # correction (sample earlier) to close the loop, not increase it.
        integrator += ki * (-pd)
        raw_correction_samples = (kp * (-pd) + integrator) * samples_per_ui
        if pi_step_samples > 0:
            correction += pi_step_samples * round(raw_correction_samples / pi_step_samples)
        else:
            correction += raw_correction_samples

        phase_ui[i] = correction / samples_per_ui
        data_bits[i] = bit
        prev_bit = bit

    return phase_ui, data_bits, pd_out
