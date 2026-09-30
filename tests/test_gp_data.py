import gzip
import json

import numpy as np
import pytest

import gp_data


def test_rbf_is_one_on_the_diagonal_and_symmetric():
    x = np.linspace(0, 5, 7)
    k = gp_data.rbf(x, x, 1.5)
    assert np.allclose(np.diag(k), 1.0)
    assert np.allclose(k, k.T)


def test_rbf_known_value():
    assert gp_data.rbf([0.0], [1.0], 1.0)[0, 0] == pytest.approx(np.exp(-0.5))


def test_sample_pool_is_deterministic():
    cov = gp_data.rbf(np.arange(5), np.arange(5), 2.0)
    first = gp_data.sample_pool(np.zeros(5), cov, n=4, seed=7)
    second = gp_data.sample_pool(np.zeros(5), cov, n=4, seed=7)
    assert first.shape == (4, 5)
    assert np.array_equal(first, second)


@pytest.mark.parametrize(
    ("x", "ell"),
    [(np.linspace(0, 50, 50), 30.0), (np.linspace(-1, 1, 50), 2.0), (np.linspace(-1, 1, 50), 0.05)],
)
def test_sample_pool_is_finite_for_extreme_length_scales(x, ell):
    pool = gp_data.sample_pool(np.zeros(len(x)), gp_data.rbf(x, x, ell))
    assert np.isfinite(pool).all()


def test_gp_posterior_goes_through_the_training_data():
    x = np.array([0.0, 1.0, 2.5])
    y = np.array([1.0, -0.5, 0.3])
    mean, cov = gp_data.gp_posterior(y, x, x, ell=1.0)
    assert np.allclose(mean, y, atol=1e-6)
    assert np.allclose(np.diag(cov), 0.0, atol=1e-6)


def test_page_data_has_the_expected_shapes():
    data = gp_data.page_data()
    assert len(data["regression"]["a"]["lines"]) == 50
    assert len(data["regression"]["b"]["betas"][0]) == 2
    assert len(data["hist"]["z"]) == 5000
    assert len(data["mvn2"]["z"]) == 2500
    assert len(data["iid"]["d50"]) == 50 and len(data["iid"]["d50"][0]) == 50
    assert sorted(int(key) for key in data["fuzzy"]["pools"]) == list(range(1, 31))
    assert data["double"]["ells"][0] == 0.05 and data["double"]["ells"][-1] == 2.0
    assert len(data["double"]["ells"]) == 40
    assert len(data["double"]["pools"]) == 40 and len(data["double"]["pools"][0]) == 50
    assert len(data["post"]["pool"]) == 50 and len(data["post"]["many"]) == 500
    assert len(data["post"]["known"]["x"]) == 15


def test_page_data_is_finite_and_fits_the_budget():
    text = json.dumps(gp_data.page_data(), allow_nan=False)
    assert len(gzip.compress(text.encode())) < 800_000


def test_same_z_inside_a_widget():
    """Within a widget, different ℓ values use the same z."""
    tol = 1e-5  # Numerical tolerance for direct sample comparison
    mean_zero = np.zeros(50)

    # Test fuzzy_data: ℓ = 1 and ℓ = 20 should use the same z
    x_fuzzy = np.linspace(0, 50, 50)
    ell1, ell20 = 1.0, 20.0
    cov1 = gp_data.rbf(x_fuzzy, x_fuzzy, ell1)
    cov20 = gp_data.rbf(x_fuzzy, x_fuzzy, ell20)

    # Generate samples with the same seed
    pool_ell1 = gp_data.sample_pool(mean_zero, cov1, seed=gp_data.SEED + 40)
    pool_ell20 = gp_data.sample_pool(mean_zero, cov20, seed=gp_data.SEED + 40)

    # Recover z by solving: pool = mean + z @ L.T => pool - mean = z @ L.T
    # => (pool - mean).T = L @ z.T => z.T = solve(L, (pool - mean).T)
    # Note: sample_pool adds JITTER internally, so we use cov + JITTER here
    L1 = np.linalg.cholesky(cov1 + gp_data.JITTER * np.eye(50))
    L20 = np.linalg.cholesky(cov20 + gp_data.JITTER * np.eye(50))
    z1 = np.linalg.solve(L1, (pool_ell1 - mean_zero).T)
    z20 = np.linalg.solve(L20, (pool_ell20 - mean_zero).T)

    assert np.allclose(z1, z20, atol=tol), "fuzzy pools with different ℓ should have same z"

    # Test double_data: first and last ℓ should use the same z
    x_double = np.linspace(-1, 1, 50)
    ell_first = 0.05
    ell_last = 2.0
    cov_first = gp_data.rbf(x_double, x_double, ell_first)
    cov_last = gp_data.rbf(x_double, x_double, ell_last)

    # Generate samples with the same seed
    pool_first = gp_data.sample_pool(mean_zero, cov_first, seed=gp_data.SEED + 70)
    pool_last = gp_data.sample_pool(mean_zero, cov_last, seed=gp_data.SEED + 70)

    # Recover z
    L_first = np.linalg.cholesky(cov_first + gp_data.JITTER * np.eye(50))
    L_last = np.linalg.cholesky(cov_last + gp_data.JITTER * np.eye(50))
    z_first = np.linalg.solve(L_first, (pool_first - mean_zero).T)
    z_last = np.linalg.solve(L_last, (pool_last - mean_zero).T)

    assert np.allclose(z_first, z_last, atol=tol), "double pools with different ℓ should have same z"


def test_sample_pool_produces_correct_covariance():
    """Empirical covariance of samples matches the target covariance."""
    cov_target = np.array([[1.0, 0.3, 0.1], [0.3, 1.0, -0.2], [0.1, -0.2, 1.0]])
    pool = gp_data.sample_pool(np.zeros(3), cov_target, n=200_000, seed=1)
    cov_empirical = np.cov(pool.T)

    assert np.allclose(cov_empirical, cov_target, atol=0.02), "empirical covariance should match target"


def test_different_widgets_do_not_share_random_numbers():
    """Different widgets should not share random numbers."""
    data = gp_data.page_data()

    # hist.z should not equal first 5000 values of mvn2.z flattened
    hist_z = np.array(data["hist"]["z"])
    mvn2_z = np.array(data["mvn2"]["z"]).flatten()
    first_5000_mvn2 = mvn2_z[:5000]

    assert not np.allclose(hist_z, first_5000_mvn2), "hist and mvn2 should not share random numbers"

    # fuzzy["pools"]["5"] should not equal double["pools"][3] (ℓ = 0.2)
    fuzzy_pool_ell5 = np.array(data["fuzzy"]["pools"]["5"])
    double_pool_ell02 = np.array(data["double"]["pools"][3])  # ℓ = 0.2

    assert not np.allclose(fuzzy_pool_ell5, double_pool_ell02), "fuzzy and double should not share random numbers"
