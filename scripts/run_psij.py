"""PDN / power-integrity workstream 1: power-supply-induced jitter (PSIJ).
Show supply ripple turning into edge timing jitter (validated against the
Kvs model), a tracked spur in the CDR's own phase-correction spectrum when
the ripple is inside the loop bandwidth, and the eye closing as ripple
amplitude grows.

Run from the repo root:
    python scripts/run_psij.py
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

from serdeslink.analysis import jitter as jitter_mod  # noqa: E402

IMG_DIR = ROOT / "docs" / "imgs"

RBIT = 5e9
UI_SEC = 1.0 / RBIT
SAMPLES_PER_UI = 32
KVS_PS_PER_MV = 5.0


def fig_eye_closure():
    # Stops at 10 mV deliberately: 2*Kvs*ripple approaches the crossing
    # search window's own width above this, and the measurement saturates
    # (an artifact of the search window, not the physics) -- see
    # docs/05-power-integrity.md.
    ripple_mv_list = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0])
    ripple_freq_hz = 50e6
    spreads = jitter_mod.demo_psij_eye_sweep(
        SAMPLES_PER_UI, UI_SEC, ripple_mv_list, ripple_freq_hz, KVS_PS_PER_MV, n_bits=3000,
    )
    expected_ui = 2 * KVS_PS_PER_MV * ripple_mv_list * 1e-12 / UI_SEC

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(ripple_mv_list, spreads, "o-", label="measured (crossing-time spread)")
    ax.plot(ripple_mv_list, expected_ui, "--", color="gray",
             label="Kvs model: 2*Kvs*ripple")
    ax.set_xlabel("supply ripple amplitude (mV)")
    ax.set_ylabel("horizontal eye closure (UI)")
    ax.set_title(f"PSIJ closes the eye (Kvs={KVS_PS_PER_MV} ps/mV, {ripple_freq_hz/1e6:.0f} MHz ripple)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(IMG_DIR / "psij_eye_closure.png", dpi=150)
    plt.close(fig)

    print(f"[psij] eye closure at {ripple_mv_list[-1]:.0f} mV ripple: {spreads[-1]:.3f} UI "
          f"(model predicts {expected_ui[-1]:.3f} UI)")


def fig_spectrum():
    ripple_mv = 20.0
    below_freq = 1e6
    above_freq = 200e6

    freqs_b, spec_b, wn_hz, zeta = jitter_mod.demo_psij_spectrum(
        SAMPLES_PER_UI, UI_SEC, ripple_mv, below_freq, KVS_PS_PER_MV, n_bits=8000,
    )
    freqs_a, spec_a, _, _ = jitter_mod.demo_psij_spectrum(
        SAMPLES_PER_UI, UI_SEC, ripple_mv, above_freq, KVS_PS_PER_MV, n_bits=8000,
    )

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].semilogy(freqs_b / 1e6, spec_b)
    axes[0].axvline(below_freq / 1e6, color="C1", linestyle="--", label=f"ripple ({below_freq/1e6:.0f} MHz)")
    axes[0].axvline(wn_hz / 1e6, color="gray", linestyle=":", label=f"loop wn ({wn_hz/1e6:.1f} MHz)")
    axes[0].set_xlabel("frequency (MHz)")
    axes[0].set_ylabel("|FFT(phase correction)|")
    axes[0].set_title("Ripple BELOW loop bandwidth: loop tracks it (spur)")
    axes[0].legend(fontsize=7)
    axes[0].set_xlim(0, 5)

    axes[1].semilogy(freqs_a / 1e6, spec_a)
    axes[1].axvline(above_freq / 1e6, color="C1", linestyle="--", label=f"ripple ({above_freq/1e6:.0f} MHz)")
    axes[1].axvline(wn_hz / 1e6, color="gray", linestyle=":", label=f"loop wn ({wn_hz/1e6:.1f} MHz)")
    axes[1].set_xlabel("frequency (MHz)")
    axes[1].set_title("Ripple ABOVE loop bandwidth: loop can't track it\n(shows up as eye closure instead, not a tracked spur)")
    axes[1].legend(fontsize=7)
    axes[1].set_xlim(0, 250)

    fig.tight_layout()
    fig.savefig(IMG_DIR / "psij_spectrum.png", dpi=150)
    plt.close(fig)

    print(f"[psij] loop natural frequency = {wn_hz/1e6:.2f} MHz, zeta = {zeta:.3f}")


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    fig_eye_closure()
    fig_spectrum()
    print(f"\nFigures written to {IMG_DIR}")


if __name__ == "__main__":
    main()
