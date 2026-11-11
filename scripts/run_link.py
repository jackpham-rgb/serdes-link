"""Run the whole link and regenerate the headline results.

Loads the channel, then adds the equalizers one at a time (raw, TX FFE,
CTLE, DFE). For each step it draws the eye from a PRBS15 time-domain
simulation and computes eye height, eye width and BER from the statistical
eye. Writes the figures to docs/imgs/ and the numbers to
docs/results.json and docs/results_table.md.

Run from the repo root:
    python scripts/run_link.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import fftconvolve

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data" / "touchstone"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from serdeslink import channel as channel_mod  # noqa: E402
from serdeslink import ctle as ctle_mod  # noqa: E402
from serdeslink import dfe as dfe_mod  # noqa: E402
from serdeslink import link  # noqa: E402
from serdeslink.analysis import jitter as jitter_mod  # noqa: E402
from serdeslink.analysis import optimize as optimize_mod  # noqa: E402
from serdeslink.analysis import plotstyle  # noqa: E402
from serdeslink.analysis.stateye import best_sampling_index, stat_eye  # noqa: E402
from sweep_jtol import sweep as sweep_jtol  # noqa: E402

IMG_DIR = ROOT / "docs" / "imgs"
CHANNEL_FILE = ROOT / "data" / "touchstone" / "synthetic_36in_channel.s4p"

# ── Link definition ──────────────────────────────────────────────────────
RBIT = 5e9                 # 5 Gb/s NRZ
UI_SEC = 1.0 / RBIT
SAMPLES_PER_UI = 32
LAUNCH_V = 0.5             # +-0.5 V at the transmitter (1 V peak-to-peak differential)
FFE_TAPS = (0.0, 0.834, (-0.166,))   # 2-tap, 3.5 dB de-emphasis
CTLE_POLES = dict(pole1_hz=3.5e9, pole2_hz=7.5e9)
N_DFE = 4
NOISE_MV_RMS = 1.0         # receiver input noise in a 5 GHz band
RJ_UI_RMS = 0.015          # random jitter, 3 ps rms
TARGET_BER = 1e-12
N_BITS = 4000
SKIP_UI = 300              # start-up: channel delay plus equalizer settling
FLAT = dict(zero_hz=1e15, **CTLE_POLES)


def noise_sigma(ctle_kwargs) -> float:
    """White input noise shaped by the CTLE, in volts rms at the slicer."""
    f = np.linspace(0, 100e9, 400001)
    gain = np.trapezoid(np.abs(ctle_mod.ctle_response(f, **ctle_kwargs)) ** 2, f) / RBIT
    return NOISE_MV_RMS * 1e-3 * float(np.sqrt(gain))


def tx_waveform(ffe, n_bits=N_BITS):
    bits, w = link.generate_tx_waveform(n_bits, SAMPLES_PER_UI, order=15, ffe=ffe)
    return bits, LAUNCH_V * w


def pulse_response(h_tx, ffe, ctle_kwargs):
    """Response at the slicer to one isolated '1' bit."""
    pre, main, post = ffe
    taps = np.array([pre, main, *post]) if pre else np.array([main, *post])
    taps = taps / np.sum(np.abs(taps))
    n_ui = 300
    x = np.zeros(n_ui * SAMPLES_PER_UI)
    for k, c in enumerate(taps):
        x[(k + 4) * SAMPLES_PER_UI:(k + 5) * SAMPLES_PER_UI] += c
    rise = max(1, int(round(0.2 * SAMPLES_PER_UI)))
    win = np.hanning(2 * rise + 1)
    x = np.convolve(x, win / win.sum(), mode="same")
    p = LAUNCH_V * fftconvolve(x, h_tx, mode="full")[: len(x)]
    return link.apply_ctle_time_domain(p, SAMPLES_PER_UI, UI_SEC, **ctle_kwargs)


def simulate(h_tx, ffe, ctle_kwargs):
    bits, w = tx_waveform(ffe)
    rx = fftconvolve(w, h_tx, mode="full")[: len(w)]
    return bits, link.apply_ctle_time_domain(rx, SAMPLES_PER_UI, UI_SEC, **ctle_kwargs)


def eye_traces(rx, phase, correction=None):
    """2-UI traces with the data sampling instant at 0.5 and 1.5 UI."""
    spu = SAMPLES_PER_UI
    start = SKIP_UI * spu + (phase - spu // 2) % spu
    w = rx if correction is None else rx - correction
    n = (len(w) - start) // spu - 2
    return np.stack([w[start + i * spu: start + (i + 2) * spu] for i in range(n)])


def dfe_correction(rx, phase):
    """Run the adaptive DFE on the UI-spaced samples and build the waveform
    it subtracts (each tap held for one UI around the sampling instant)."""
    spu = SAMPLES_PER_UI
    samples = rx[phase % spu::spu]
    scale = np.mean(np.abs(samples[SKIP_UI:]))
    decisions, taps_hist, _ = dfe_mod.run_dfe(samples / scale, n_taps=N_DFE, mu=1e-3)
    taps = taps_hist[-500:].mean(axis=0) * scale
    fb = np.zeros(len(samples))
    for k in range(N_DFE):
        fb[k + 1:] += taps[k] * decisions[: len(samples) - k - 1]
    corr = np.repeat(fb, spu)
    corr = np.roll(corr, phase % spu - spu // 2)[: len(rx)]
    return corr, taps, taps_hist * scale, decisions


def count_errors(rx, phase, bits, correction=None):
    spu = SAMPLES_PER_UI
    w = rx if correction is None else rx - correction
    rx_bits = (w[phase % spu::spu] > 0).astype(int)[SKIP_UI:]
    best = len(rx_bits)
    for lag in range(0, 80):
        ref = bits[SKIP_UI - lag: SKIP_UI - lag + len(rx_bits)]
        n = min(len(ref), len(rx_bits))
        best = min(best, int(np.sum(ref[:n] != rx_bits[:n])))
    return best, len(rx_bits)


def plot_eye(ax, traces, title, sub):
    spu = SAMPLES_PER_UI
    t = np.tile(np.linspace(0, 2, 2 * spu, endpoint=False), len(traces))
    lim = 1.15 * np.percentile(np.abs(traces), 99.9)
    ax.hist2d(t, traces.ravel() * 1e3, bins=[2 * spu, 160],
              range=[[0, 2], [-lim * 1e3, lim * 1e3]], cmap=plotstyle.EYE_CMAP, cmin=1)
    ax.set_title(title, loc="left")
    ax.text(0.02, 0.03, sub, transform=ax.transAxes, fontsize=8, color=plotstyle.INK,
            family=plotstyle.MONO, va="bottom")
    ax.set_xlabel("time (UI)")


def main():
    warnings.filterwarnings("ignore")
    plotstyle.apply()
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    if not CHANNEL_FILE.exists():
        from make_synthetic_channel import make_synthetic_channel
        make_synthetic_channel(str(CHANNEL_FILE))

    t, h, freq, sdd21 = channel_mod.load(str(CHANNEL_FILE))
    dt_ch = t[1] - t[0]
    dt_tx = UI_SEC / SAMPLES_PER_UI
    t_ch = np.arange(len(h)) * dt_ch
    h_tx = np.interp(np.arange(0, t_ch[-1], dt_tx), t_ch, h) * (dt_tx / dt_ch)
    loss_nyq = 20 * np.log10(abs(sdd21[np.argmin(abs(freq - RBIT / 2))]))
    print(f"[channel] loss at Nyquist ({RBIT/2e9:.1f} GHz) = {loss_nyq:.1f} dB, "
          f"causality fraction = {channel_mod.causality_energy_fraction(h):.4f}")

    # ── CTLE sweep (with the FFE on): pick the zero that gives the tallest eye at 1e-12
    fr = np.linspace(1e6, 40e9, 4001)
    sweep = []
    for fz in np.geomspace(0.3e9, 4e9, 15):
        kw = dict(zero_hz=fz, **CTLE_POLES)
        p = pulse_response(h_tx, FFE_TAPS, kw)
        se = stat_eye(p, best_sampling_index(p, SAMPLES_PER_UI), SAMPLES_PER_UI,
                      noise_sigma(kw), RJ_UI_RMS, target_ber=TARGET_BER)
        sweep.append((fz, ctle_mod.peaking_db(fr, ctle_mod.ctle_response(fr, **kw)), se["eye_height"]))
    best_fz, best_pk, _ = max(sweep, key=lambda r: r[2])
    ctle_best = dict(zero_hz=best_fz, **CTLE_POLES)
    pk = np.array([r[1] for r in sweep]); hh = np.array([r[2] for r in sweep]) * 1e3
    near = hh > 0.5 * hh.max()
    fit_pk, fit_h, coeffs = optimize_mod.fit_optimal_peaking(pk[near], hh[near])

    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    ax.plot(pk, hh, "o", color=plotstyle.BLUE, label="swept settings")
    if fit_pk is not None:
        xs = np.linspace(pk[near].min(), pk[near].max(), 100)
        ax.plot(xs, np.polyval(coeffs, xs), color=plotstyle.GRAY, label="quadratic fit near the peak")
        ax.axvline(fit_pk, color=plotstyle.RED, lw=1, ls="--", label=f"fitted optimum {fit_pk:.1f} dB")
    ax.set_xlabel("CTLE peaking (dB)"); ax.set_ylabel("eye height at 1e-12 (mV)")
    ax.set_title("Too little peaking leaves ISI, too much adds noise", loc="left")
    ax.legend()
    fig.savefig(IMG_DIR / "ctle_sweep.png"); plt.close(fig)

    # ── The four steps
    steps = [
        ("Raw channel", (0.0, 1.0, ()), FLAT, 0),
        ("+ TX FFE", FFE_TAPS, FLAT, 0),
        ("+ CTLE", FFE_TAPS, ctle_best, 0),
        ("+ DFE", FFE_TAPS, ctle_best, N_DFE),
    ]
    results, eyes, bathtubs = [], [], []
    dfe_info = None
    for name, ffe, kw, n_dfe in steps:
        p = pulse_response(h_tx, ffe, kw)
        idx = best_sampling_index(p, SAMPLES_PER_UI, 0)
        se = stat_eye(p, idx, SAMPLES_PER_UI, noise_sigma(kw), RJ_UI_RMS, n_dfe=n_dfe, target_ber=TARGET_BER)
        bits, rx = simulate(h_tx, ffe, kw)
        # the pulse was launched 4 UI into its buffer; the waveform has the same phase modulo one UI
        phase = idx % SAMPLES_PER_UI
        corr = None
        if n_dfe:
            corr, taps, taps_hist, _ = dfe_correction(rx, phase)
            cursors = se["cursors"][7:7 + N_DFE]
            dfe_info = (taps, taps_hist, cursors)
        errs, n_checked = count_errors(rx, phase, bits, corr)
        eyes.append(eye_traces(rx, phase, corr))
        bathtubs.append((name, se["phases_ui"], se["ber_vs_phase"]))
        results.append({
            "step": name,
            "eye_height_mV": round(se["eye_height"] * 1e3, 1),
            "eye_width_UI": round(se["eye_width_ui"], 2),
            "ber": float(se["ber_center"]),
            "sim_bit_errors": errs,
            "sim_bits": n_checked,
        })
        print(f"[{name:12s}] eye {se['eye_height']*1e3:6.1f} mV x {se['eye_width_ui']:.2f} UI, "
              f"BER {se['ber_center']:.1e}, simulation {errs}/{n_checked} bit errors")

    def ber_text(b):
        return "< 1e-15" if b < 1e-15 else f"{b:.0e}"

    fig, axes = plt.subplots(1, 4, figsize=(13, 3.4), sharey=False)
    for ax, tr, r in zip(axes, eyes, results):
        sub = f"{r['eye_height_mV']:.0f} mV x {r['eye_width_UI']:.2f} UI\nBER {ber_text(r['ber'])}"
        plot_eye(ax, tr, r["step"], sub)
    axes[0].set_ylabel("voltage at the slicer (mV)")
    fig.suptitle(f"5 Gb/s over 36 in of FR4 ({-loss_nyq:.0f} dB loss at Nyquist): the eye after each equalizer",
                 x=0.01, ha="left", fontsize=11)
    fig.savefig(IMG_DIR / "eye_steps.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    for (name, ph, b), col in zip(bathtubs, plotstyle.SERIES):
        ax.semilogy(ph, np.clip(b, 1e-18, 1), color=col, label=name)
    ax.axhline(TARGET_BER, color=plotstyle.GRAY, lw=0.8, ls=":")
    ax.set_ylim(1e-18, 1); ax.set_xlabel("sampling phase (UI from eye center)"); ax.set_ylabel("BER")
    ax.set_title("Bathtub: how far the sampling clock can drift", loc="left")
    ax.legend()
    ax.tick_params(axis="y", which="both", labelfontfamily="DejaVu Sans")
    fig.savefig(IMG_DIR / "bathtub.png"); plt.close(fig)

    taps, taps_hist, cursors = dfe_info
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for k in range(N_DFE):
        axes[0].plot(taps_hist[:, k] * 1e3, color=plotstyle.SERIES[k], label=f"tap {k + 1}")
        axes[0].axhline(cursors[k] * 1e3, color=plotstyle.SERIES[k], lw=0.8, ls=":")
    axes[0].set_xlabel("bits"); axes[0].set_ylabel("tap weight (mV)")
    axes[0].set_title("DFE taps adapt (dotted: pulse-response value)", loc="left"); axes[0].legend(ncol=2)
    x = np.arange(N_DFE)
    axes[1].bar(x - 0.2, cursors * 1e3, 0.4, color=plotstyle.GRAY, label="postcursor from pulse response")
    axes[1].bar(x + 0.2, taps * 1e3, 0.4, color=plotstyle.BLUE, label="adapted tap (sign-sign LMS)")
    axes[1].set_xticks(x); axes[1].set_xticklabels([f"tap {k + 1}" for k in x]); axes[1].set_ylabel("mV")
    axes[1].set_title("They land on the ISI they must cancel", loc="left"); axes[1].legend()
    fig.savefig(IMG_DIR / "dfe_taps.png"); plt.close(fig)

    # ── Channel figure
    p_raw = pulse_response(h_tx, (0.0, 1.0, ()), FLAT)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    axes[0].plot(freq / 1e9, 20 * np.log10(np.abs(sdd21)), color=plotstyle.BLUE)
    axes[0].axvline(RBIT / 2e9, color=plotstyle.RED, lw=1, ls="--")
    axes[0].text(RBIT / 2e9 + 0.2, -3, f"Nyquist: {loss_nyq:.1f} dB", color=plotstyle.RED, fontsize=8)
    axes[0].set_xlim(0, 10); axes[0].set_ylim(-45, 0)
    axes[0].set_xlabel("frequency (GHz)"); axes[0].set_ylabel("differential insertion loss (dB)")
    axes[0].set_title("Channel: 36 in FR4 microstrip", loc="left")
    i0 = best_sampling_index(p_raw, SAMPLES_PER_UI)
    tt = (np.arange(len(p_raw)) - i0) / SAMPLES_PER_UI
    sel = (tt > -4) & (tt < 12)
    axes[1].plot(tt[sel], p_raw[sel] * 1e3, color=plotstyle.BLUE)
    ks = np.arange(-3, 11)
    axes[1].plot(ks, p_raw[i0 + ks * SAMPLES_PER_UI] * 1e3, "o", color=plotstyle.RED, ms=4)
    axes[1].set_xlabel("time (UI)"); axes[1].set_ylabel("mV")
    axes[1].set_title("One bit smears across many bit slots", loc="left")
    fig.savefig(IMG_DIR / "channel.png"); plt.close(fig)

    # ── CDR
    freq_hz = np.geomspace(1e4, 0.5 * RBIT, 200)
    gains = {"kp=0.05, ki=0.001": (0.05, 0.001), "kp=0.02, ki=0.0002": (0.02, 0.0002)}
    width = results[-1]["eye_width_UI"]
    curves = sweep_jtol(freq_hz, RBIT, ui_margin=width / 2, gain_sets=gains)
    phase_ui, _, _ = jitter_mod.demo_lock_acquisition(samples_per_ui=SAMPLES_PER_UI, n_bits=4000, ppm=200.0)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for (label, jt), col in zip(curves.items(), plotstyle.SERIES):
        axes[0].loglog(freq_hz, jt, color=col, label=label)
    axes[0].set_xlabel("jitter frequency (Hz)"); axes[0].set_ylabel("tolerated jitter amplitude (UI)")
    axes[0].set_title("Jitter tolerance (linearized loop)", loc="left"); axes[0].legend()
    axes[1].plot(phase_ui, color=plotstyle.BLUE)
    slope = np.polyfit(np.arange(2000, 4000 - 2), phase_ui[2000:], 1)[0]
    axes[1].set_xlabel("bits"); axes[1].set_ylabel("phase correction (UI)")
    axes[1].set_title(f"CDR tracks a 200 ppm offset ({slope*1e6:.0f} ppm recovered)", loc="left")
    axes[0].tick_params(which="both", labelfontfamily="DejaVu Sans")
    fig.savefig(IMG_DIR / "jtol_and_lock.png"); plt.close(fig)

    summary = {
        "bit_rate_gbps": RBIT / 1e9, "channel": "36 in FR4 microstrip (synthetic)",
        "loss_at_nyquist_dB": round(float(loss_nyq), 1),
        "launch_Vppd": 2 * LAUNCH_V, "ffe_deemphasis_dB": 3.5,
        "ctle_zero_GHz": round(best_fz / 1e9, 2), "ctle_peaking_dB": round(float(best_pk), 1),
        "dfe_taps_mV": [round(float(v) * 1e3, 1) for v in taps],
        "noise_mV_rms": NOISE_MV_RMS, "rj_UI_rms": RJ_UI_RMS, "target_ber": TARGET_BER,
        "cdr_recovered_ppm": round(float(-slope * 1e6), 1),
        "steps": results,
    }
    (ROOT / "docs" / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["| Step | Eye height at 1e-12 | Eye width at 1e-12 | BER at eye center | Bit errors in simulation |",
             "|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['step']} | {r['eye_height_mV']:.0f} mV | {r['eye_width_UI']:.2f} UI | "
                     f"{ber_text(r['ber'])} | {r['sim_bit_errors']} of {r['sim_bits']} |")
    (ROOT / "docs" / "results_table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n[ctle] best zero {best_fz/1e9:.2f} GHz, {best_pk:.1f} dB peaking; DFE taps (mV) {summary['dfe_taps_mV']}")


if __name__ == "__main__":
    main()
