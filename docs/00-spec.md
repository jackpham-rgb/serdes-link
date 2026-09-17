# Stage 0 - Spec

## Bit rate and instrument target

Rbit = **5 Gb/s NRZ** (UI = 200 ps). Chosen for LiteVNA-class (~6 GHz) VNA
coverage: Nyquist = 2.5 GHz, and VNA coverage to roughly 3x Nyquist (~7.5
GHz) is comfortably inside a ~6 GHz instrument's range with margin, per the
project howto's "pick the rate from the instrument" rule. **This is
provisional.** Stage A has no VNA yet (it runs entirely on a synthetic
channel), so this number gets locked for real once a VNA is purchased and
its actual max frequency is known (see `coop-plan.txt` in the planning repo).
If the real instrument covers less than ~6 GHz, this drops to ~3-4 Gb/s
before Stage B; the architecture doesn't change (`channel.load()` takes a
path and nothing else).

## Channel

`data/touchstone/synthetic_12in_channel.s4p` is a synthetic 12" FR4
microstrip differential pair (scikit-rf `MLine`, er=4.3, tan-delta=0.02, two
identical uncoupled single-ended lines assembled into a 4-port file). This is
a stand-in for a measured board, not a measurement. See
`data/touchstone/make_synthetic_channel.py` for the exact parameters, and its
docstring for the port-numbering convention (`channel.load()` assumes
scikit-rf's `se2gmm(p=2)` native order: TX+, TX-, RX+, RX-).

## Block diagram

```
PRBS15 -> NRZ -> TX FFE (1 precursor, 1 postcursor) -> finite-rise shaping
        -> [channel: measured/synthetic SDD21, resampled + convolved]
        -> CTLE (1 zero, 2 poles, swept for peaking) -> UI-center sampling
        -> DFE (4-tap, sign-sign LMS)  |  CDR (bang-bang PD + PI loop filter)
        -> eye / statistical BER (peak-distortion) / JTOL (linearized loop)
```

## The ML / optimization decision (recorded here so it isn't re-litigated)

Two different things both get called "ML," and only one of them is out of
scope for this repo.

**Out of scope, not planned:** ML that *designs or judges a circuit*, for
example a model that proposes analog transistor sizes, or scores a layout.
That's a real, separate research direction (it was the original idea for
"Stage D" here), and it stays out of this repo: it would overpromise and
isn't something I've built.

**In scope, and used here:** applied math/optimization to *process signal
and measurement data*. This repo doesn't just promise that, it does it:
`src/serdeslink/analysis/optimize.py` fits a quadratic (ordinary least
squares) to the CTLE peaking sweep and solves for its vertex, i.e. the
continuous peaking value the *data* predicts is optimal, rather than only
reporting the best of the handful of sampled points (see the CTLE sweep
figure in docs/01-model.md). That's the same kind of applied
regression/optimization this project uses elsewhere (statistical BER,
the DFE and CDR's adaptive loop math): read the numbers, fit or solve
something, report the result. No part of it looks at or judges a circuit's
layout. See the planning repo's `portfolio-projects-reference.txt` section
8 for the fuller reasoning; that file is private and not part of this
public repo.

## Honesty line

This is a link model plus a synthetic channel (a real measured channel is
Stage B) plus digital control RTL cosimulated against that model (Stage C,
see docs/03-rtl.md). It is not a full-rate SerDes PHY tapeout, and the RTL
has not run on real silicon or an FPGA yet.
