"""Applied-math extension, Workstream 2: name the slicer as a MAP detector,
derive its optimal decision threshold from the likelihood ratio, and show
it beats the naive threshold=0 assumption once the channel isn't perfectly
symmetric (asymmetric levels, or asymmetric noise).

Run from the repo root:
    python scripts/run_ber_threshold.py
"""
from __future__ import annotations

import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from serdeslink.analysis import ber  # noqa: E402

IMG_DIR = ROOT / "docs" / "imgs"

CASES = {
    "asymmetric levels\n(duty-cycle distortion)": dict(mu0=-0.7, sigma0=0.2, mu1=1.0, sigma1=0.2),
    "asymmetric noise\n(heteroscedastic)": dict(mu0=-1.0, sigma0=0.1, mu1=1.0, sigma1=0.5),
}


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, len(CASES) + 1, figsize=(4 * (len(CASES) + 1), 4))

    labels, err_naive_list, err_opt_list = [], [], []
    for ax, (label, params) in zip(axes, CASES.items()):
        mu0, sigma0, mu1, sigma1 = params["mu0"], params["sigma0"], params["mu1"], params["sigma1"]
        t_opt = ber.optimal_threshold(mu0, sigma0, mu1, sigma1)
        err_naive = ber.error_probability(0.0, mu0, sigma0, mu1, sigma1)
        err_opt = ber.error_probability(t_opt, mu0, sigma0, mu1, sigma1)

        x = np.linspace(min(mu0, mu1) - 4 * max(sigma0, sigma1), max(mu0, mu1) + 4 * max(sigma0, sigma1), 500)
        ax.plot(x, norm.pdf(x, mu0, sigma0), label="H0 (bit=-1)")
        ax.plot(x, norm.pdf(x, mu1, sigma1), label="H1 (bit=+1)")
        ax.axvline(0.0, color="gray", linestyle="--", label="naive threshold (0)")
        ax.axvline(t_opt, color="C3", linestyle="-", label=f"MAP-optimal ({t_opt:.3f})")
        ax.set_title(label, fontsize=9)
        ax.set_xlabel("sampled amplitude")
        ax.legend(fontsize=6)

        print(f"[{label.splitlines()[0]}] optimal threshold = {t_opt:.4f}, "
              f"P(error) naive = {err_naive:.3e}, P(error) optimal = {err_opt:.3e} "
              f"({err_naive / err_opt:.1f}x improvement)")
        labels.append(label.splitlines()[0])
        err_naive_list.append(err_naive)
        err_opt_list.append(err_opt)

    ax = axes[-1]
    x = np.arange(len(labels))
    width = 0.35
    ax.bar(x - width / 2, err_naive_list, width, label="naive threshold=0")
    ax.bar(x + width / 2, err_opt_list, width, label="MAP-optimal threshold")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("P(error)")
    ax.set_title("A rigorous threshold\nlowers BER for free")
    ax.legend(fontsize=7)

    fig.tight_layout()
    fig.savefig(IMG_DIR / "ber_optimal_threshold.png", dpi=150)
    plt.close(fig)
    print(f"\nFigure written to {IMG_DIR / 'ber_optimal_threshold.png'}")


if __name__ == "__main__":
    main()
