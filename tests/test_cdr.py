import numpy as np

from serdeslink import cdr, prbs, tx


def _make_waveform(order=11, n_bits=6000, samples_per_ui=32):
    bits = prbs.prbs(order, n_bits)
    symbols = tx.nrz_symbols(bits)
    waveform = tx.rise_fall_shape(symbols, ui=1.0, samples_per_ui=samples_per_ui, rise_frac=0.1)
    return bits, symbols, waveform


def test_alexander_pd_truth_table():
    assert cdr.alexander_pd(edge_bit=1, early_bit=1, late_bit=1) == 0   # no transition
    assert cdr.alexander_pd(edge_bit=1, early_bit=-1, late_bit=1) == 1   # late
    assert cdr.alexander_pd(edge_bit=-1, early_bit=-1, late_bit=1) == -1  # early


def test_loop_locks_and_tracks_ppm_offset():
    samples_per_ui = 32
    ppm = 200.0
    bits, symbols, waveform = _make_waveform(samples_per_ui=samples_per_ui)

    phase_ui, data_bits, pd_out = cdr.run_cdr(
        waveform, samples_per_ui, ppm=ppm, kp=0.05, ki=0.001, pi_steps_per_ui=64,
    )

    # once locked, the phase-interpolator correction must ramp at close to
    # -ppm*1e-6 UI per UI to cancel the injected frequency offset
    tail = slice(len(phase_ui) // 2, None)
    idx = np.arange(len(phase_ui))[tail]
    slope = np.polyfit(idx, phase_ui[tail], 1)[0]
    expected_slope = -ppm * 1e-6
    assert abs(slope - expected_slope) < 0.2 * abs(expected_slope) + 1e-6

    # and the recovered bits should mostly agree with what was transmitted
    # once the loop has settled (allow for the fixed group delay through the
    # rise/fall shaping filter by comparing against a small set of alignments)
    tx_bits = symbols[len(symbols) // 2:]
    rx_bits = data_bits[len(data_bits) // 2:]
    best_agreement = 0.0
    for shift in range(-2, 3):
        n = min(len(tx_bits) - abs(shift), len(rx_bits) - abs(shift))
        if shift >= 0:
            a, b = tx_bits[:n], rx_bits[shift:shift + n]
        else:
            a, b = tx_bits[-shift:-shift + n], rx_bits[:n]
        best_agreement = max(best_agreement, np.mean(a == b))
    assert best_agreement > 0.9


def test_zero_ppm_stays_near_initial_phase():
    samples_per_ui = 32
    _, _, waveform = _make_waveform(samples_per_ui=samples_per_ui)
    phase_ui, _, _ = cdr.run_cdr(waveform, samples_per_ui, ppm=0.0, kp=0.05, ki=0.001)
    assert np.std(phase_ui[len(phase_ui) // 2:]) < 0.1


def test_fixed_point_loop_filter_tracks_float_run_cdr():
    """The Stage C RTL (cdr_loop_filter.sv) only implements the digital loop
    filter, not the waveform resampling run_cdr() does. This test replays
    run_cdr()'s REAL pd_out sequence (from actual bang-bang PD decisions on
    a real waveform) through the pure fixed-point model and checks the two
    correction trajectories track each other, proving the fixed-point model
    is a faithful stand-in for run_cdr()'s float loop filter before it's
    even compared against RTL."""
    samples_per_ui = 32
    pi_steps_per_ui = 64
    kp, ki = 0.05, 0.001
    ppm = 200.0
    _, _, waveform = _make_waveform(samples_per_ui=samples_per_ui)

    phase_ui_float, _, pd_out = cdr.run_cdr(
        waveform, samples_per_ui, ppm=ppm, kp=kp, ki=ki, pi_steps_per_ui=pi_steps_per_ui,
    )

    kp_fixed, ki_fixed = cdr.loop_filter_gains_fixed(kp, ki, pi_steps_per_ui)
    integrator_fixed = 0
    correction_steps = 0
    phase_ui_fixed = np.zeros(len(pd_out))
    for i, pd in enumerate(pd_out):
        delta_steps, integrator_fixed = cdr.loop_filter_step_fixed(
            int(pd), integrator_fixed, kp_fixed, ki_fixed,
        )
        correction_steps += delta_steps
        phase_ui_fixed[i] = correction_steps / pi_steps_per_ui

    # Same pd sequence, same gains (up to a one-time fixed-point rounding of
    # kp/ki): the two trajectories should stay close the whole way, not just
    # agree on average. 0.05 UI is a small fraction of the eye (see the
    # ~0.5 UI eye margin used elsewhere in this project).
    assert np.max(np.abs(phase_ui_fixed - phase_ui_float)) < 0.05

    # and the settled ramp rate (what actually matters for tracking a
    # frequency offset) should match closely too
    tail = slice(len(phase_ui_fixed) // 2, None)
    idx = np.arange(len(phase_ui_fixed))[tail]
    slope_fixed = np.polyfit(idx, phase_ui_fixed[tail], 1)[0]
    slope_float = np.polyfit(idx, phase_ui_float[tail], 1)[0]
    assert abs(slope_fixed - slope_float) < 0.1 * abs(slope_float) + 1e-6
