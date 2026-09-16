"""One-command Stage A pipeline: load the channel, drive it with a PRBS
waveform, sweep the CTLE, run the DFE and CDR/JTOL, and write every figure to
docs/imgs/ that the README and docs/01-model.md reference.

Run from the repo root:
    python scripts/run_link.py
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
sys.path.insert(0, str(ROOT / "data" / "touchstone"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from serdeslink import channel as channel_mod  # noqa: E402
from serdeslink import dfe as dfe_mod  # noqa: E402
from serdeslink import link  # noqa: E402
from serdeslink.analysis import ber as ber_mod  # noqa: E402
from serdeslink.analysis import eye as eye_mod  # noqa: E402
from serdeslink.analysis import jitter as jitter_mod  # noqa: E402
from sweep_ctle import sweep as sweep_ctle  # noqa: E402
from sweep_jtol import sweep as sweep_jtol  # noqa: E402

IMG_DIR = ROOT / "docs" / "imgs"
DATA_DIR = ROOT / "data" / "touchstone"
CHANNEL_FILE = DATA_DIR / "synthetic_12in_channel.s4p"

# Rbit chosen for LiteVNA-class (~6 GHz) coverage per the project howto
# (Nyquist ~3x within instrument BW) — see docs/00-spec.md. Provisional until
# a real VNA spec locks this number in.
RBIT = 5e9
UI_SEC = 1.0 / RBIT
SAMPLES_PER_UI = 32
N_BITS = 3000
PRBS_ORDER = 15


def ensure_channel_file() -> str:
    if not CHANNEL_FILE.exists():
        from make_synthetic_channel import make_synthetic_channel
        make_synthetic_channel(str(CHANNEL_FILE))
    return str(CHANNEL_FILE)


def fig_closed_eye(waveform, samples_per_ui):
    t_ui, traces = eye_mod.build_eye_traces(waveform, samples_per_ui)
    fig, ax = plt.subplots(figsize=(5, 4))
    eye_mod.plot_eye(ax, t_ui, traces, title='Unequalized channel eye (12" synthetic FR4)')
    fig.tight_layout()
    fig.savefig(IMG_DIR / "closed_eye.png", dpi=150)
    plt.close(fig)
    return eye_mod.eye_height(traces)


def fig_ctle_sweep(waveform, samples_per_ui, ui_sec):
    zero_hz_list = np.geomspace(0.3e9, 4e9, 12)
    results = sweep_ctle(waveform, samples_per_ui, ui_sec, zero_hz_list)
    peaks = [r["peaking_db"] for r in results]
    heights = [r["eye_height"] for r in results]

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(peaks, heights, "o-")
    ax.set_xlabel("realized CTLE peaking (dB)")
    ax.set_ylabel("eye height (a.u.)")
    ax.set_title("CTLE peaking sweep")
    fig.tight_layout()
    fig.savefig(IMG_DIR / "ctle_sweep.png", dpi=150)
    plt.close(fig)

    return max(results, key=lambda r: r["eye_height"])


def fig_dfe(equalized_waveform, samples_per_ui):
    samples = link.sample_ui_centers(equalized_waveform, samples_per_ui)
    decisions, taps_history, residual = dfe_mod.run_dfe(samples, n_taps=4, mu=2e-3)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for k in range(taps_history.shape[1]):
        axes[0].plot(taps_history[:, k], label=f"tap {k + 1}")
    axes[0].set_xlabel("UI")
    axes[0].set_ylabel("tap value")
    axes[0].set_title("DFE tap convergence (sign-sign LMS)")
    axes[0].legend(fontsize=8)

    axes[1].hist(residual[len(residual) // 2:], bins=60)
    axes[1].set_xlabel("sampler residual")
    axes[1].set_title("Residual-ISI histogram (post-DFE)")
    fig.tight_layout()
    fig.savefig(IMG_DIR / "dfe_taps.png", dpi=150)
    plt.close(fig)
    return decisions, taps_history, residual


def fig_jtol_and_lock():
    freq_hz = np.geomspace(1e4, 0.5 * RBIT, 200)
    gain_sets = {
        "kp=0.05 ki=0.001 (default)": (0.05, 0.001),
        "kp=0.02 ki=0.0002 (narrower loop BW)": (0.02, 0.0002),
    }
    curves = sweep_jtol(freq_hz, RBIT, ui_margin=0.3, gain_sets=gain_sets)
    phase_ui, data_bits, pd_out = jitter_mod.demo_lock_acquisition(
        samples_per_ui=SAMPLES_PER_UI, n_bits=4000, ppm=200.0,
    )

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for label, jtol in curves.items():
        axes[0].loglog(freq_hz, jtol, label=label)
    axes[0].set_xlabel("jitter frequency (Hz)")
    axes[0].set_ylabel("tolerable sinusoidal jitter (UI)")
    axes[0].set_title("JTOL (linearized loop model)")
    axes[0].legend(fontsize=7)

    axes[1].plot(phase_ui)
    axes[1].set_xlabel("UI")
    axes[1].set_ylabel("PI correction (UI)")
    axes[1].set_title("CDR lock acquisition, 200 ppm offset")
    fig.tight_layout()
    fig.savefig(IMG_DIR / "jtol_and_lock.png", dpi=150)
    plt.close(fig)


def fig_bathtub(h, dt_channel):
    p = channel_mod.pulse_response(h, dt_channel, UI_SEC)
    main, isi_cursors = channel_mod.cursor_amplitudes(p, dt_channel, UI_SEC)
    thresholds, ber_high, ber_low = ber_mod.bathtub(isi_cursors, sigma_rj=0.05)

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.semilogy(thresholds, np.clip(ber_high, 1e-20, 1), label="sent '1'")
    ax.semilogy(thresholds, np.clip(ber_low, 1e-20, 1), label="sent '0'")
    ax.set_xlabel("decision threshold (normalized to main cursor)")
    ax.set_ylabel("BER")
    ax.set_title("Statistical bathtub (peak-distortion + Gaussian RJ)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMG_DIR / "bathtub.png", dpi=150)
    plt.close(fig)
    return isi_cursors


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    channel_path = ensure_channel_file()

    t, h, freq, sdd21 = channel_mod.load(channel_path)
    dt_channel = t[1] - t[0]
    causality = channel_mod.causality_energy_fraction(h)
    print(f"[channel] loaded {channel_path}; causality energy fraction = {causality:.4f}")

    bits, tx_waveform = link.generate_tx_waveform(
        N_BITS, SAMPLES_PER_UI, order=PRBS_ORDER, ffe=(-0.05, 1.0, (-0.1,)),
    )
    rx_raw = link.drive_channel(tx_waveform, h, dt_channel, SAMPLES_PER_UI, UI_SEC)

    closed_height = fig_closed_eye(rx_raw, SAMPLES_PER_UI)
    print(f"[eye] unequalized eye height = {closed_height:.4f}")

    best_ctle = fig_ctle_sweep(rx_raw, SAMPLES_PER_UI, UI_SEC)
    print(f"[ctle] best setting: {best_ctle}")

    rx_eq = link.apply_ctle_time_domain(
        rx_raw, SAMPLES_PER_UI, UI_SEC, dc_gain_db=0.0, zero_hz=best_ctle["zero_hz"],
    )
    decisions, taps_history, residual = fig_dfe(rx_eq, SAMPLES_PER_UI)
    print(f"[dfe] settled taps = {np.round(taps_history[-1], 4)}")

    fig_jtol_and_lock()

    isi_cursors = fig_bathtub(h, dt_channel)
    print(f"[ber] ISI cursors (normalized to main cursor): {[round(c, 3) for c in isi_cursors]}")

    print(f"\nAll figures written to {IMG_DIR}")


if __name__ == "__main__":
    main()
