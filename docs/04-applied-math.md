# Applied Math In Use

This page exists to make the math/estimation/optimization coursework
behind this repo's design choices *visible*, not just claimed. One block
per result: the formula, the course/book it's from, the code that
implements it, and the plot that proves it.

Started with Workstream 1 (the optimal equalizer). Detection-theory BER,
a regression surrogate on sweep data, and a Kalman-filter view of CDR
phase tracking are follow-on workstreams, not yet built; see
`career/p1-applied-math-extension.txt` (planning repo, private) for the
roadmap.

## Workstream 1: the optimal equalizer (MMSE / least squares / convex)

**Formula**

MMSE / Wiener-Hopf estimation:

```
w* = R^-1 p,   R = E[y y^T]  (regressor autocorrelation)
               p = E[y d]    (regressor / desired-value cross-correlation)
```

which is the same object as ordinary least squares:

```
minimize ||Y w - d||^2   ->   w = (Y^T Y)^-1 Y^T d
```

and, with a tap-magnitude budget added (a real constraint: a TX has a fixed
output-swing budget to split across taps, exactly what `tx.py`'s
`sum(|tap|) == 1` FFE normalization already enforces elsewhere in this
repo):

```
minimize ||Y w - d||^2   s.t.  ||w||_1 <= budget      (a convex QP)
```

**Book / course**

EECS126 (linear least-squares estimation / MMSE), EECS127 + Boyd &
Vandenberghe's *Convex Optimization* ch. 4 (least squares, convex
constraints), 16A/16B (linear algebra, normal equations).

**Code**

`src/serdeslink/analysis/equalizer_opt.py`:
- `build_regressor_matrix(decisions, n_taps)`: the DFE's own regressor,
  past decisions ordered most-recent-first, exactly matching `dfe.py`'s
  `past` tap-history convention.
- `mmse_taps(Y, d)`: solves `R w = p` directly.
- `ls_taps(Y, d)`: the same optimum via `numpy.linalg.lstsq` (more robust
  when `R` is close to singular).
- `convex_taps(Y, d, budget)`: the same objective with an L1 tap-budget
  constraint, via `cvxpy` (solved with CLARABEL; see the code comment for
  why the default solver was swapped out).

`dfe.py`'s `run_dfe` was NOT changed. It already existed and already runs
sign-sign LMS; this workstream shows what LMS is converging toward,
computed independently, next to it.

**Result**

![Equalizer taps: LMS vs. MMSE vs. convex](imgs/equalizer_opt.png)

On a known 3-tap postcursor channel (`0.30, -0.15, 0.05`, noiseless so the
optimum is exactly solvable), the settled sign-sign LMS taps
(`0.2996, -0.1498, 0.0505`) match the closed-form MMSE solution
(`0.3000, -0.1500, 0.0500`) to within LMS's own steady-state dither, not
just the true channel value — this is the literal "LMS converges to MMSE"
claim, checked directly rather than assumed. `ls_taps` agrees with
`mmse_taps` to numerical precision. `convex_taps` with a loose budget
reproduces the same optimum; with a budget tight enough to bind
(half the unconstrained solution's L1 norm), it's forced to give up some
of tap 3 entirely, and its mean-squared ISI-prediction error is measurably
worse than the unconstrained optimum's, exactly demonstrating a real
constraint a closed-form formula can't express but a solver can.

Reproduce: `python scripts/run_equalizer_opt.py`. Tests:
`tests/test_equalizer_opt.py` (3 tests: LMS-vs-MMSE agreement, convex
matches the unconstrained optimum when the budget is loose, convex
respects a binding budget and pays for it in fit error).
