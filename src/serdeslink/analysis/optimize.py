"""Applied optimization on measurement/simulation data.

This is the "use math/optimization to process signal and measurement data"
half of applied ML this project actually does. It is a completely different
thing from ML that designs or judges a circuit's layout (choosing transistor
sizes, judging a floorplan), which stays out of scope here; see the ML
decision in docs/00-spec.md for that distinction spelled out.
"""
from __future__ import annotations

import numpy as np


def fit_optimal_peaking(peaking_db, eye_height):
    """Fit a quadratic (least squares) to eye_height vs peaking_db and solve
    for its vertex: the CONTINUOUS peaking value the data predicts is
    optimal, not just the best of a handful of sampled grid points. A CTLE
    sweep genuinely has a single interior optimum (peaking helps, then
    over-peaking hurts; see docs/01-model.md), so a concave-down quadratic
    is a reasonable local model near that optimum, not a curve-fitting trick
    for its own sake.

    Returns
    -------
    optimal_peaking_db : float, or None if the fit isn't concave (no
        interior maximum in this data; the quadratic model doesn't apply)
    predicted_eye_height : float, or None
    coeffs : ndarray, the fitted [a, b, c] for a*x^2 + b*x + c
    """
    x = np.asarray(peaking_db, dtype=float)
    y = np.asarray(eye_height, dtype=float)
    coeffs = np.polyfit(x, y, deg=2)
    a, b, c = coeffs
    if a >= 0:
        return None, None, coeffs
    x_opt = -b / (2 * a)
    y_opt = a * x_opt ** 2 + b * x_opt + c
    return float(x_opt), float(y_opt), coeffs
