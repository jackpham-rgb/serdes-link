"""cocotb testbench for rtl/dfe.sv, compared against serdeslink.dfe.run_dfe()
(the Stage A golden model) run on the SAME quantized inputs.

Methodology: quantize the test samples to the RTL's fixed-point format
first, then run the Python golden model on those quantized-and-back-to-
float values, so both sides see identical discretized inputs. mu is chosen
as a power of two (2^-8) so it is exactly representable in the fixed-point
format, removing tap-update rounding as a source of drift; the only
remaining differences are single-LSB rounding on sample/residual values.

Run directly: `python test_dfe.py`. Or via pytest: `pytest tests/rtl/test_dfe.py`
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from serdeslink import dfe as dfe_golden  # noqa: E402

WIDTH = 16
FRAC = 14
N_TAPS = 4
MU_FIXED = 64  # 2^-8 in Q1.14: 64/16384 = 0.00390625, exact
SCALE = 1 << FRAC
N_SAMPLES = 4000


def to_fixed(x: float) -> int:
    return int(round(x * SCALE))


def from_fixed(x: int) -> float:
    return x / SCALE


def to_signed(value: int, width: int) -> int:
    value &= (1 << width) - 1
    if value & (1 << (width - 1)):
        value -= 1 << width
    return value


@cocotb.test()
async def dfe_matches_golden_model(dut):
    rng = np.random.default_rng(0)
    true_bits = rng.choice([-1.0, 1.0], size=N_SAMPLES)
    c1 = 0.3
    samples = true_bits.copy()
    samples[1:] += c1 * true_bits[:-1]

    # Quantize inputs to the RTL's fixed-point grid, then run the golden
    # model on the SAME quantized values, so both sides see identical data.
    samples_fixed = [to_fixed(s) for s in samples]
    samples_quantized = np.array([from_fixed(v) for v in samples_fixed])
    mu_golden = MU_FIXED / SCALE
    decisions_golden, taps_golden, residual_golden = dfe_golden.run_dfe(
        samples_quantized, n_taps=N_TAPS, mu=mu_golden,
    )

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst_n.value = 0
    dut.en.value = 0
    dut.sample_in.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    dut.en.value = 1

    rtl_decisions = []
    rtl_tap0 = []
    for i in range(N_SAMPLES):
        dut.sample_in.value = samples_fixed[i]
        await RisingEdge(dut.clk)
        # Sample at the falling edge: reading tap0_out (registered) right
        # after RisingEdge can race the DUT's own non-blocking update for
        # that edge (see the same bug caught and documented in
        # test_cdr_loop_filter.py / docs/03-rtl.md). decision_out is
        # combinational so it wasn't affected, but tap0_out is registered.
        await FallingEdge(dut.clk)
        rtl_decisions.append(1.0 if int(dut.decision_out.value) else -1.0)
        rtl_tap0.append(from_fixed(to_signed(int(dut.tap0_out.value), WIDTH)))

    rtl_decisions = np.array(rtl_decisions)
    rtl_tap0 = np.array(rtl_tap0)

    agreement = np.mean(rtl_decisions == decisions_golden)
    assert agreement > 0.99, f"RTL/golden decision agreement only {agreement:.4f}"

    # Tap 0 should track the golden model's tap 0 closely once past the
    # initial transient (both start at 0 and adapt with the same mu).
    tail = slice(N_SAMPLES // 2, None)
    max_tap_diff = np.max(np.abs(rtl_tap0[tail] - taps_golden[tail, 0]))
    assert max_tap_diff < 0.02, f"tap0 diverged from golden model by {max_tap_diff:.4f}"


def test_dfe_runner():
    from cocotb_tools.runner import get_runner

    sim = os.getenv("SIM", "icarus")
    runner = get_runner(sim)
    runner.build(
        sources=[REPO_ROOT / "rtl" / "dfe.sv"],
        hdl_toplevel="dfe",
        parameters={"WIDTH": WIDTH, "FRAC": FRAC, "N_TAPS": N_TAPS, "MU": MU_FIXED},
        build_dir=REPO_ROOT / "tests" / "rtl" / "sim_build" / "dfe",
        always=True,
    )
    runner.test(
        hdl_toplevel="dfe",
        test_module="test_dfe",
        test_dir=Path(__file__).resolve().parent,
    )


if __name__ == "__main__":
    test_dfe_runner()
