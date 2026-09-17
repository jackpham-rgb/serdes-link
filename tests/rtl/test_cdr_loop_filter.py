"""cocotb testbench for rtl/cdr_loop_filter.sv, compared bit-for-bit against
serdeslink.cdr.loop_filter_step_fixed() (the Stage C fixed-point golden
model) on a REAL phase-detector sequence taken from an actual run_cdr()
bang-bang lock (not a synthetic dummy pattern).

Run directly: `python test_cdr_loop_filter.py`.
Or via pytest: `pytest tests/rtl/test_cdr_loop_filter.py`
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from serdeslink import cdr as cdr_golden  # noqa: E402
from serdeslink import prbs as prbs_mod  # noqa: E402
from serdeslink import tx as tx_mod  # noqa: E402

PI_SUBSTEPS = 256
KP, KI = 0.05, 0.001
PI_STEPS_PER_UI = 64


def to_signed(value: int, width: int) -> int:
    value &= (1 << width) - 1
    if value & (1 << (width - 1)):
        value -= 1 << width
    return value


def _real_pd_sequence():
    """A real bang-bang PD sequence from an actual lock, not synthetic
    filler, so this test exercises the loop filter on realistic pd
    statistics (mostly 0, occasional +-1, biased while locking)."""
    samples_per_ui = 32
    bits = prbs_mod.prbs(11, 4000)
    symbols = tx_mod.nrz_symbols(bits)
    waveform = tx_mod.rise_fall_shape(symbols, ui=1.0, samples_per_ui=samples_per_ui, rise_frac=0.1)
    _, _, pd_out = cdr_golden.run_cdr(
        waveform, samples_per_ui, ppm=200.0, kp=KP, ki=KI, pi_steps_per_ui=PI_STEPS_PER_UI,
    )
    return [int(pd) for pd in pd_out]


@cocotb.test()
async def cdr_loop_filter_matches_golden_model(dut):
    pd_sequence = _real_pd_sequence()

    kp_fixed, ki_fixed = cdr_golden.loop_filter_gains_fixed(KP, KI, PI_STEPS_PER_UI)
    assert int(dut.KP_FIXED.value) == kp_fixed, "RTL KP_FIXED parameter out of sync with the golden model"
    assert int(dut.KI_FIXED.value) == ki_fixed, "RTL KI_FIXED parameter out of sync with the golden model"

    golden_integrator = 0
    golden_correction = 0
    golden_trace = []
    for pd in pd_sequence:
        delta, golden_integrator = cdr_golden.loop_filter_step_fixed(pd, golden_integrator, kp_fixed, ki_fixed)
        golden_correction += delta
        golden_trace.append(golden_correction)

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.en.value = 0
    dut.pd_in.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    dut.en.value = 1

    rtl_trace = []
    for pd in pd_sequence:
        dut.pd_in.value = pd
        await RisingEdge(dut.clk)
        # Sample at the falling edge, not immediately after the rising edge:
        # reading a registered output right after RisingEdge can race the
        # DUT's own non-blocking update for that same edge and see the
        # PRE-edge value (a real bug this caught: see docs/03-rtl.md).
        await FallingEdge(dut.clk)
        rtl_trace.append(to_signed(int(dut.correction_steps.value), 32))

    mismatches = [i for i in range(len(pd_sequence)) if rtl_trace[i] != golden_trace[i]]
    assert not mismatches, (
        f"{len(mismatches)}/{len(pd_sequence)} steps differ from the fixed-point golden "
        f"model; first mismatch at index {mismatches[0]}: "
        f"RTL={rtl_trace[mismatches[0]]} golden={golden_trace[mismatches[0]]}"
    )


def test_cdr_loop_filter_runner():
    from cocotb_tools.runner import get_runner

    kp_fixed, ki_fixed = cdr_golden.loop_filter_gains_fixed(KP, KI, PI_STEPS_PER_UI)

    sim = os.getenv("SIM", "icarus")
    runner = get_runner(sim)
    runner.build(
        sources=[REPO_ROOT / "rtl" / "cdr_loop_filter.sv"],
        hdl_toplevel="cdr_loop_filter",
        parameters={
            "PI_SUBSTEPS": PI_SUBSTEPS,
            "KP_FIXED": kp_fixed,
            "KI_FIXED": ki_fixed,
        },
        build_dir=REPO_ROOT / "tests" / "rtl" / "sim_build" / "cdr_loop_filter",
        always=True,
    )
    runner.test(
        hdl_toplevel="cdr_loop_filter",
        test_module="test_cdr_loop_filter",
        test_dir=Path(__file__).resolve().parent,
    )


if __name__ == "__main__":
    test_cdr_loop_filter_runner()
