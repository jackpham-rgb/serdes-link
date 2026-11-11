"""Draw the link block diagram with the values used in scripts/run_link.py.

Run from the repo root:
    python scripts/make_block_diagram.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from serdeslink.analysis import plotstyle  # noqa: E402

RESULTS = json.loads((ROOT / "docs" / "results.json").read_text())


def block(ax, x, y, w, h, title, lines, color):
    ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor=color, linewidth=1.6))
    ax.add_patch(Rectangle((x, y + h - 0.06), w, 0.06, facecolor=color, edgecolor=color, linewidth=1.6))
    ax.text(x + w / 2, y + h - 0.14, title, ha="center", va="top", fontsize=10.5,
            fontweight="bold", color=plotstyle.INK)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.36 - 0.17 * i, line, ha="center", va="top",
                fontsize=7.6, color=plotstyle.INK, family=plotstyle.MONO)


def arrow(ax, x0, y0, x1, y1, color=None, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=11,
                                 linewidth=1.3, linestyle=ls, color=color or plotstyle.INK,
                                 shrinkA=0, shrinkB=0))


def main():
    plotstyle.apply()
    plt.rcParams["axes.grid"] = False
    fig, ax = plt.subplots(figsize=(13, 4.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 4.6)
    ax.axis("off")

    r = RESULTS
    w, h, y = 1.55, 1.25, 2.55
    xs = [0.2, 2.05, 3.9, 5.75, 7.6, 9.45, 11.3]
    blue, gray, red, teal, amber = plotstyle.BLUE, plotstyle.GRAY, plotstyle.RED, plotstyle.TEAL, plotstyle.AMBER
    spec = [
        ("PRBS15", ["pseudo-random", "32,767-bit period"], gray),
        ("TX FFE", ["2 taps", f"{r['ffe_deemphasis_dB']} dB de-emphasis", f"{r['launch_Vppd']:.0f} Vppd launch"], amber),
        ("Channel", ["36 in FR4", f"{-r['loss_at_nyquist_dB']:.1f} dB @ 2.5 GHz", "synthetic .s4p"], red),
        ("CTLE", [f"zero {r['ctle_zero_GHz']} GHz", f"{r['ctle_peaking_dB']} dB peaking", "poles 3.5, 7.5 GHz"], teal),
        ("Sampler", ["1 sample per bit", "+ edge sample", "for the CDR"], gray),
        ("DFE", ["4 taps", "sign-sign LMS", "subtracts past bits"], blue),
        ("Bits out", ["BER < 1e-15", f"eye {r['steps'][-1]['eye_height_mV']:.0f} mV", f"x {r['steps'][-1]['eye_width_UI']:.2f} UI"], gray),
    ]
    for x, (title, lines, col) in zip(xs, spec):
        block(ax, x, y, w, h, title, lines, col)
    for x0, x1 in zip(xs[:-1], xs[1:]):
        arrow(ax, x0 + w, y + h / 2, x1, y + h / 2)

    # DFE feedback loop into the slicer input
    fb_y = y - 0.32
    ax.plot([xs[5] + w / 2, xs[5] + w / 2], [y, fb_y], color=blue, lw=1.3)
    ax.plot([xs[5] + w / 2, xs[4] + w * 0.75], [fb_y, fb_y], color=blue, lw=1.3)
    arrow(ax, xs[4] + w * 0.75, fb_y, xs[4] + w * 0.75, y, color=blue)
    ax.text((xs[4] + xs[5]) / 2 + w * 0.6, fb_y - 0.16, "decided bits feed back", ha="center",
            fontsize=7.6, color=blue)

    # CDR below the sampler
    cx, cy, cw, ch = xs[4] - 0.2, 0.25, w + 0.4, 1.3
    block(ax, cx, cy, cw, ch, "CDR", ["bang-bang phase detector", "2-path loop filter",
                                      "64-step interpolator", f"tracks {r['cdr_recovered_ppm']:.0f} ppm"], amber)
    arrow(ax, xs[4] + w * 0.25, y, xs[4] + w * 0.25, cy + ch, style="-|>", color=amber)
    ax.text(xs[4] + w * 0.25 - 0.08, (y + cy + ch) / 2, "data and\nedge samples", ha="right",
            va="center", fontsize=7.4, color=amber)
    arrow(ax, cx + cw * 0.85, cy + ch, xs[4] + w * 0.55, y, color=amber)
    ax.text(cx + cw * 0.92, (cy + ch + fb_y) / 2 - 0.05, "when to\nsample", ha="left",
            va="center", fontsize=7.4, color=amber)

    # what is RTL
    rtl = [xs[0], xs[5]]
    for x in rtl:
        ax.add_patch(Rectangle((x - 0.05, y - 0.05), w + 0.1, h + 0.1, fill=False,
                               edgecolor=plotstyle.INK, linewidth=0.9, linestyle=(0, (3, 2))))
    ax.add_patch(Rectangle((cx - 0.05, cy - 0.05), cw + 0.1, ch + 0.1, fill=False,
                           edgecolor=plotstyle.INK, linewidth=0.9, linestyle=(0, (3, 2))))
    ax.plot([0.25, 0.65], [0.45, 0.45], color=plotstyle.INK, lw=0.9, ls=(0, (3, 2)))
    ax.text(0.75, 0.45, "also built in SystemVerilog and checked against the model with cocotb\n"
            "(the CDR's loop filter only; the sampler and interpolator stay analog)",
            va="center", fontsize=7.8, color=plotstyle.INK)

    ax.text(0.2, 4.35, "serdes-link: 5 Gb/s NRZ, transmitter to recovered bits",
            fontsize=12, fontweight="bold", color=plotstyle.INK)
    out = ROOT / "docs" / "imgs" / "block_diagram.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
