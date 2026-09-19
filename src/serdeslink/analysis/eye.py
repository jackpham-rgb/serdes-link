"""Eye-diagram construction and eye-opening metrics.

Numeric functions here are pure (testable); `plot_eye` is the one function
that touches matplotlib.
"""
from __future__ import annotations

import numpy as np


def build_eye_traces(waveform: np.ndarray, samples_per_ui: int, ui_span: int = 2):
    """Slice a continuous, sampled waveform into overlapping `ui_span`-UI-wide
    traces for an eye diagram.

    Returns
    -------
    t_ui : ndarray, shared UI-relative time axis, length = ui_span*samples_per_ui
    traces : ndarray, shape (n_traces, len(t_ui))
    """
    win = ui_span * samples_per_ui
    n_traces = len(waveform) // samples_per_ui - ui_span
    traces = np.zeros((max(n_traces, 0), win))
    for i in range(n_traces):
        start = i * samples_per_ui
        traces[i] = waveform[start:start + win]
    t_ui = np.linspace(0, ui_span, win, endpoint=False)
    return t_ui, traces


def eye_height(traces: np.ndarray, center_frac: float = 0.5, band_frac: float = 0.1) -> float:
    """Vertical eye opening near the UI center: min(top cluster) -
    max(bottom cluster), sampled in a narrow time band around `center_frac`
    of the trace window."""
    if traces.size == 0:
        return 0.0
    n = traces.shape[1]
    lo = max(0, int((center_frac - band_frac / 2) * n))
    hi = min(n, int((center_frac + band_frac / 2) * n))
    center_vals = traces[:, lo:hi]
    top = center_vals[center_vals > 0]
    bottom = center_vals[center_vals <= 0]
    if len(top) == 0 or len(bottom) == 0:
        return 0.0
    return float(top.min() - bottom.max())


def crossing_jitter_ui(traces: np.ndarray, t_ui: np.ndarray, crossing_t_ui: float = 1.0,
                        search_band_ui: float = 0.6) -> tuple[float, np.ndarray]:
    """Horizontal (timing) eye metric: peak-to-peak spread of where traces
    cross zero near `crossing_t_ui` (a UI boundary, where a bit TRANSITION
    can happen). `eye_height` measures the VERTICAL opening, appropriate
    for amplitude/ISI effects; this measures the HORIZONTAL one, the
    correct metric for timing jitter (a supply-ripple-induced dt(t) shows
    up here, not necessarily in eye_height -- see docs/05-power-integrity.md).
    Only traces that actually transition near `crossing_t_ui` contribute
    (a PRBS trace with no transition there never crosses and is skipped,
    same as a real TIE/jitter measurement only using edges that exist).

    Returns
    -------
    spread_ui : float, max - min crossing time (0.0 if fewer than 2 traces
        have a transition in the search band)
    crossings_ui : ndarray, the individual crossing times found
    """
    lo = np.searchsorted(t_ui, crossing_t_ui - search_band_ui / 2)
    hi = np.searchsorted(t_ui, crossing_t_ui + search_band_ui / 2)
    t_seg = t_ui[lo:hi]
    crossings = []
    for tr in traces:
        seg = tr[lo:hi]
        signs = np.sign(seg)
        idx = np.flatnonzero(np.diff(signs) != 0)
        if idx.size == 0:
            continue
        i = idx[0]
        y0, y1 = seg[i], seg[i + 1]
        t0, t1 = t_seg[i], t_seg[i + 1]
        frac = -y0 / (y1 - y0)
        crossings.append(t0 + frac * (t1 - t0))
    crossings = np.array(crossings)
    if len(crossings) < 2:
        return 0.0, crossings
    return float(crossings.max() - crossings.min()), crossings


def plot_eye(ax, t_ui, traces, title=None, color="C0", alpha=0.15):
    for tr in traces:
        ax.plot(t_ui, tr, color=color, alpha=alpha, linewidth=0.6)
    ax.set_xlabel("UI")
    ax.set_ylabel("amplitude")
    if title:
        ax.set_title(title)
