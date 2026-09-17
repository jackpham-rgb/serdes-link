"""cocotb testbench for rtl/prbs_gen.sv, compared bit-for-bit against
serdeslink.prbs.prbs() (the Stage A golden model).

Run directly (builds + simulates with Icarus, then runs the cocotb test
below inside it): `python test_prbs_gen.py`
Or via pytest: `pytest tests/rtl/test_prbs_gen.py`
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

from serdeslink import prbs as prbs_golden  # noqa: E402

ORDER = 15
TAP1, TAP2 = 15, 14
N_BITS = 2000


@cocotb.test()
async def prbs_matches_golden_model(dut):
    golden = prbs_golden.prbs(ORDER, N_BITS)

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.en.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    dut.en.value = 1

    # prbs.py's convention is "read reg&1, THEN shift" (out[i] is captured
    # BEFORE that iteration's update). Index 0 is the reset value, read
    # before any clocked edge (no race possible: nothing is toggling yet).
    # Every later index needs a real edge to have happened AND settled
    # before it's safe to read: sampling right at/after RisingEdge without
    # waiting for FallingEdge is a genuine race against the DUT's own
    # non-blocking update (it silently broke test_cdr_loop_filter.py the
    # same way; see docs/03-rtl.md).
    rtl_bits = [int(dut.out_bit.value)]
    for _ in range(N_BITS - 1):
        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)
        rtl_bits.append(int(dut.out_bit.value))

    mismatches = [i for i in range(N_BITS) if rtl_bits[i] != int(golden[i])]
    assert not mismatches, (
        f"{len(mismatches)}/{N_BITS} bits differ from the Python golden model; "
        f"first mismatch at index {mismatches[0]}"
    )


def test_prbs_gen_runner():
    from cocotb_tools.runner import get_runner

    sim = os.getenv("SIM", "icarus")
    runner = get_runner(sim)
    runner.build(
        sources=[REPO_ROOT / "rtl" / "prbs_gen.sv"],
        hdl_toplevel="prbs_gen",
        parameters={"ORDER": ORDER, "TAP1": TAP1, "TAP2": TAP2},
        build_dir=REPO_ROOT / "tests" / "rtl" / "sim_build" / "prbs_gen",
        always=True,
    )
    runner.test(
        hdl_toplevel="prbs_gen",
        test_module="test_prbs_gen",
        test_dir=Path(__file__).resolve().parent,
    )


if __name__ == "__main__":
    test_prbs_gen_runner()
