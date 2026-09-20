import numpy as np

from serdeslink.analysis import surrogate


def test_polynomial_features_degree2_shape_and_values():
    X = np.array([[1.0, 2.0], [3.0, 4.0]])
    Xp, names = surrogate.polynomial_features(X, degree=2)
    # bias, x0, x1, x0^2, x1^2, x0*x1 = 6 columns
    assert Xp.shape == (2, 6)
    assert names == ["bias", "x0", "x1", "x0^2", "x1^2", "x0*x1"]
    np.testing.assert_allclose(Xp[0], [1.0, 1.0, 2.0, 1.0, 4.0, 2.0])
    np.testing.assert_allclose(Xp[1], [1.0, 3.0, 4.0, 9.0, 16.0, 12.0])


def test_r_squared_is_one_for_perfect_fit():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert surrogate.r_squared(y, y) == 1.0


def test_polynomial_surrogate_recovers_known_quadratic():
    rng = np.random.default_rng(0)
    X = rng.uniform(-3, 3, size=(300, 2))
    y_true = 2.0 - 1.5 * X[:, 0] + 0.5 * X[:, 1] + 0.3 * X[:, 0] ** 2 - 0.8 * X[:, 0] * X[:, 1]
    y = y_true + rng.normal(0, 0.01, size=len(y_true))

    model = surrogate.PolynomialSurrogate(degree=2).fit(X, y)
    pred = model.predict(X)
    assert surrogate.r_squared(y, pred) > 0.999


def test_xgboost_beats_polynomial_on_a_function_no_quadratic_can_fit():
    """The actual Workstream 3 claim: a fixed-degree polynomial underfits a
    genuinely non-quadratic response surface, while a more flexible model
    (XGBoost) captures it. Uses a function with a sharp local feature (a
    narrow bump) that a global quadratic cannot represent, regardless of
    its coefficients."""
    rng = np.random.default_rng(1)
    X = rng.uniform(-3, 3, size=(400, 1))
    y = np.sin(3 * X[:, 0]) + 2.0 * np.exp(-((X[:, 0] - 1.0) ** 2) / 0.05)
    y = y + rng.normal(0, 0.02, size=len(y))

    n_train = 300
    X_train, y_train = X[:n_train], y[:n_train]
    X_test, y_test = X[n_train:], y[n_train:]

    poly = surrogate.PolynomialSurrogate(degree=2).fit(X_train, y_train)
    poly_r2 = surrogate.r_squared(y_test, poly.predict(X_test))

    xgb_model = surrogate.fit_xgboost_surrogate(X_train, y_train)
    xgb_r2 = surrogate.r_squared(y_test, xgb_model.predict(X_test))

    assert xgb_r2 > 0.9
    assert xgb_r2 > poly_r2 + 0.2


def test_suggest_settings_finds_known_minimum():
    def predict_fn(X):
        return (X[:, 0] - 3.0) ** 2 + (X[:, 1] - (-2.0)) ** 2

    best_x, best_y = surrogate.suggest_settings(
        predict_fn, bounds=[(-10, 10), (-10, 10)], n_samples=200000, minimize=True,
    )
    assert abs(best_x[0] - 3.0) < 0.1
    assert abs(best_x[1] - (-2.0)) < 0.1
    assert best_y < 0.02


def test_suggest_settings_rounds_integer_dims():
    def predict_fn(X):
        return (X[:, 0] - 3.0) ** 2 + (X[:, 1] - 4.7) ** 2

    best_x, _ = surrogate.suggest_settings(
        predict_fn, bounds=[(0, 10), (0, 10)], integer_dims=[1], n_samples=50000,
    )
    assert best_x[1] == round(best_x[1])
