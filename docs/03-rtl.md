# Stage C: SystemVerilog + cocotb

## Goal

Reimplement the DFE and the CDR's digital loop filter in synthesizable
SystemVerilog, and prove each one matches the Stage A Python model
(`dfe.py`, `cdr.py`) on the same input vectors, using cocotb to drive real
Icarus Verilog simulations from Python. Also add a PRBS generator in RTL,
since a real link needs a hardware pattern source, not just a Python one.

This stage deliberately does NOT try to reimplement `cdr.py`'s waveform
resampling (`_sample_at`) in hardware. That function stands in for an
analog front end (a real sampler and phase interpolator), which isn't
digital logic. What Stage C implements is the actual digital control:
the PRBS pattern, the DFE, and the CDR's phase-detector-to-correction loop
filter.

## Procedure

1. **Golden-model split** (`src/serdeslink/cdr.py`): added
   `loop_filter_gains_fixed()` and `loop_filter_step_fixed()`, a pure
   fixed-point (integer-only) version of the digital loop filter math that
   was previously inlined inside `run_cdr()`. `run_cdr()` itself is
   untouched; the new functions are additive and separately tested
   (`tests/test_cdr.py::test_fixed_point_loop_filter_tracks_float_run_cdr`)
   to prove they track the existing float behavior before ever touching
   RTL.
2. **`rtl/prbs_gen.sv`**: a Fibonacci LFSR, bit-for-bit matching
   `serdeslink.prbs.prbs()`'s seed, tap positions, and left-shift update.
3. **`rtl/dfe.sv`**: an N-tap sign-sign LMS DFE in Q1.14 fixed point.
   Because both the past decisions and the sign-sign update multiply only
   by +-1, every "multiply" is a conditional add/subtract; there are no
   real multipliers in this design. That's not a simplification I made for
   convenience, it's the actual reason sign-sign LMS gets chosen in real
   hardware.
4. **`rtl/cdr_loop_filter.sv`**: the digital loop filter alone, in pure
   integer fixed point (see "Fixed-point design" below). No floats, no
   dependency on `samples_per_ui` (that's a Stage-A-simulation-only
   concept; real hardware only knows the phase interpolator's own step
   resolution).
5. **`rtl/serdes_digital_top.sv`**: a flat-IO wrapper bundling all three,
   as the eventual P2 (Tiny Tapeout) target.
6. **cocotb testbenches** (`tests/rtl/test_*.py`): each one builds the
   relevant RTL with Icarus Verilog via cocotb's Python runner API
   (`cocotb_tools.runner`, no Makefile needed), drives it with real
   vectors, and compares against the matching golden model. They run as
   ordinary pytest tests (`python -m pytest`) alongside the Stage A suite,
   or standalone (`python tests/rtl/test_dfe.py`).

## Fixed-point design

**DFE**: Q1.14 (16-bit signed, 1 integer bit including sign, 14 fractional
bits), range +-2.0, resolution ~6.1e-5. `mu` for the cosim is chosen as
2^-8 (exactly representable in this format: 64/16384 = 0.00390625 exactly),
so tap-update rounding isn't an extra source of RTL-vs-golden drift beyond
sample/residual quantization itself.

**CDR loop filter**: pure integer, no fractional-bit convention at all.
`kp`/`ki` (Stage A's UI-scale float gains) are converted once, by
`loop_filter_gains_fixed()`, into integers scaled so that 256 "subunits"
equal one phase-interpolator step (1/64 of a UI by default). Concretely:
`kp_fixed = round(kp * pi_steps_per_ui * 256)`. The RTL and the Python
golden model both consume these same pre-rounded integers, so there's a
single rounding step shared by both sides, not two independently-rounded
copies of the same number that could silently drift apart.

## Results

All three cocotb tests pass as part of the normal `pytest` run (18 tests
total: 15 from Stage A, 3 RTL cosims):

- `prbs_gen` matches `serdeslink.prbs.prbs()` bit-for-bit across 2000 bits.
- `dfe` agrees with `run_dfe()` on >99% of decisions across 4000 samples,
  and tap 0 tracks the golden model's tap 0 within 0.02 once past the
  initial transient.
- `cdr_loop_filter` matches `loop_filter_step_fixed()` **exactly**, cycle
  for cycle, across a ~4000-step phase-detector sequence taken from a real
  `run_cdr()` lock (not a synthetic dummy pattern). It's bit-exact because
  both sides do the identical integer arithmetic with no floats anywhere.

## Implementation map

| Piece | Code |
|---|---|
| PRBS generator | `rtl/prbs_gen.sv` |
| DFE | `rtl/dfe.sv` |
| CDR digital loop filter | `rtl/cdr_loop_filter.sv` |
| Flat-IO top (P2 target) | `rtl/serdes_digital_top.sv` |
| CDR fixed-point golden model | `src/serdeslink/cdr.py` (`loop_filter_gains_fixed`, `loop_filter_step_fixed`) |
| cocotb testbenches | `tests/rtl/test_prbs_gen.py`, `test_dfe.py`, `test_cdr_loop_filter.py` |

## What went wrong

Three real bugs, in the order I hit them:

1. **A sign error in the DFE tap-update logic**, caught before it ever ran.
   Deriving `taps -= mu * sign(error) * sign(past[k])` in terms of the two
   sign *bits* (not the +-1 values), it's easy to get the "same sign vs.
   opposite sign" branch backwards. Working through the four-case truth
   table by hand caught an inverted branch before the first simulation run,
   and the DFE cosim then passed immediately.
2. **A race between the testbench and the DUT's own register update.**
   The CDR loop filter test failed with 2007/3998 mismatches on the first run,
   `RTL=0, golden=-3` at step 1. Tracing internal signals showed the
   *combinational* logic (`raw`, `correction_d`) had already updated
   correctly by the time of the read, but the *registered* output
   (`correction_q`) hadn't: reading a cocotb signal immediately after
   `await RisingEdge(dut.clk)` can race the DUT's own non-blocking
   assignment for that same edge and see the pre-edge value. The fix is to
   sample after `await FallingEdge(dut.clk)` instead, well clear of the
   edge. This is a general cocotb hazard, not specific to this module.
3. **The PRBS test had the identical race, and "passed" anyway, which is
   worse than failing.** Applying the same `FallingEdge` fix to
   `test_prbs_gen.py` on the assumption it was equally unsafe there broke
   a previously-passing test (912/2000 mismatches). The reason: `prbs.py`'s
   convention is "read the bit, *then* shift," so the correct read point
   for index *i* is the settled state *before* the i-th edge, not after
   it. Sampling right after an edge (racy or not) was accidentally
   reading the *next* index's value, and the original race had been
   silently canceling that offset out. The real fix reads index 0 from the
   stable reset state (no edge yet, so no race is even possible), then
   for every later index: `await RisingEdge`, `await FallingEdge` (settle
   safely), *then* read. The lesson: a passing test that relies on an
   unsynchronized read after a clock edge isn't evidence of a correct
   testbench, even when the numbers happen to match.

## References

- cocotb docs: https://docs.cocotb.org
- Icarus Verilog: https://github.com/steveicarus/iverilog
- The general cocotb "read right after RisingEdge" hazard: see cocotb's own
  synchronization-primitive docs for `ReadOnly` / `FallingEdge`.
