"""Sweep CTLE zero placement, measure eye height at the UI center after
equalization, and report the best setting. Importable by run_link.py or
runnable standalone.
"""
from __future__ import annotations

import numpy as np

from serdeslink import link
from serdeslink.analysis import eye as eye_mod


def sweep(waveform, samples_per_ui, ui_sec, zero_hz_list, pole1_hz=5e9, pole2_hz=15e9,
           dc_gain_db=0.0):
    results = []
    for zero_hz in zero_hz_list:
        eq = link.apply_ctle_time_domain(
            waveform, samples_per_ui, ui_sec,
            dc_gain_db=dc_gain_db, zero_hz=zero_hz, pole1_hz=pole1_hz, pole2_hz=pole2_hz,
        )
        t_ui, traces = eye_mod.build_eye_traces(eq, samples_per_ui, ui_span=2)
        height = eye_mod.eye_height(traces)

        freq = np.linspace(1e6, pole2_hz * 1.5, 4001)
        from serdeslink import ctle as ctle_mod
        h = ctle_mod.ctle_response(freq, dc_gain_db=dc_gain_db, zero_hz=zero_hz,
                                    pole1_hz=pole1_hz, pole2_hz=pole2_hz)
        peaking = ctle_mod.peaking_db(freq, h)
        results.append({"zero_hz": zero_hz, "peaking_db": peaking, "eye_height": height})
    return results


if __name__ == "__main__":
    print("Run via scripts/run_link.py. This module is imported, not standalone.")
