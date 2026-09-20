"""Applied-math extension, Workstream 3: generate a multivariate sweep of
the link (channel length, CTLE zero placement, DFE tap count) and fit a
regression surrogate of log10(BER), instead of only ever reading BER off a
single-variable sweep the way the CTLE-only fit in optimize.py does.

Run from the repo root:
    python scripts/sweep_and_fit.py
"""
from __future__ import annotations

import pathlib
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data" / "touchstone"))

from make_synthetic_channel import make_synthetic_channel  # noqa: E402
from serdeslink import channel as channel_mod  # noqa: E402
from serdeslink import dfe as dfe_mod  # noqa: E402
from serdeslink import link  # noqa: E402
from serdeslink.analysis import ber as ber_mod  # noqa: E402
from serdeslink.analysis import surrogate  # noqa: E402

IMG_DIR = ROOT / "docs" / "imgs"
TMP_CHANNEL = ROOT / "_tmp_sweep_channel.s4p"

RBIT = 5e9
UI_SEC = 1.0 / RBIT
SAMPLES_PER_UI = 32
N_BITS = 3000
FEATURE_NAMES = ["channel length (in)", "CTLE zero (GHz)", "DFE taps"]


def run_one(length_in: float, zero_hz: float, n_taps: int, channel_cache: dict) -> float:
    """One point of the sweep: build (or reuse) the channel at this length,
    drive it, equalize, run the DFE, and turn the post-DFE residual into a
    log10(BER) estimate via `ber.error_probability` -- the same detection-
    theory machinery Workstream 2 added, reused here as the sweep's target
    metric instead of inventing a new one."""
    length_key = round(length_in, 3)
    if length_key not in channel_cache:
        make_synthetic_channel(str(TMP_CHANNEL), length_m=length_key * 0.0254)
        channel_cache[length_key] = channel_mod.load(str(TMP_CHANNEL))
    t, h, freq, sdd21 = channel_cache[length_key]
    dt_channel = t[1] - t[0]

    bits, tx_waveform = link.generate_tx_waveform(
        N_BITS, SAMPLES_PER_UI, order=15, ffe=(-0.05, 1.0, (-0.1,)),
    )
    rx_raw = link.drive_channel(tx_waveform, h, dt_channel, SAMPLES_PER_UI, UI_SEC)
    rx_eq = link.apply_ctle_time_domain(rx_raw, SAMPLES_PER_UI, UI_SEC, dc_gain_db=0.0, zero_hz=zero_hz)
    samples = link.sample_ui_centers(rx_eq, SAMPLES_PER_UI)
    decisions, taps_history, residual = dfe_mod.run_dfe(samples, n_taps=n_taps, mu=2e-3)

    window = slice(-1500, None)
    sigma_eff = float(np.std(residual[window] - decisions[window]))
    ber_est = ber_mod.error_probability(0.0, -1.0, sigma_eff, 1.0, sigma_eff)
    return float(np.log10(max(ber_est, 1e-300)))


def build_dataset(rng):
    lengths_in = [4, 8, 12, 16, 20, 24]
    zero_hz_list = np.geomspace(0.5e9, 4e9, 6)
    n_taps_list = [1, 2, 3, 4, 5, 6]

    X, y = [], []
    channel_cache = {}
    for length_in in lengths_in:
        for zero_hz in zero_hz_list:
            for n_taps in n_taps_list:
                log_ber = run_one(length_in, zero_hz, n_taps, channel_cache)
                X.append([length_in, zero_hz / 1e9, n_taps])
                y.append(log_ber)
    return np.array(X), np.array(y)


def train_test_split(X, y, test_frac=0.25, rng=None):
    rng = rng or np.random.default_rng(0)
    n = len(y)
    idx = rng.permutation(n)
    n_test = int(n * test_frac)
    test_idx, train_idx = idx[:n_test], idx[n_test:]
    return X[train_idx], y[train_idx], X[test_idx], y[test_idx]


def main():
    warnings.filterwarnings("ignore")  # scikit-rf's own conductor-loss-model warning, not ours
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)

    print("[sweep] generating dataset (6 lengths x 6 CTLE settings x 6 DFE tap counts = 216 points)...")
    X, y = build_dataset(rng)
    X_train, y_train, X_test, y_test = train_test_split(X, y, rng=rng)
    print(f"[sweep] {len(y_train)} train / {len(y_test)} test points; "
          f"log10(BER) range [{y.min():.2f}, {y.max():.2f}]")

    poly = surrogate.PolynomialSurrogate(degree=2).fit(X_train, y_train)
    poly_pred_test = poly.predict(X_test)
    poly_r2 = surrogate.r_squared(y_test, poly_pred_test)
    print(f"[poly]    held-out R^2 = {poly_r2:.3f}, RMSE = {np.sqrt(np.mean((poly_pred_test - y_test) ** 2)):.3f}")

    xgb_model = surrogate.fit_xgboost_surrogate(X_train, y_train)
    xgb_pred_test = xgb_model.predict(X_test)
    xgb_r2 = surrogate.r_squared(y_test, xgb_pred_test)
    print(f"[xgboost] held-out R^2 = {xgb_r2:.3f}, RMSE = {np.sqrt(np.mean((xgb_pred_test - y_test) ** 2)):.3f}")

    best_x, best_y = surrogate.suggest_settings(
        xgb_model.predict, bounds=[(4, 24), (0.5, 4.0), (1, 6)], integer_dims=[2], rng=rng,
    )
    print(f"[suggest] surrogate-proposed settings: length={best_x[0]:.1f}in, "
          f"CTLE zero={best_x[1]:.2f}GHz, DFE taps={int(best_x[2])} "
          f"-> predicted log10(BER)={best_y:.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].scatter(y_test, poly_pred_test, label=f"polynomial (R^2={poly_r2:.2f})", alpha=0.7)
    axes[0].scatter(y_test, xgb_pred_test, label=f"xgboost (R^2={xgb_r2:.2f})", alpha=0.7)
    lims = [min(y.min(), poly_pred_test.min(), xgb_pred_test.min()),
            max(y.max(), poly_pred_test.max(), xgb_pred_test.max())]
    axes[0].plot(lims, lims, "k--", linewidth=1)
    axes[0].set_xlabel("actual log10(BER)")
    axes[0].set_ylabel("predicted log10(BER)")
    axes[0].set_title("Held-out fit quality")
    axes[0].legend(fontsize=8)

    importances = xgb_model.feature_importances_
    axes[1].bar(FEATURE_NAMES, importances)
    axes[1].set_ylabel("XGBoost feature importance")
    axes[1].set_title("Which setting matters most for BER")
    axes[1].tick_params(axis="x", labelsize=8)

    fig.tight_layout()
    fig.savefig(IMG_DIR / "surrogate_fit.png", dpi=150)
    plt.close(fig)

    print(f"\nFigure written to {IMG_DIR / 'surrogate_fit.png'}")
    TMP_CHANNEL.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
