# Spec

| Item | Value |
|---|---|
| Bit rate | 5 Gb/s NRZ, 200 ps per bit |
| Channel | 36 in FR4 microstrip differential pair, synthetic (scikit-rf), 14.9 dB loss at 2.5 GHz |
| Launch swing | 1 V peak-to-peak differential |
| TX FFE | 2 taps, 3.5 dB de-emphasis |
| CTLE | 1 zero (swept), poles at 3.5 and 7.5 GHz |
| DFE | 4 taps, sign-sign LMS |
| CDR | Bang-bang (Alexander) phase detector, two-path loop filter, 64-step phase interpolator |
| Noise | 1 mV rms at the receiver input in a 5 GHz band |
| Random jitter | 0.015 UI rms |
| Target BER | 1e-12 |

The bit rate was chosen so the channel's interesting frequency range (up to about three times Nyquist, 7.5 GHz) fits inside a low-cost 6 GHz network analyzer, which is what measuring the test board in `pcb/` would need.

## Block diagram

```
PRBS15 -> NRZ -> TX FFE -> rise-time shaping -> channel -> CTLE -> sampler -> DFE -> bits
                                                                      ^
                                                                     CDR
```

## Channel files

`data/touchstone/synthetic_36in_channel.s4p` is two identical, uncoupled lossy microstrip lines (er = 4.3, loss tangent 0.02) written as a 4-port file. Port order is TX+, TX−, RX+, RX−, the order scikit-rf's mixed-mode conversion expects. A measured file in the same order drops in with no code change.

## Scope

The repo applies regression and optimization to simulated signal data: fitting the CTLE sweep, solving for the optimal equalizer taps, choosing the slicer threshold, and a surrogate model of BER (see `04-applied-math.md`). Machine learning that designs or judges a circuit, such as sizing transistors, is outside this project.
