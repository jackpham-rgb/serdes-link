"""Statistical BER / bathtub curve via the peak-distortion (StatEye-style)
method: build the ISI amplitude distribution from pulse-response cursors,
convolve with Gaussian noise/random-jitter, and integrate the tails vs
decision threshold. No brute-force bit-by-bit Monte Carlo to 1e-12.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm


def isi_pdf(isi_cursors, n_points: int = 4096, clip: float = 1.5):
    """Amplitude PDF at the sampler from ISI alone (main cursor normalized to
    +-1, excluded from `isi_cursors`). Each cursor contributes a +-|cursor|
    pair (both bit values equally likely), so the full PDF is the
    convolution of one two-point distribution per cursor. This is the
    standard peak-distortion construction."""
    amp = np.linspace(-clip, clip, n_points)
    da = amp[1] - amp[0]
    pdf = np.zeros(n_points)
    pdf[n_points // 2] = 1.0  # delta at 0
    for c in isi_cursors:
        shift = int(round(c / da))
        new_pdf = 0.5 * np.roll(pdf, shift) + 0.5 * np.roll(pdf, -shift)
        pdf = new_pdf
    pdf /= pdf.sum() * da
    return amp, pdf


def bathtub(isi_cursors, sigma_rj: float, thresholds=None, n_points: int = 4096):
    """BER vs decision threshold, symmetric-channel assumption (main cursor
    normalized to +-1).

    Returns
    -------
    thresholds : ndarray
    ber_high : ndarray, P(sample < threshold | sent '1')
    ber_low : ndarray, P(sample > threshold | sent '0') (mirror of ber_high)
    """
    amp, pdf = isi_pdf(isi_cursors, n_points=n_points)
    da = amp[1] - amp[0]
    if thresholds is None:
        thresholds = np.linspace(-1.2, 1.2, 200)

    ber_high = np.zeros_like(thresholds)
    for i, th in enumerate(thresholds):
        z = (th - (1.0 + amp)) / sigma_rj
        ber_high[i] = np.sum(pdf * norm.cdf(z)) * da

    ber_low = ber_high[::-1]
    return thresholds, ber_high, ber_low
