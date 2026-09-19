import numpy as np

from serdeslink import dfe
from serdeslink.analysis import equalizer_opt


def _synthetic_channel(rng, n, taps):
    """samples[i] = bit[i] + sum_k taps[k] * bit[i-1-k]: a known multi-tap
    postcursor channel, the same construction test_dfe.py uses for its
    single-tap case, generalized to n_taps postcursors."""
    true_bits = rng.choice([-1.0, 1.0], size=n)
    samples = true_bits.copy()
    for k, c in enumerate(taps):
        samples[k + 1:] += c * true_bits[: n - k - 1]
    return true_bits, samples


def test_lms_converges_to_mmse_solution():
    rng = np.random.default_rng(2)
    n = 40000
    true_taps = [0.30, -0.15, 0.05]
    true_bits, samples = _synthetic_channel(rng, n, true_taps)

    decisions, taps_history, residual = dfe.run_dfe(samples, n_taps=len(true_taps), mu=2e-3)

    # LMS should have found the exact postcursors (noiseless channel).
    settled_lms = taps_history[-4000:].mean(axis=0)
    assert np.allclose(settled_lms, true_taps, atol=0.03)

    # Closed-form MMSE, from the SAME decisions the settled LMS was using:
    # the DFE regressor is past DECISIONS (see dfe.py / build_regressor_matrix),
    # and its target is the ISI portion of each sample (what the feedback
    # taps should predict to cancel out), samples[i] - true_bits[i].
    burn_in = 4000
    d_used = decisions[burn_in:]
    isi_target = (samples - true_bits)[burn_in:]
    Y = equalizer_opt.build_regressor_matrix(d_used, len(true_taps))
    target = isi_target[len(true_taps):]

    w_mmse = equalizer_opt.mmse_taps(Y, target)
    w_ls = equalizer_opt.ls_taps(Y, target)

    assert np.allclose(w_mmse, true_taps, atol=0.02)
    assert np.allclose(w_ls, w_mmse, atol=1e-6)
    # LMS's own settled taps should match the closed-form optimum, not just
    # the true channel -- this is the actual "LMS converges to MMSE" claim.
    assert np.allclose(settled_lms, w_mmse, atol=0.03)


def test_convex_taps_matches_unconstrained_optimum_when_budget_is_loose():
    rng = np.random.default_rng(3)
    n = 20000
    true_taps = [0.30, -0.15, 0.05]
    true_bits, samples = _synthetic_channel(rng, n, true_taps)
    decisions, _, _ = dfe.run_dfe(samples, n_taps=len(true_taps), mu=2e-3)

    burn_in = 4000
    d_used = decisions[burn_in:]
    isi_target = (samples - true_bits)[burn_in:]
    Y = equalizer_opt.build_regressor_matrix(d_used, len(true_taps))
    target = isi_target[len(true_taps):]

    w_mmse = equalizer_opt.mmse_taps(Y, target)
    loose_budget = float(np.sum(np.abs(w_mmse))) * 10  # far from binding
    w_convex = equalizer_opt.convex_taps(Y, target, budget=loose_budget)

    assert np.allclose(w_convex, w_mmse, atol=0.02)


def test_convex_taps_respects_a_binding_budget():
    rng = np.random.default_rng(4)
    n = 20000
    true_taps = [0.30, -0.15, 0.05]
    true_bits, samples = _synthetic_channel(rng, n, true_taps)
    decisions, _, _ = dfe.run_dfe(samples, n_taps=len(true_taps), mu=2e-3)

    burn_in = 4000
    d_used = decisions[burn_in:]
    isi_target = (samples - true_bits)[burn_in:]
    Y = equalizer_opt.build_regressor_matrix(d_used, len(true_taps))
    target = isi_target[len(true_taps):]

    w_mmse = equalizer_opt.mmse_taps(Y, target)
    tight_budget = float(np.sum(np.abs(w_mmse))) * 0.5  # deliberately binding

    w_convex = equalizer_opt.convex_taps(Y, target, budget=tight_budget)

    assert np.sum(np.abs(w_convex)) <= tight_budget + 1e-4
    # A tighter budget than the unconstrained optimum needs MUST cost
    # something: the constrained solution should fit the data worse.
    err_mmse = np.sum((Y @ w_mmse - target) ** 2)
    err_convex = np.sum((Y @ w_convex - target) ** 2)
    assert err_convex > err_mmse
