"""Synthetic 4-port differential-channel Touchstone generator (scikit-rf).

Stand-in for a real measured board (Stage B / P5 in the master reference).
Builds a differential channel as two identical, UNCOUPLED, lossy microstrip
lines (TX+ -> RX+ and TX- -> RX-) on FR4-like dielectric, assembled into a
4-port single-ended file with port order (1=TX+, 2=TX-, 3=RX+, 4=RX-). This
is the scikit-rf se2gmm(p=2) native ordering that channel.load() assumes. No
differential-mode coupling is modeled (a real coupled pair would show some
common-to-differential conversion). That's an honest simplification worth
calling out, not a measured result.

Swap the file this writes for a real measured .s4p in this folder once one
exists. channel.load() does not need to change.
"""
from __future__ import annotations

import pathlib

import numpy as np
import skrf as rf


def make_synthetic_channel(out_path: str, length_m: float = 12 * 0.0254,
                            freq_start_hz: float = 1e6, freq_stop_hz: float = 15e9,
                            n_points: int = 1001) -> rf.Network:
    freq = rf.Frequency(freq_start_hz / 1e9, freq_stop_hz / 1e9, n_points, unit="GHz")
    # FR4-ish 50-ohm single-ended microstrip: er=4.3, tand=0.02, ~5 mil trace.
    media = rf.media.MLine(
        frequency=freq, z0=50, w=0.127e-3, h=0.127e-3, t=0.035e-3,
        ep_r=4.3, rho=1.7e-8, tand=0.02,
        model="hammerstadjensen", diel="frequencyinvariant",
    )
    line = media.line(length_m, unit="m", name="line")

    s2 = line.s
    n = s2.shape[0]
    s4 = np.zeros((n, 4, 4), dtype=complex)
    # se2gmm(p=2) native order: (port0=TX+, port1=TX-, port2=RX+, port3=RX-).
    # Each physical line's 2-port S-matrix goes into the (in, out) sub-indices
    # for THAT line, not into a contiguous block.
    s4[:, 0, 0] = s2[:, 0, 0]  # TX+ line: S11
    s4[:, 0, 2] = s2[:, 0, 1]  # TX+ -> RX+
    s4[:, 2, 0] = s2[:, 1, 0]  # RX+ -> TX+
    s4[:, 2, 2] = s2[:, 1, 1]  # TX+ line: S22

    s4[:, 1, 1] = s2[:, 0, 0]  # TX- line: S11
    s4[:, 1, 3] = s2[:, 0, 1]  # TX- -> RX-
    s4[:, 3, 1] = s2[:, 1, 0]  # RX- -> TX-
    s4[:, 3, 3] = s2[:, 1, 1]  # TX- line: S22

    ntwk = rf.Network(frequency=freq, s=s4, z0=50, name="synthetic_channel")
    ntwk.write_touchstone(out_path, form="ri")
    return ntwk


if __name__ == "__main__":
    out_dir = pathlib.Path(__file__).parent
    out = out_dir / "synthetic_12in_channel.s4p"
    make_synthetic_channel(str(out))
    print(f"wrote {out}")
