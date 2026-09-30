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
