import numpy as np

from serdeslink import prbs


def test_period_and_no_early_repeat():
    order = 7
    n = prbs.period(order)
    seq = prbs.prbs(order, 3 * n)
    one_period = seq[:n]
    # sequence must repeat exactly at the period boundary...
    assert np.array_equal(seq[n:2 * n], one_period)
    assert np.array_equal(seq[2 * n:3 * n], one_period)
    # ...and not before it (no proper divisor of n is also a period)
    for k in (1, 2, n // 2, n - 1):
        assert not np.array_equal(np.roll(one_period, k), one_period)


def test_balance_and_run_lengths():
    order = 7
    n = prbs.period(order)
    seq = prbs.prbs(order, n)
    ones = int(seq.sum())
    # a maximal-length sequence has 2^(n-1) ones and 2^(n-1)-1 zeros
    assert ones == 2 ** (order - 1)
    assert n - ones == 2 ** (order - 1) - 1

    runs = _run_lengths(seq)
    max_one_run = max(length for value, length in runs if value == 1)
    max_zero_run = max(length for value, length in runs if value == 0)
    # exactly one run of `order` consecutive ones, longest zero run is order-1
    assert max_one_run == order
    assert max_zero_run == order - 1


def test_prbs15_period():
    order = 15
    n = prbs.period(order)
    assert n == 2 ** 15 - 1
    seq = prbs.prbs(order, n + 10)
    assert np.array_equal(seq[:10], seq[n:n + 10])


def _run_lengths(seq):
    runs = []
    cur = seq[0]
    length = 1
    for v in seq[1:]:
        if v == cur:
            length += 1
        else:
            runs.append((int(cur), length))
            cur, length = v, 1
    runs.append((int(cur), length))
    return runs
