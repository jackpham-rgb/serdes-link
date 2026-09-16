"""Maximal-length PRBS sequence generators (Fibonacci LFSR).

Standard two-tap feedback polynomials (x^n + x^k + 1) for the orders used in
SerDes test patterns. Bit-exact alignment to a particular vendor's PRBS
convention doesn't matter for a link-model eye/BER study (any maximal-length
sequence has the same flat-spectrum, all-run-lengths-present statistics).
What's tested in tests/test_prbs.py are the structural properties that
actually matter: period length, run-length bounds, and non-repetition within
one period.
"""
from __future__ import annotations

import numpy as np

# order -> (tap1, tap2), 1-indexed bit positions, x^tap1 + x^tap2 + 1
_TAPS = {
    7: (7, 6),
    9: (9, 5),
    11: (11, 9),
    15: (15, 14),
    23: (23, 18),
    31: (31, 28),
}


def prbs(order: int, n_bits: int, seed: int | None = None) -> np.ndarray:
    """Generate `n_bits` of a PRBS-`order` sequence as a uint8 {0,1} array."""
    if order not in _TAPS:
        raise ValueError(f"unsupported PRBS order {order}; have {sorted(_TAPS)}")
    t1, t2 = _TAPS[order]
    reg = 1 if seed is None else int(seed)
    if reg == 0:
        raise ValueError("LFSR seed must be nonzero (all-zero state is not part of a maximal sequence)")
    mask = (1 << order) - 1

    out = np.empty(n_bits, dtype=np.uint8)
    for i in range(n_bits):
        fb = ((reg >> (t1 - 1)) ^ (reg >> (t2 - 1))) & 1
        out[i] = reg & 1
        reg = ((reg << 1) | fb) & mask
    return out


def period(order: int) -> int:
    return (1 << order) - 1
