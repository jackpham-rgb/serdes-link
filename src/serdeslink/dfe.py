"""Decision-feedback equalizer with sign-sign LMS tap adaptation.

Pure array function: no matplotlib, no file I/O. This is what Stage C
reimplements in SystemVerilog and cosimulates against via cocotb, so its
inputs/outputs stay plain arrays on purpose.
"""
from __future__ import annotations

import numpy as np


def run_dfe(samples: np.ndarray, n_taps: int = 4, mu: float = 1e-3,
            ref_level: float = 0.0, init_taps=None):
    """Slice `samples` (one sample per UI, already CTLE'd and timing-aligned)
    through a sign-sign LMS DFE.

    Returns
    -------
    decisions : ndarray {-1,+1}, one per input sample
    taps_history : ndarray, shape (len(samples), n_taps)
    residual : ndarray, the value actually seen by the slicer AFTER feedback
        cancellation. Plot THIS for the "opened" eye, never the raw channel
        eye (see common failure mode notes in the project howto).
    """
    n = len(samples)
    taps = np.zeros(n_taps) if init_taps is None else np.asarray(init_taps, dtype=float).copy()
    decisions = np.zeros(n)
    residual = np.zeros(n)
    taps_history = np.zeros((n, n_taps))
    past = np.zeros(n_taps)  # past decisions, most recent first

    for i in range(n):
        feedback = np.dot(taps, past)
        r = samples[i] - feedback
        residual[i] = r
        d = 1.0 if r >= ref_level else -1.0
        decisions[i] = d

        error = d - r
        taps -= mu * np.sign(error) * np.sign(past)
        taps_history[i] = taps

        past = np.roll(past, 1)
        past[0] = d

    return decisions, taps_history, residual
