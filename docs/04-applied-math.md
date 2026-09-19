# Applied Math In Use

This page exists to make the math/estimation/optimization coursework
behind this repo's design choices *visible*, not just claimed. One block
per result: the formula, the course/book it's from, the code that
implements it, and the plot that proves it.

Started with Workstream 1 (the optimal equalizer) and Workstream 2
(detection-theory BER). A regression surrogate on sweep data and a
Kalman-filter view of CDR phase tracking are follow-on workstreams, not
yet built; see `career/p1-applied-math-extension.txt` (planning repo,
private) for the roadmap.

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

## Workstream 2: the slicer is a MAP detector

**Formula**

The sampler's slicer is choosing between two hypotheses (H0: bit sent =
-1, H1: bit sent = +1) from one noisy observation. The Bayes-optimal
(MAP) rule is the likelihood-ratio test:

```
decide H1  iff  p1 * f1(t) > p0 * f0(t)
```

`ber.py`'s existing `bathtub()` already computes each hypothesis's tail
probability with a Gaussian CDF -- that IS `P(error) = Q((c0 - |ISI|) /
sigma)`, it just wasn't named as detection theory. It also implicitly
assumes the optimal threshold is exactly 0, true only for a **symmetric**
channel (mirrored means, equal noise, equal priors). Solving the
likelihood-ratio equation directly for equal-variance hypotheses gives a
closed form:

```
t* = (mu0 + mu1)/2 + sigma^2/(mu1 - mu0) * ln(p1/p0)
```

which collapses to 0 exactly under symmetry, and to the weighted midpoint
under a DC-offset-style level asymmetry. For unequal variances the
equation is quadratic in `t`; solved numerically here (`scipy.optimize.
brentq`, bracketed between the two means) rather than by hand-selecting
between two algebraic roots.

**Book / course**

EECS126 (binary hypothesis testing / MAP detection, Walrand's
*Probability in Electrical Engineering and Computer Science*).

**Code**

`src/serdeslink/analysis/ber.py`:
- `optimal_threshold(mu0, sigma0, mu1, sigma1, p0, p1)`: the MAP threshold,
  closed-form when variances match, numeric otherwise.
- `error_probability(threshold, mu0, sigma0, mu1, sigma1, p0, p1)`: total
  P(error) at a given threshold, the same Q-function construction
  `bathtub` already uses, generalized so it can be evaluated away from 0.

`bathtub()` and `isi_pdf()` were NOT changed; they remain the right tool
for the symmetric-channel peak-distortion case this repo's channel
actually produces. The new functions are for when that symmetry doesn't
hold.

**Result**

![MAP-optimal threshold vs. the naive assumption](imgs/ber_optimal_threshold.png)

Two asymmetric scenarios, each a real SerDes non-ideality: duty-cycle
distortion (the '0' and '1' levels aren't exact mirrors) and heteroscedastic
noise (different effective sigma on each side, e.g. from unequal residual
ISI). In both, the naive threshold=0 is measurably wrong, and the derived
MAP threshold is a strict improvement with no other change to the link:
10.9x lower error probability under the tested level asymmetry, 34.2x
lower under the tested noise asymmetry. `test_error_probability_matches_
bathtub_in_symmetric_case` checks the new general formula reduces to
`bathtub`'s own existing number for the ordinary symmetric case, so
nothing here contradicts what was already validated.

Reproduce: `python scripts/run_ber_threshold.py`. Tests: `tests/test_ber.py`
(5 tests: symmetric case gives exactly 0, closed-form level-asymmetry
shift, the derived threshold beats naive 0 under noise asymmetry, a
brute-force grid-search cross-check for the no-closed-form case, and
agreement with `bathtub` in the symmetric case).
