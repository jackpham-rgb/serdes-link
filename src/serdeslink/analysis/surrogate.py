"""A multivariate regression surrogate of the link: fit log10(BER) as a
function of design settings (channel length, CTLE zero placement, DFE tap
count), instead of only ever reading it off a brute-force sweep.

Generalizes `optimize.py`'s 1-D quadratic CTLE fit (EECS189 regression,
bias/variance): start with plain polynomial regression (the normal
equations again, this time on more than one input dimension), then a
gradient-boosted tree model (XGBoost) for the nonlinear/interaction terms
polynomial regression of a fixed degree can't capture. Feature importances
/ sensitivities are read as DESIGN INTUITION (which knob matters most),
and the fitted surrogate can propose good settings faster than a
brute-force grid, exactly the same way `optimize.fit_optimal_peaking`
already does for the 1-D case; this is not a model that designs a circuit.
"""
from __future__ import annotations

import numpy as np
from xgboost import XGBRegressor


def polynomial_features(X: np.ndarray, degree: int = 2) -> tuple[np.ndarray, list[str]]:
    """Expand `X` (n_samples, n_features) into an explicit polynomial
    design matrix: a bias column, the linear terms, and (for degree=2) the
    squared and pairwise-interaction terms. Plain and explicit on purpose
    (matches `optimize.py`'s `np.polyfit`-based 1-D fit, generalized by
    hand rather than pulled in from a modeling library), so the columns
    stay directly readable as physical quantities in `feature_names`.
    """
    if degree not in (1, 2):
        raise ValueError("polynomial_features only supports degree 1 or 2")
    X = np.asarray(X, dtype=float)
    n, d = X.shape
    cols = [np.ones(n)]
    names = ["bias"]
    for i in range(d):
        cols.append(X[:, i])
        names.append(f"x{i}")
    if degree == 2:
        for i in range(d):
            cols.append(X[:, i] ** 2)
            names.append(f"x{i}^2")
        for i in range(d):
            for j in range(i + 1, d):
                cols.append(X[:, i] * X[:, j])
                names.append(f"x{i}*x{j}")
    return np.column_stack(cols), names


def fit_linear_regression(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """w = (X^T X)^-1 X^T y via `lstsq` (the same normal-equations object
    as `equalizer_opt.ls_taps`, applied here to a design matrix instead of
    a DFE regressor)."""
    w, *_ = np.linalg.lstsq(np.asarray(X, dtype=float), np.asarray(y, dtype=float), rcond=None)
    return w


def r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


class PolynomialSurrogate:
    """Degree-2 polynomial regression surrogate, fit once on raw (x0, x1,
    ...) feature columns."""

    def __init__(self, degree: int = 2):
        self.degree = degree
        self.weights = None
        self.feature_names = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "PolynomialSurrogate":
        Xp, names = polynomial_features(X, degree=self.degree)
        self.weights = fit_linear_regression(Xp, y)
        self.feature_names = names
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        Xp, _ = polynomial_features(X, degree=self.degree)
        return Xp @ self.weights

    def coefficient_table(self) -> list[tuple[str, float]]:
        """(name, weight) pairs, for reading which terms matter -- NOT a
        standardized/z-scored importance (raw regression coefficients
        depend on each feature's own units and scale), just the fitted
        polynomial's own terms, for inspection alongside the XGBoost
        feature importances below."""
        return list(zip(self.feature_names, self.weights))


def fit_xgboost_surrogate(X: np.ndarray, y: np.ndarray, **kwargs) -> XGBRegressor:
    defaults = dict(n_estimators=200, max_depth=3, learning_rate=0.1)
    defaults.update(kwargs)
    model = XGBRegressor(**defaults)
    model.fit(np.asarray(X, dtype=float), np.asarray(y, dtype=float))
    return model


def suggest_settings(predict_fn, bounds, integer_dims=(), n_samples: int = 20000,
                      minimize: bool = True, rng=None):
    """Random search over `bounds` (a list of (lo, hi) per feature) using
    an already-fit surrogate's `predict_fn`, instead of a brute-force grid
    over the real link. `integer_dims` are feature indices to round to the
    nearest integer after sampling (e.g. a DFE tap count). Returns
    (best_x, best_y).
    """
    rng = rng or np.random.default_rng(0)
    bounds = np.asarray(bounds, dtype=float)
    n_features = bounds.shape[0]
    samples = rng.uniform(bounds[:, 0], bounds[:, 1], size=(n_samples, n_features))
    for i in integer_dims:
        samples[:, i] = np.round(samples[:, i])
    preds = predict_fn(samples)
    idx = int(np.argmin(preds)) if minimize else int(np.argmax(preds))
    return samples[idx], preds[idx]
