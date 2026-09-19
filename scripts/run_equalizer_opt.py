"""Applied-math extension, Workstream 1: compare the DFE's adaptive
sign-sign LMS taps against the closed-form MMSE/least-squares optimum and a
budget-constrained convex solution, on a known multi-tap postcursor
channel.

Run from the repo root:
    python scripts/run_equalizer_opt.py
"""
from __future__ import annotations

import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from serdeslink import dfe as dfe_mod  # noqa: E402
from serdeslink.analysis import equalizer_opt  # noqa: E402

IMG_DIR = ROOT / "docs" / "imgs"

TRUE_TAPS = [0.30, -0.15, 0.05]
N = 40000
BURN_IN = 4000


def synthetic_channel(rng, n, taps):
    true_bits = rng.choice([-1.0, 1.0], size=n)
    samples = true_bits.copy()
    for k, c in enumerate(taps):
        samples[k + 1:] += c * true_bits[: n - k - 1]
    return true_bits, samples


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2)
    true_bits, samples = synthetic_channel(rng, N, TRUE_TAPS)

    decisions, taps_history, residual = dfe_mod.run_dfe(samples, n_taps=len(TRUE_TAPS), mu=2e-3)
    lms_taps = taps_history[-4000:].mean(axis=0)

    d_used = decisions[BURN_IN:]
    isi_target = (samples - true_bits)[BURN_IN:]
    Y = equalizer_opt.build_regressor_matrix(d_used, len(TRUE_TAPS))
    target = isi_target[len(TRUE_TAPS):]

    mmse = equalizer_opt.mmse_taps(Y, target)
    ls = equalizer_opt.ls_taps(Y, target)
    loose_budget = float(np.sum(np.abs(mmse))) * 10
    tight_budget = float(np.sum(np.abs(mmse))) * 0.5
    convex_loose = equalizer_opt.convex_taps(Y, target, budget=loose_budget)
    convex_tight = equalizer_opt.convex_taps(Y, target, budget=tight_budget)

    print(f"[equalizer_opt] true taps:        {np.round(TRUE_TAPS, 4)}")
    print(f"[equalizer_opt] LMS settled taps: {np.round(lms_taps, 4)}")
    print(f"[equalizer_opt] MMSE taps:        {np.round(mmse, 4)}")
    print(f"[equalizer_opt] LS taps:          {np.round(ls, 4)}")
    print(f"[equalizer_opt] convex (loose budget={loose_budget:.3f}): {np.round(convex_loose, 4)}")
    print(f"[equalizer_opt] convex (tight budget={tight_budget:.3f}): {np.round(convex_tight, 4)}")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    x = np.arange(len(TRUE_TAPS))
    width = 0.15
    axes[0].bar(x - 2 * width, TRUE_TAPS, width, label="true channel")
    axes[0].bar(x - width, lms_taps, width, label="LMS (adaptive)")
    axes[0].bar(x, mmse, width, label="MMSE (closed form)")
    axes[0].bar(x + width, convex_loose, width, label="convex, loose budget")
    axes[0].bar(x + 2 * width, convex_tight, width, label="convex, tight budget")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([f"tap {k + 1}" for k in x])
    axes[0].set_ylabel("tap value")
    axes[0].set_title("LMS converges to the MMSE optimum")
    axes[0].legend(fontsize=7)

    err_mmse = np.sum((Y @ mmse - target) ** 2) / len(target)
    err_loose = np.sum((Y @ convex_loose - target) ** 2) / len(target)
    err_tight = np.sum((Y @ convex_tight - target) ** 2) / len(target)
    axes[1].bar(["MMSE\n(unconstrained)", f"convex\n(budget={loose_budget:.2f})",
                 f"convex\n(budget={tight_budget:.2f})"],
                [err_mmse, err_loose, err_tight])
    axes[1].set_ylabel("mean squared ISI-prediction error")
    axes[1].set_title("A tap-budget constraint MMSE can't express")
    fig.tight_layout()
    fig.savefig(IMG_DIR / "equalizer_opt.png", dpi=150)
    plt.close(fig)

    print(f"\nFigure written to {IMG_DIR / 'equalizer_opt.png'}")


if __name__ == "__main__":
    main()
