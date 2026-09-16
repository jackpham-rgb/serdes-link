# Stage 0 — Spec

## Bit rate and instrument target

Rbit = **5 Gb/s NRZ** (UI = 200 ps). Chosen for LiteVNA-class (~6 GHz) VNA
coverage: Nyquist = 2.5 GHz, and VNA coverage to roughly 3x Nyquist (~7.5
GHz) is comfortably inside a ~6 GHz instrument's range with margin, per the
project howto's "pick the rate from the instrument" rule. **This is
provisional** — Stage A has no VNA yet (it runs entirely on a synthetic
channel), so this number gets locked for real once a VNA is purchased and
its actual max frequency is known (see `coop-plan.txt` in the planning repo).
If the real instrument covers less than ~6 GHz, this drops to ~3-4 Gb/s
before Stage B; the architecture doesn't change (`channel.load()` takes a
path and nothing else).

## Channel

`data/touchstone/synthetic_12in_channel.s4p` — a synthetic 12" FR4
microstrip differential pair (scikit-rf `MLine`, εr=4.3, tanδ=0.02, two
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

## The ML decision (recorded here so it isn't re-litigated)

**POSTPONED, decided 2026-09-16.** No ML-for-transistor-sizing / no ML
"designs" anything in this repo. Where ML shows up (not yet, but noted for
Stage D if ever un-postponed): applied regression/feature-importance on
measurement data, e.g. eye height or BER vs CTLE/DFE settings — an
*analysis* tool, never a design method, and never framed as more than that.
See the planning repo's `portfolio-projects-reference.txt` §8 for the full
reasoning; that file is private and not part of this public repo.

## Honesty line

This is a link model + a synthetic channel (a real measured channel is
Stage B) + (later) digital control RTL. It is not a full-rate SerDes PHY
tapeout.
</content>
