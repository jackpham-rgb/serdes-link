# rtl/: Stage C (done)

SystemVerilog reimplementation of the PRBS generator, the DFE, and the
CDR's digital loop filter, cosimulated against the Python golden models in
`src/serdeslink/` via cocotb. See [docs/03-rtl.md](../docs/03-rtl.md) for
the full writeup, and `tests/rtl/` for the cocotb testbenches (they run as
part of the normal `pytest` suite).

Files:
- `prbs_gen.sv`: Fibonacci LFSR, matches `serdeslink.prbs.prbs()`.
- `dfe.sv`: N-tap sign-sign LMS DFE, Q1.14 fixed point.
- `cdr_loop_filter.sv`: the CDR's digital loop filter only (not the
  waveform resampling `run_cdr()` does in Python), pure integer fixed
  point.
- `serdes_digital_top.sv`: flat-IO wrapper bundling all three, the
  eventual P2 (Tiny Tapeout) target.

Requires [Icarus Verilog](https://github.com/steveicarus/iverilog) on your PATH and
`cocotb` (in `requirements.txt`).
