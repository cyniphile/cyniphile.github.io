"""Precomputed data for the Gaussian process post.

All random numbers come from fixed seeds, so each build gives the same data.
A sample is mean + L @ z, where L is the Cholesky factor of the covariance.
All length scales use the same z, so the curves change smoothly when the reader moves a slider.
"""

from __future__ import annotations

import numpy as np

SEED = 42
POOL = 50
JITTER = 1e-6

HOUSING_X = [
    9.34825241, 9.67438030, 11.7250505, 5.99427279, 10.7375146, 3.87950162, 2.71045131,
    7.35740185, 9.13638194, 10.5863164, 7.42074188, 12.0328572, 5.15531137, 0.324806136,
    0.00132962952,
]
HOUSING_Y = [
    295011.54177245, 291803.4301587, 302340.03191297, 254244.52812629, 288037.40660445,
    225340.17067212, 235462.67258466, 291158.36183822, 297052.11645609, 287514.83630223,
    292359.62730391, 310157.34073017, 233483.05286424, 209630.56264745, 200039.88887763,
]


def rbf(xa, xb, ell):
    """RBF kernel: the covariance between each point in xa and each point in xb."""
    xa = np.asarray(xa, dtype=float).reshape(-1)
    xb = np.asarray(xb, dtype=float).reshape(-1)
    return np.exp(-0.5 / ell**2 * (xa[:, None] - xb[None, :]) ** 2)


def sample_pool(mean, cov, n=POOL, seed=SEED):
    """Draw n samples of N(mean, cov). The same seed gives the same standard-normal draws."""
    mean = np.asarray(mean, dtype=float)
    cov = np.asarray(cov, dtype=float)
    chol = np.linalg.cholesky(cov + JITTER * np.eye(len(cov)))
    z = np.random.default_rng(seed).standard_normal((n, len(cov)))
    return mean + z @ chol.T


def gp_posterior(y_train, x_train, x_test, ell=1.0):
    """Mean and covariance of a zero-mean GP with an RBF kernel, conditioned on training data."""
    k11 = rbf(x_train, x_train, ell)
    k21 = rbf(x_test, x_train, ell)
    k22 = rbf(x_test, x_test, ell)
    mean = k21 @ np.linalg.solve(k11, np.asarray(y_train, dtype=float))
    cov = k22 - k21 @ np.linalg.solve(k11, k21.T)
    return mean, (cov + cov.T) / 2


def _round(values, decimals=3):
    return np.round(np.asarray(values, dtype=float), decimals).tolist()


def regression_data(seed=SEED):
    rng = np.random.default_rng(seed)
    x = np.linspace(-3, 3, 10)
    noisy = x + rng.normal(0, 1.0, 10)
    less_noisy = x + rng.normal(0, 0.1, 10)
    slope_a = np.corrcoef(x, noisy)[0, 1] * np.std(noisy) / np.std(x)

    def panel(points, slope, spread, seed_offset):
        draws = np.random.default_rng(seed + seed_offset)
        b0 = draws.normal(0.0, spread, POOL)
        b1 = draws.normal(slope, spread, POOL)
        return {
            "points": _round(points),
            "ols": _round(np.polyval(np.polyfit(x, points, 1), x)),
            "truth": _round(slope * x),
            "lines": _round(b0[:, None] + b1[:, None] * x[None, :]),
            "betas": _round(np.column_stack([b0, b1]), 2),
        }

    return {"x": _round(x), "a": panel(noisy, slope_a, 1.0, 1), "b": panel(less_noisy, 1.0, 0.1, 2)}


def histogram_data(n=5000, seed=SEED + 10):
    return {"z": _round(np.random.default_rng(seed).standard_normal(n))}


def mvn2_data(n=2500, seed=SEED + 20):
    rng = np.random.default_rng(seed)
    return {"z": _round(rng.standard_normal((n, 2))), "reference": _round(rng.standard_normal((n, 2)))}


def iid_data(seed=SEED + 30):
    rng = np.random.default_rng(seed)
    return {f"d{d}": _round(rng.standard_normal((POOL, d))) for d in (1, 2, 3, 50)}


def fuzzy_data():
    x = np.linspace(0, 50, 50)
    ells = list(range(1, 31))
    pools = {str(ell): _round(sample_pool(np.zeros(50), rbf(x, x, ell), seed=SEED + 40)) for ell in ells}
    return {"x": _round(x), "ells": ells, "pools": pools}


def pi_data():
    x = np.array([-np.pi, np.pi, 2 * np.pi])
    cov = np.diag(x**2)
    return {
        "x": _round(x, 4),
        "labels": [f"{value:.4f}" for value in x],
        "cov": _round(cov, 4),
        "pool": _round(sample_pool(x, cov, seed=SEED + 50)),
    }


def real50_data():
    x = np.linspace(-1, 1, 50)
    cov = np.diag(x**2)
    return {
        "x": _round(x),
        "labels": [f"{value:.2f}" for value in x],
        "cov": _round(cov, 4),
        "pool": _round(sample_pool(x, cov, seed=SEED + 60)),
    }


def double_data():
    x = np.linspace(-1, 1, 50)
    ells = np.round(np.arange(1, 41) * 0.05, 2)
    pools = [_round(sample_pool(np.zeros(50), rbf(x, x, ell), seed=SEED + 70)) for ell in ells]
    return {"x": _round(x), "ells": ells.tolist(), "pools": pools}


def posterior_data(seed=SEED):
    x_known = np.array(HOUSING_X)
    y_known = np.array(HOUSING_Y)
    x_test = np.linspace(0, 4 * np.pi, 50)
    y_mean, y_std = y_known.mean(), y_known.std()
    mean, cov = gp_posterior((y_known - y_mean) / y_std, x_known, x_test, ell=1.0)
    pool = sample_pool(mean, cov, n=POOL, seed=seed + 80) * y_std + y_mean
    many = sample_pool(mean, cov, n=500, seed=seed + 81) * y_std + y_mean
    truth = (0.1 * np.sin(x_test) + 1) * 200000 + x_test * 10000
    return {
        "x": _round(x_test),
        "labels": [f"{value:.2f}" for value in x_test],
        "known": {"x": _round(x_known), "y": _round(y_known, 0)},
        "truth": {"x": _round(x_test), "y": _round(truth, 0)},
        "mean": _round(mean * y_std + y_mean, 0),
        "cov": _round(cov),
        "pool": _round(pool, 0),
        "many": _round(many, 0),
    }


def page_data():
    """All data for the post, as lists that json.dumps can write."""
    return {
        "regression": regression_data(),
        "hist": histogram_data(),
        "mvn2": mvn2_data(),
        "iid": iid_data(),
        "fuzzy": fuzzy_data(),
        "pi": pi_data(),
        "real50": real50_data(),
        "double": double_data(),
        "post": posterior_data(),
    }
