"""Compute the linearized JTOL curve for a set of loop-filter gains.
Importable by run_link.py or runnable standalone.
"""
from __future__ import annotations

import numpy as np

from serdeslink.analysis import jitter as jitter_mod


def sweep(freq_hz, ui_rate_hz, ui_margin, gain_sets):
    curves = {}
    for label, (kp, ki) in gain_sets.items():
        curves[label] = jitter_mod.jitter_tolerance(freq_hz, kp, ki, ui_rate_hz, ui_margin)
    return curves


if __name__ == "__main__":
    print("Run via scripts/run_link.py. This module is imported, not standalone.")
