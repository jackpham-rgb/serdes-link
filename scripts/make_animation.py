"""Animate the link: the same bits sent four times, adding one equalizer each
time, while the received waveform scrolls by and the eye builds up.

Uses the link simulation in scripts/run_link.py. Run from the repo root:
    python scripts/make_animation.py
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
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_link as rl  # noqa: E402
from serdeslink import channel as channel_mod  # noqa: E402
from serdeslink.analysis import plotstyle  # noqa: E402
from serdeslink.analysis.stateye import best_sampling_index  # noqa: E402

RESULTS = json.loads((rl.ROOT / "docs" / "results.json").read_text())
SPU = rl.SAMPLES_PER_UI
WINDOW_UI = 16          # bits visible in the scrolling trace
FRAMES_PER_STEP = 20
HOLD = 10               # extra frames to pause on the finished eye

CAPTIONS = [
    "Raw: the long trace smears each bit into its neighbors. The eye is shut.",
    "+ TX FFE: the transmitter pre-shapes each bit edge. Still shut, but closer.",
    "+ CTLE: the receiver boosts high frequencies back up. The eye opens.",
    "+ DFE: decided bits are used to cancel their leftover tails. Wider still.",
]
BLOCKS = ["TX FFE", "Channel", "CTLE", "DFE"]
ON = [{"Channel"}, {"TX FFE", "Channel"}, {"TX FFE", "Channel", "CTLE"}, set(BLOCKS)]


def build_steps():
    t, h, _, _ = channel_mod.load(str(rl.CHANNEL_FILE))
    dt_ch, dt_tx = t[1] - t[0], rl.UI_SEC / SPU
    t_ch = np.arange(len(h)) * dt_ch
    h_tx = np.interp(np.arange(0, t_ch[-1], dt_tx), t_ch, h) * (dt_tx / dt_ch)
    ctle = dict(zero_hz=RESULTS["ctle_zero_GHz"] * 1e9, **rl.CTLE_POLES)
    cfg = [((0.0, 1.0, ()), rl.FLAT, 0), (rl.FFE_TAPS, rl.FLAT, 0),
           (rl.FFE_TAPS, ctle, 0), (rl.FFE_TAPS, ctle, rl.N_DFE)]
    steps = []
    for ffe, kw, n_dfe in cfg:
        p = rl.pulse_response(h_tx, ffe, kw)
        phase = best_sampling_index(p, SPU, 0) % SPU
        bits, rx = rl.simulate(h_tx, ffe, kw)
        corr = rl.dfe_correction(rx, phase)[0] if n_dfe else None
        w = rx if corr is None else rx - corr
        # find the channel delay in bits, so the sent bits line up with the received ones
        rx_bits = (w[phase::SPU] > 0).astype(int)
        lag = min(range(80), key=lambda L: np.sum(bits[rl.SKIP_UI - L: rl.SKIP_UI - L + 2000]
                                                   != rx_bits[rl.SKIP_UI: rl.SKIP_UI + 2000]))
        steps.append(dict(w=w, phase=phase, bits=bits, lag=lag, traces=rl.eye_traces(rx, phase, corr)))
    return steps


def shrink(path, colors=48):
    """Re-save the GIF with one small shared palette (about half the size)."""
    from PIL import Image, ImageSequence
    im = Image.open(path)
    frames, durs = [], []
    for f in ImageSequence.Iterator(im):
        durs.append(f.info.get("duration", 100))
        frames.append(f.convert("RGB"))
    pal = frames[-1].quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=durs, loop=0, optimize=True)


def main():
    warnings.filterwarnings("ignore")
    plotstyle.apply()
    plt.rcParams["axes.grid"] = False
    steps = build_steps()
    lim = 1.15 * max(np.percentile(np.abs(s["traces"]), 99.9) for s in steps) * 1e3

    fig = plt.figure(figsize=(10, 4.8), dpi=72)
    ax_chain = fig.add_axes([0.02, 0.80, 0.96, 0.17])
    ax_wave = fig.add_axes([0.07, 0.17, 0.55, 0.50])
    ax_eye = fig.add_axes([0.70, 0.17, 0.27, 0.50])
    cap = fig.text(0.02, 0.03, "", fontsize=10, color=plotstyle.INK)
    colors = {"TX FFE": plotstyle.AMBER, "Channel": plotstyle.RED, "CTLE": plotstyle.TEAL, "DFE": plotstyle.BLUE}

    def draw_chain(k):
        ax_chain.clear(); ax_chain.axis("off"); ax_chain.set_xlim(0, 10); ax_chain.set_ylim(0, 1)
        xs = [0.1, 2.25, 4.4, 6.55]
        for x, name in zip(xs, BLOCKS):
            on = name in ON[k]
            c = colors[name] if on else "#c9cdd2"
            ax_chain.add_patch(FancyBboxPatch((x, 0.2), 1.9, 0.6, boxstyle="round,pad=0.02",
                                              facecolor=c if on else "white", edgecolor=c, lw=1.6))
            ax_chain.text(x + 0.95, 0.5, name if on else f"{name} (off)", ha="center", va="center",
                          fontsize=10, color="white" if on else "#9aa1a9", fontweight="bold")
        for x0, x1 in zip(xs[:-1], xs[1:]):
            ax_chain.annotate("", (x1, 0.5), (x0 + 1.9, 0.5),
                              arrowprops=dict(arrowstyle="-|>", color=plotstyle.INK, lw=1.2))
        ax_chain.text(9.3, 0.5, f"step {k + 1} of 4", ha="center", va="center", fontsize=10, color=plotstyle.GRAY)

    total = FRAMES_PER_STEP + HOLD

    def frame(i):
        k, j = divmod(i, total)
        j = min(j, FRAMES_PER_STEP - 1)
        s = steps[k]
        if i % total == 0:
            draw_chain(k)
            cap.set_text(CAPTIONS[k])

        # scrolling waveform at the slicer, with the bits that were sent
        start_ui = rl.SKIP_UI + 3 * j
        a = start_ui * SPU + s["phase"] - SPU // 2
        seg = s["w"][a: a + WINDOW_UI * SPU] * 1e3
        tt = np.arange(len(seg)) / SPU
        sent = s["bits"][start_ui - s["lag"]: start_ui - s["lag"] + WINDOW_UI]
        ax_wave.clear()
        ax_wave.step(np.arange(WINDOW_UI + 1), np.r_[sent, sent[-1]] * 2 * lim * 0.85 - lim * 0.85,
                     where="post", color="#c9cdd2", lw=1.2, label="bits sent")
        ax_wave.plot(tt, seg, color=plotstyle.BLUE, lw=1.6, label="signal at the receiver")
        ax_wave.axhline(0, color=plotstyle.GRAY, lw=0.8, ls="--")
        ax_wave.text(WINDOW_UI - 0.1, lim * 0.04, "above = 1, below = 0", ha="right", va="bottom", fontsize=7.5, color=plotstyle.GRAY)
        for n in range(WINDOW_UI):
            got = int(seg[n * SPU + SPU // 2] > 0)
            ax_wave.plot(n + 0.5, seg[n * SPU + SPU // 2], "o", ms=4,
                         color=plotstyle.TEAL if got == sent[n] else plotstyle.RED)
        ax_wave.set_xlim(0, WINDOW_UI); ax_wave.set_ylim(-lim, lim)
        ax_wave.set_xlabel("time (bits)"); ax_wave.set_ylabel("mV")
        ax_wave.set_title("dots: where the receiver reads each bit (red = read wrong)", loc="right", fontsize=8.5, color=plotstyle.GRAY)
        ax_wave.legend(loc="lower left", bbox_to_anchor=(0, 1.08), fontsize=8.5, frameon=False, ncol=2)

        # eye: overlay every received bit, more of them each frame
        n = max(20, int(len(s["traces"]) * (j + 1) / FRAMES_PER_STEP))
        tr = s["traces"][:n]
        ax_eye.clear()
        t2 = np.tile(np.linspace(0, 2, 2 * SPU, endpoint=False), len(tr))
        ax_eye.hist2d(t2, tr.ravel() * 1e3, bins=[SPU, 70], range=[[0, 2], [-lim, lim]],
                      cmap=plotstyle.EYE_CMAP, cmin=1)
        r = RESULTS["steps"][k]
        ax_eye.set_title(f"eye: {r['eye_height_mV']:.0f} mV tall, {r['eye_width_UI']:.2f} UI wide",
                         loc="left", fontsize=9.5)
        ax_eye.set_xlabel("time (UI)"); ax_eye.set_yticks([])
        return []

    anim = FuncAnimation(fig, frame, frames=4 * total, blit=False)
    out = rl.IMG_DIR / "link_animation.gif"
    anim.save(out, writer=PillowWriter(fps=10))
    plt.close(fig)
    shrink(out)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
