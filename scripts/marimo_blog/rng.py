"""Random sampling that the browser can repeat.

During a conversion, np.random.normal and np.random.multivariate_normal are replaced. Both take
their standard-normal draws from numpy's global generator, so np.random.seed works as before and
normal() gives the same values as numpy's legacy normal(). Each call is recorded (parameters,
draws, result), so the converter can find the result in the output and the browser can compute
it again from the draws: loc + scale * z, or mean + z @ sqrt_factor(cov).

sqrt_factor uses the cyclic Jacobi eigenvalue method for small matrices, the same method as the
browser runtime (mb.js), so both give the same samples. Larger matrices use numpy.linalg.eigh;
the browser never repeats those (their states are precomputed).
"""

from __future__ import annotations

import contextlib
import hashlib
import math
import warnings
from dataclasses import dataclass, field

import numpy as np

JACOBI_MAX_SIZE = 4
PSD_TOL = 1e-8
NOT_PSD = "covariance is not symmetric positive-semidefinite."

_numpy_normal = np.random.normal
_numpy_mvn = np.random.multivariate_normal


@dataclass
class Call:
    fn: str  # "normal" or "multivariate_normal"
    params: dict
    z: np.ndarray
    result: np.ndarray | None = None
    error: str | None = None


@dataclass
class Recorder:
    calls: list[Call] = field(default_factory=list)


_recorders: list[Recorder] = []


def _record(call: Call) -> None:
    for recorder in _recorders:
        recorder.calls.append(call)


@contextlib.contextmanager
def recording():
    """Record the sampling calls made inside the block."""
    recorder = Recorder()
    _recorders.append(recorder)
    try:
        yield recorder
    finally:
        _recorders.remove(recorder)


def jacobi_eigh(matrix):
    """Eigenvalues and eigenvectors (columns) of a small symmetric matrix, cyclic Jacobi method.

    The browser runtime has the same algorithm (mb.js eigh), so the results agree.
    """
    a = [[float(v) for v in row] for row in matrix]
    n = len(a)
    vecs = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _sweep in range(50):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < 1e-30:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-300:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
                t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = vecs[k][p], vecs[k][q]
                    vecs[k][p], vecs[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    return np.array([a[i][i] for i in range(n)]), np.array(vecs)


def is_psd(cov, tol: float = PSD_TOL) -> bool:
    """numpy's check_valid test: the matrix is symmetric and has no negative eigenvalue."""
    cov = np.asarray(cov, dtype=float)
    if not np.allclose(cov, cov.T, rtol=tol, atol=tol):
        return False
    values = jacobi_eigh(cov)[0] if len(cov) <= JACOBI_MAX_SIZE else np.linalg.eigvalsh(cov)
    return bool(values.min() >= -tol * max(1.0, float(np.abs(values).max())))


def sqrt_factor(cov) -> np.ndarray:
    """F with F.T @ F == cov for a PSD matrix (negative eigenvalues count as 0)."""
    cov = np.asarray(cov, dtype=float)
    sym = (cov + cov.T) / 2.0
    values, vectors = jacobi_eigh(sym) if len(cov) <= JACOBI_MAX_SIZE else np.linalg.eigh(sym)
    return np.sqrt(np.clip(values, 0.0, None))[:, None] * vectors.T


def normal(loc=0.0, scale=1.0, size=None):
    """np.random.normal, with the same values as numpy's legacy generator."""
    loc_arr, scale_arr = np.asarray(loc, dtype=float), np.asarray(scale, dtype=float)
    if np.any(scale_arr < 0):
        raise ValueError("scale < 0")
    if size is None:
        shape = np.broadcast(loc_arr, scale_arr).shape
        size = shape or None
    z = np.random.standard_normal(size)
    result = loc_arr + scale_arr * z
    if np.ndim(result) == 0:
        result = float(result)
    _record(Call("normal", {"loc": loc_arr, "scale": scale_arr}, np.asarray(z), np.asarray(result)))
    return result


def multivariate_normal(mean, cov, size=None, check_valid="warn", tol=PSD_TOL):
    """np.random.multivariate_normal, with a factor that the browser can compute again."""
    if check_valid not in ("warn", "raise", "ignore"):
        raise ValueError("check_valid must equal 'warn', 'raise', or 'ignore'")
    mean = np.asarray(mean, dtype=float)
    cov = np.asarray(cov, dtype=float)
    if mean.ndim != 1:
        raise ValueError("mean must be 1 dimensional")
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        raise ValueError("cov must be 2 dimensional and square")
    if mean.shape[0] != cov.shape[0]:
        raise ValueError("mean and cov must have same length")
    shape = [] if size is None else ([int(size)] if np.ndim(size) == 0 else [int(s) for s in size])
    final_shape = [*shape, mean.shape[0]]
    # numpy draws before it checks the matrix, so a failed check still uses the draws
    z = np.random.standard_normal(final_shape).reshape(-1, mean.shape[0])
    call = Call("multivariate_normal", {"mean": mean, "cov": cov}, z)
    if check_valid != "ignore" and not is_psd(cov, tol):
        if check_valid == "raise":
            call.error = NOT_PSD
            _record(call)
            raise ValueError(NOT_PSD)
        warnings.warn(NOT_PSD, RuntimeWarning, stacklevel=2)
    result = (z @ sqrt_factor(cov) + mean).reshape(final_shape)
    call.result = result
    _record(call)
    return result


@contextlib.contextmanager
def controlled(seed: int | None = None):
    """Replace numpy's two sampling functions inside the block, then restore them."""
    if seed is not None:
        np.random.seed(seed)
    np.random.normal = normal
    np.random.multivariate_normal = multivariate_normal
    try:
        yield
    finally:
        np.random.normal = _numpy_normal
        np.random.multivariate_normal = _numpy_mvn


def event_seed(*parts) -> int:
    """A stable seed for one simulated event (the same parts give the same draws)."""
    text = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "little")
