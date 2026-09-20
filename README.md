# serdes-link

A high-speed serial link, modeled end to end in Python: a lossy channel, TX
equalization, a CTLE, a DFE, and a bang-bang CDR. It closes the loop between
"here's a closed eye" and "here's what each stage bought back."

![Closed eye](docs/imgs/closed_eye.png)

## What's here (Stage A + Stage C)

- `src/serdeslink/channel.py`: loads a 4-port Touchstone file and extracts
  the differential-mode impulse response (DC-extrapolated, causality-checked).
- `src/serdeslink/prbs.py`, `tx.py`: PRBS15 -> NRZ -> FFE -> pulse shaping.
- `src/serdeslink/ctle.py`: single-zero/two-pole CTLE, swept for peaking.
- `src/serdeslink/dfe.py`: 4-tap sign-sign LMS DFE (pure array function; this
  becomes the Stage C cocotb golden model).
- `src/serdeslink/cdr.py`: closed-loop bang-bang (Alexander) CDR. Phase
  detector, 2nd-order digital loop filter, and finite-resolution PI, run
  bit-level on an oversampled waveform with an injected ppm offset.
- `src/serdeslink/analysis/`: eye diagrams, statistical BER (peak-distortion
  method, plus `optimal_threshold`/`error_probability`: the slicer named
  as a MAP detector, with its decision threshold derived from the
  likelihood ratio instead of assumed to be 0), JTOL (linearized loop
  model), `optimize.py` (fits the CTLE sweep and solves for its continuous
  optimum), `equalizer_opt.py` (closed-form MMSE/least-squares equalizer
  taps next to `dfe.py`'s adaptive LMS, plus a convex,
  tap-budget-constrained version via cvxpy), and `surrogate.py` (a
  multivariate regression surrogate of log10(BER) vs. channel length/CTLE
  zero/DFE taps: polynomial regression, then XGBoost for what a
  fixed-degree polynomial can't fit, with feature importances read as
  design intuition; see [docs/04-applied-math.md](docs/04-applied-math.md)).
  Applied optimization on measurement/signal data, not ML that designs a
  circuit; see the honesty line.
- Currently runs on a **synthetic** channel (`data/touchstone/`, scikit-rf
  FR4 microstrip). Stage B swaps in a real measured channel with zero code
  changes to `channel.load()`.
- `rtl/`: SystemVerilog reimplementation of the PRBS generator, the DFE, and
  the CDR's digital loop filter, cosimulated against the Python golden
  models above via cocotb + Icarus Verilog.
- Power-supply-induced jitter (PSIJ): `tx.apply_supply_jitter` turns supply
  ripple into edge-timing jitter, `analysis/eye.py::crossing_jitter_ui`
  measures the resulting horizontal eye closure, and `analysis/jitter.py`
  ties it to the CDR's own loop bandwidth (tracked out below it, closes
  the eye above it); see [docs/05-power-integrity.md](docs/05-power-integrity.md).

## Stages

| Stage | Status | Docs |
|---|---|---|
| A: Python link model | done | [docs/01-model.md](docs/01-model.md) |
| B: PCB channel + measurement | not started | `pcb/` |
| C: SystemVerilog + cocotb | done | [docs/03-rtl.md](docs/03-rtl.md) |
| D: analog transistor sizing via ML | **out of scope, not planned** | `analog/` |

That's a specific, deliberate boundary, not a blanket "no ML": this repo
already uses applied optimization to process measurement data (see
`src/serdeslink/analysis/optimize.py` and the honesty line below). What's
out of scope is ML that designs or judges a circuit's layout.

Spec and decisions: [docs/00-spec.md](docs/00-spec.md).

## Quickstart

```
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -e .
python -m pytest                       # 40 tests: 37 Python (Stage A + applied math + PSIJ) + 3 RTL cosims (Stage C)
python scripts/run_link.py             # regenerates every Stage A figure in docs/imgs/
python scripts/run_equalizer_opt.py    # regenerates the LMS vs. MMSE vs. convex figure
python scripts/run_ber_threshold.py    # regenerates the MAP-optimal threshold figure
python scripts/sweep_and_fit.py        # regenerates the regression-surrogate fit figure
python scripts/run_psij.py             # regenerates the PSIJ eye-closure and spectrum figures
```

Stage C's RTL tests also need [Icarus Verilog](https://github.com/steveicarus/iverilog)
on your PATH (`scoop install iverilog` on Windows, `apt install iverilog`
or `brew install icarus-verilog` elsewhere).

## Honesty line

This is a link model plus a synthetic FR4 channel (a real measured channel
is Stage B) plus digital control RTL cosimulated against that model
(Stage C). It is **not** a full-rate SerDes PHY tapeout, and the RTL has
never run on real silicon or an FPGA (that's P2 and P7). ML/optimization
framing: this repo uses applied math/optimization to process signal and
measurement data (see `analysis/optimize.py`'s CTLE-sweep fit); it does
**not** use ML to design or judge a circuit's layout, and that's a
deliberate boundary, not something postponed. See `docs/00-spec.md`.

## Status

Stage A complete: channel model, TX, CTLE sweep, DFE convergence, CDR lock
acquisition (bit-level) and JTOL (linearized), and a statistical bathtub.
Stage C complete: PRBS generator, DFE, and CDR digital loop filter in
SystemVerilog, cosimulated against the Stage A golden models via cocotb.
All of it (Python figures + RTL cosim) is regenerated/verified by one
script and one `pytest` run respectively. Next: a real measured channel
(Stage B) once a VNA is in hand.
