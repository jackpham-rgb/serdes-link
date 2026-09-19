"""Statistical BER / bathtub curve via the peak-distortion (StatEye-style)
method: build the ISI amplitude distribution from pulse-response cursors,
convolve with Gaussian noise/random-jitter, and integrate the tails vs
decision threshold. No brute-force bit-by-bit Monte Carlo to 1e-12.

Detection theory (EECS126 hypothesis testing), named explicitly: the
sampler's slicer is a MAP (maximum a posteriori) detector choosing between
two hypotheses, H0 (bit sent = -1) and H1 (bit sent = +1). `bathtub`
already computes each hypothesis's error probability via a Gaussian tail
(`norm.cdf`), i.e. P(error) = Q((c0 - |ISI|) / sigma) with c0 the main
cursor -- that IS the Q-function BER formula, it just wasn't named as
such. It ALSO silently assumes the optimal decision threshold is 0, which
is only true for a symmetric channel (equal means +-1, equal noise sigma
on both sides). `optimal_threshold` below derives what the threshold
actually should be, from the likelihood-ratio test, when that symmetry
doesn't hold -- e.g. asymmetric signal levels (duty-cycle distortion: the
'1' and '0' levels aren't equal and opposite) or asymmetric noise
(different effective sigma on each side).
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
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


def optimal_threshold(mu0: float, sigma0: float, mu1: float, sigma1: float,
                       p0: float = 0.5, p1: float = 0.5) -> float:
    """The MAP decision threshold between two Gaussian hypotheses (H0: bit
    sent = -1, sampled value ~ N(mu0, sigma0^2); H1: bit sent = +1, sampled
    value ~ N(mu1, sigma1^2)), from the likelihood-ratio test:
    p1 * f1(t) == p0 * f0(t), i.e. decide H1 when p1*f1(t) > p0*f0(t).

    Equal-variance case (sigma0 == sigma1 == sigma): the likelihood-ratio
    equation is linear in t and solves in closed form:
        t* = (mu0 + mu1)/2 + sigma^2/(mu1 - mu0) * ln(p1/p0)
    which is exactly 0 for a symmetric channel (mu1 = -mu0, p0 = p1 = 0.5)
    -- the threshold `bathtub` implicitly assumes everywhere. A DC offset
    between the levels (mu0 != -mu1, e.g. duty-cycle distortion) shifts it
    to the weighted midpoint (mu0+mu1)/2 even with equal priors.

    Unequal-variance case: the likelihood-ratio equation is quadratic in t
    (the classic unequal-variance Gaussian discriminant boundary) and is
    solved numerically here (`brentq` on the log-likelihood-ratio, bracketed
    between the two means) rather than by hand-picking the correct one of
    two algebraic roots.
    """
    if np.isclose(sigma0, sigma1):
        s2 = sigma0 ** 2
        return (mu0 + mu1) / 2 + s2 / (mu1 - mu0) * np.log(p1 / p0)

    def log_likelihood_ratio(t):
        return (np.log(p1) + norm.logpdf(t, mu1, sigma1)
                - np.log(p0) - norm.logpdf(t, mu0, sigma0))

    lo, hi = sorted([mu0, mu1])
    return brentq(log_likelihood_ratio, lo, hi)


def error_probability(threshold: float, mu0: float, sigma0: float,
                       mu1: float, sigma1: float,
                       p0: float = 0.5, p1: float = 0.5) -> float:
    """Total P(error) for a given decision threshold: p0 * P(decide H1 | H0)
    + p1 * P(decide H0 | H1), the same Q-function construction `bathtub`
    uses, generalized to unequal means/variances/priors so it can be
    evaluated at `optimal_threshold`'s answer instead of assuming 0."""
    if mu0 <= mu1:
        p_err_h0 = norm.sf(threshold, mu0, sigma0)   # sampled above threshold -> wrongly decided H1
        p_err_h1 = norm.cdf(threshold, mu1, sigma1)  # sampled below threshold -> wrongly decided H0
    else:
        p_err_h0 = norm.cdf(threshold, mu0, sigma0)
        p_err_h1 = norm.sf(threshold, mu1, sigma1)
    return p0 * p_err_h0 + p1 * p_err_h1
