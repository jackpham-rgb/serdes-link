"""serdeslink — a from-scratch high-speed serial link model.

Channel (Touchstone) -> TX (PRBS + FFE + pulse shaping) -> channel convolution
-> CTLE -> DFE -> CDR -> eye / statistical BER / jitter-tolerance analysis.
"""

__version__ = "0.1.0"
