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


def plot_eye(ax, t_ui, traces, title=None, color="C0", alpha=0.15):
    for tr in traces:
        ax.plot(t_ui, tr, color=color, alpha=alpha, linewidth=0.6)
    ax.set_xlabel("UI")
    ax.set_ylabel("amplitude")
    if title:
        ax.set_title(title)
