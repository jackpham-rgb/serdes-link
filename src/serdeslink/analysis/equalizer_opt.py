"""Optimal (non-adaptive) equalizer taps, next to dfe.py's adaptive sign-sign
LMS: the same object LMS is converging TOWARD, computed directly.

MMSE / Wiener-Hopf (EECS126 LLSE/MMSE estimation):
    w* = R^-1 p,  R = E[y y^T] (regressor autocorrelation),
                  p = E[y d]   (cross-correlation of the regressor with the
                                desired/target value)
Least squares (EECS127 + Boyd ch. 4; 16A/16B linear algebra) is the same
object approached from a different direction:
    minimize ||Y w - d||^2   ->   w = (Y^T Y)^-1 Y^T d
`mmse_taps` solves the normal equations directly (R w = p); `ls_taps` calls
`numpy.linalg.lstsq` on the same (Y, d) pair, which is more numerically
robust when Y is close to rank-deficient. Both should agree closely.

`convex_taps` adds what a closed-form formula can't express: an inequality
CONSTRAINT on the taps (e.g. a TX power/swing budget, matching tx.py's
sum(|tap|) == 1 normalization for the FFE), solved with cvxpy.
"""
from __future__ import annotations

import cvxpy as cp
import numpy as np


def build_regressor_matrix(decisions: np.ndarray, n_taps: int) -> np.ndarray:
    """Build the DFE's own regressor matrix from a decision sequence: row i
    is `[decisions[i-1], decisions[i-2], ..., decisions[i-n_taps]]`, most
    recent first, matching dfe.py's `past` tap-history ordering exactly (so
    the same taps solve `Y @ taps ~= target` for either LMS or a
    closed-form solver). The first `n_taps` rows (not enough history yet)
    are dropped.
    """
    decisions = np.asarray(decisions, dtype=float)
    n = len(decisions)
    Y = np.zeros((n - n_taps, n_taps))
    for k in range(n_taps):
        Y[:, k] = decisions[n_taps - 1 - k: n - 1 - k]
    return Y


def mmse_taps(Y: np.ndarray, d: np.ndarray) -> np.ndarray:
    """w* = R^-1 p via the normal equations, solved directly."""
    Y = np.asarray(Y, dtype=float)
    d = np.asarray(d, dtype=float)
    R = Y.T @ Y
    p = Y.T @ d
    return np.linalg.solve(R, p)


def ls_taps(Y: np.ndarray, d: np.ndarray) -> np.ndarray:
    """The same w* = R^-1 p, via `lstsq` instead of solving R directly.
    More robust than `mmse_taps` when Y is near rank-deficient (R close to
    singular); the two should otherwise agree."""
    Y = np.asarray(Y, dtype=float)
    d = np.asarray(d, dtype=float)
    w, *_ = np.linalg.lstsq(Y, d, rcond=None)
    return w


def convex_taps(Y: np.ndarray, d: np.ndarray, budget: float = 1.0) -> np.ndarray:
    """minimize ||Y w - d||^2  s.t.  ||w||_1 <= budget, via cvxpy.

    A tap-magnitude budget is a real constraint (tx.py's FFE already
    enforces sum(|tap|) == 1: a TX has a fixed output-swing budget to
    split across taps). `mmse_taps`/`ls_taps` can't express that
    constraint at all; this can, at the cost of needing a solver instead
    of a closed form.
    """
    Y = np.asarray(Y, dtype=float)
    d = np.asarray(d, dtype=float)
    n_taps = Y.shape[1]
    w = cp.Variable(n_taps)
    objective = cp.Minimize(cp.sum_squares(Y @ w - d))
    constraints = [cp.norm1(w) <= budget]
    problem = cp.Problem(objective, constraints)
    # cvxpy's automatic solver choice for this QP (OSQP) was found to report
    # a false "infeasible" on well-conditioned, genuinely-feasible problems
    # here (verified independently against CLARABEL and SCS agreeing on the
    # same optimum OSQP rejected). CLARABEL is cvxpy's own current default
    # recommendation for QPs and solved every case tried; SCS is a fallback
    # for anything CLARABEL itself can't handle.
    problem.solve(solver=cp.CLARABEL)
    if w.value is None:
        problem.solve(solver=cp.SCS)
    if w.value is None:
        raise RuntimeError(f"convex_taps: solver did not find a solution (status={problem.status})")
    return w.value
