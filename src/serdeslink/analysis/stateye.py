"""Statistical eye: bit error rate from a single-bit pulse response.

The link is linear up to the slicer, so the sampled value for one bit is the
main cursor plus a sum of +-ISI cursors plus Gaussian noise. Convolving one
two-point distribution per cursor gives the exact ISI amplitude distribution
(the peak-distortion construction), with no long bit-by-bit simulation.
Random jitter is applied by averaging over a Gaussian spread of sampling
phases. A DFE is modeled as fixed taps equal to the first postcursors at the
sampling phase, so away from that phase only the difference is left.

`stat_eye` returns BER against sampling phase and decision threshold, and
the eye height and width at a target BER.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm


def cursor_matrix(pulse: np.ndarray, idx0: int, samples_per_ui: int,
                  n_pre: int = 6, n_post: int = 80):
    """Sample the pulse response at UI spacing for every phase in one UI.

    Returns (phases, ks, c) where c[i, j] = pulse[idx0 + phases[i] + ks[j]*spu].
    """
    spu = samples_per_ui
    phases = np.arange(-spu // 2, spu // 2 + 1)
    ks = np.arange(-n_pre, n_post + 1)
    idx = idx0 + phases[:, None] + ks[None, :] * spu
    ok = (idx >= 0) & (idx < len(pulse))
    c = np.where(ok, pulse[np.clip(idx, 0, len(pulse) - 1)], 0.0)
    return phases, ks, c


def _amplitude_cdf(main: float, isi: np.ndarray, sigma: float, vgrid: np.ndarray) -> np.ndarray:
    """CDF on `vgrid` of main + sum(+-isi) + N(0, sigma^2), for a sent '1'."""
    isi = isi[np.abs(isi) > 1e-6 * max(abs(main), 1e-12)]
    span = float(np.sum(np.abs(isi))) + 1e-12
    n = 4001
    grid = np.linspace(-span, span, n)
    step = grid[1] - grid[0]
    pdf = np.zeros(n)
    pdf[n // 2] = 1.0
    for c in isi:
        shift = int(round(c / step))
        if shift:
            pdf = 0.5 * np.roll(pdf, shift) + 0.5 * np.roll(pdf, -shift)
    keep = pdf > 0
    levels = main + grid[keep]
    weights = pdf[keep]
    return (weights[None, :] * norm.cdf((vgrid[:, None] - levels[None, :]) / sigma)).sum(axis=1)


def _run_length(ok: np.ndarray, start: int) -> tuple[int, int]:
    lo = hi = start
    while lo - 1 >= 0 and ok[lo - 1]:
        lo -= 1
    while hi + 1 < len(ok) and ok[hi + 1]:
        hi += 1
    return lo, hi


def stat_eye(pulse: np.ndarray, idx0: int, samples_per_ui: int, sigma_noise: float,
             sigma_rj_ui: float = 0.0, n_dfe: int = 0, target_ber: float = 1e-12) -> dict:
    """Statistical eye around sample index `idx0` of `pulse`.

    `idx0` is the data sampling instant (phase 0). `sigma_noise` is the rms
    noise at the slicer in the same units as `pulse`. `n_dfe` postcursors are
    cancelled with taps frozen at phase 0.
    """
    spu = samples_per_ui
    phases, ks, c = cursor_matrix(pulse, idx0, spu)
    k0 = int(np.where(ks == 0)[0][0])
    i_ref = int(np.where(phases == 0)[0][0])
    vmax = 1.3 * float(np.max(np.abs(c[:, k0])))
    vgrid = np.linspace(-vmax, vmax, 801)

    ref_isi = np.delete(c[i_ref], k0)
    cdf_one = np.zeros((len(phases), len(vgrid)))
    for i in range(len(phases)):
        isi = np.delete(c[i], k0).copy()
        if n_dfe:
            sel = np.arange(k0, k0 + n_dfe)  # postcursors 1..n_dfe after the delete
            isi[sel] -= ref_isi[sel]
        cdf_one[i] = _amplitude_cdf(c[i, k0], isi, sigma_noise, vgrid)

    if sigma_rj_ui > 0:
        spread = sigma_rj_ui * spu
        d = phases[:, None] - phases[None, :]
        w = np.exp(-0.5 * (d / spread) ** 2)
        w /= w.sum(axis=1, keepdims=True)
        cdf_one = w @ cdf_one

    # Symmetric signaling: P(v > th | sent 0) equals the mirrored CDF.
    ber = 0.5 * cdf_one + 0.5 * cdf_one[:, ::-1]
    v0 = len(vgrid) // 2
    ber_vs_phase = ber[:, v0]
    ib = i_ref

    width = 0.0
    ok = ber_vs_phase <= target_ber
    if ok[ib]:
        lo, hi = _run_length(ok, ib)
        width = (hi - lo) / spu
    height = 0.0
    okv = ber[ib] <= target_ber
    if okv[v0]:
        lo, hi = _run_length(okv, v0)
        height = float(vgrid[hi] - vgrid[lo])

    return {
        "phases_ui": phases / spu,
        "vgrid": vgrid,
        "ber": ber,
        "ber_vs_phase": ber_vs_phase,
        "ber_vs_threshold": ber[ib],
        "ber_center": float(ber_vs_phase[ib]),
        "eye_width_ui": float(width),
        "eye_height": height,
        "main_cursor": float(c[i_ref, k0]),
        "cursors": c[i_ref],
        "ks": ks,
    }


def best_sampling_index(pulse: np.ndarray, samples_per_ui: int, n_dfe: int = 0) -> int:
    """Sample index that maximizes the worst-case (peak-distortion) opening:
    main cursor minus the sum of the ISI cursors the DFE does not cancel."""
    spu = samples_per_ui
    peak = int(np.argmax(np.abs(pulse)))
    best, best_idx = -np.inf, peak
    for idx in range(peak - spu, peak + spu + 1):
        ks = np.arange(-6, 81)
        j = idx + ks * spu
        ok = (j >= 0) & (j < len(pulse))
        c = np.where(ok, pulse[np.clip(j, 0, len(pulse) - 1)], 0.0)
        isi = np.abs(np.delete(c, 6))
        if n_dfe:
            isi[6:6 + n_dfe] = 0.0
        opening = c[6] - isi.sum()
        if opening > best:
            best, best_idx = opening, idx
    return best_idx
