"""Sampler groups: matrix inputs whose values feed np.random.multivariate_normal directly.

Matrix values are continuous, so their states cannot be precomputed. The converter checks that
the cell output depends on the matrices only through one multivariate_normal call (mean and
covariance equal to matrix values), and finds where its samples go in the output (a Vega-Lite
dataset or Plotly arrays). The browser then computes the samples again from the recorded draws:
mean + z @ sqrt_factor(cov), the same method as rng.py. If the call checks the covariance
(check_valid="raise") and the matrix is not valid, the cell shows its recorded error state.
"""

from __future__ import annotations

import copy

import numpy as np

from . import ops as O
from . import rng
from .model import UnsupportedGroup, cell_payload


def _matrix_value(spec: dict, variant: int) -> list[list[float]]:
    """A valid value different from the default: a larger diagonal, a small off-diagonal."""
    value = [[float(v) for v in row] for row in spec["value"]]
    rows, cols = len(value), len(value[0])
    step = _step(spec)
    for i in range(min(rows, cols)):
        value[i][i] = round(value[i][i] + variant * step * (i + 2), 10)
    if rows == cols and rows > 1:
        off = round(step * variant, 10)
        value[0][1] = round(value[0][1] + off, 10)
        if spec.get("symmetric"):
            value[1][0] = value[0][1]
    return _clamped(value, spec)


def _invalid_cov(spec: dict) -> list[list[float]]:
    """A symmetric matrix that is not positive semi-definite (inside the input's limits)."""
    value = [[float(v) for v in row] for row in spec["value"]]
    n = len(value)
    big = max(1.0, max(abs(value[i][i]) for i in range(n))) * 2 + 1
    for i in range(n):
        for j in range(n):
            if i != j:
                value[i][j] = big
    return _clamped(value, spec)


def _step(spec: dict) -> float:
    step = spec.get("step")
    while isinstance(step, list):
        step = step[0]
    return float(step or 0.1)


def _clamped(value, spec):
    lows, highs = spec.get("min"), spec.get("max")
    for i, row in enumerate(value):
        for j, v in enumerate(row):
            low = lows[i][j] if isinstance(lows, list) else lows
            high = highs[i][j] if isinstance(highs, list) else highs
            if low is not None:
                v = max(v, float(low))
            if high is not None:
                v = min(v, float(high))
            row[j] = v
    return value


def _columns_equal(values: list, column: np.ndarray) -> bool:
    """The output values are the column (both were rounded, maybe in different ways)."""
    if len(values) != len(column) or any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in values):
        return False
    scale = max(1e-12, float(np.abs(column).max()))
    return bool(np.allclose(np.asarray(values, dtype=float), column, rtol=0, atol=scale * 2e-4))


def _data_refs(spec, name: str, path: tuple = ()) -> list[list]:
    """Paths of the {"name": <dataset>} references to a named dataset in a Vega-Lite spec."""
    refs = []
    if isinstance(spec, dict):
        if path and path[-1] == "data" and spec.get("name") == name:
            refs.append(list(path))
        for key, value in spec.items():
            if key != "datasets":
                refs += _data_refs(value, name, (*path, key))
    elif isinstance(spec, list):
        for i, value in enumerate(spec):
            refs += _data_refs(value, name, (*path, i))
    return refs


def _find_target(rendered, samples: np.ndarray) -> dict | None:
    """Where the sample columns are in the output: a chart dataset or figure arrays.

    Altair names a dataset by a hash of its values, so a chart target is the place where the
    chart uses the dataset (refs), not the name; "dataset" is the name in this output."""
    n, d = samples.shape
    for number, chart in enumerate(rendered.charts):
        for name, rows in (chart.get("datasets") or {}).items():
            if not isinstance(rows, list) or len(rows) != n or not rows or not isinstance(rows[0], dict):
                continue
            fields = []
            for j in range(d):
                match = [f for f in rows[0] if _columns_equal([r.get(f) for r in rows], samples[:, j])]
                if not match:
                    break
                fields.append(match[0])
            if len(fields) == d:
                return {"chart": number, "refs": _data_refs(chart, name), "fields": fields, "dataset": name}
    for number, fig in enumerate(rendered.figures):
        paths = []
        for j in range(d):
            for t, trace in enumerate(fig["figure"].get("data", [])):
                key = next((k for k, v in trace.items() if isinstance(v, list) and len(v) == n
                            and _columns_equal(v, samples[:, j])), None)
                if key:
                    paths.append(["data", t, key])
                    break
        if len(paths) == d:
            return {"figure": number, "paths": paths}
    return None


def _without_target(rendered, target: dict):
    """The output with the sample values taken out, to check that nothing else depends on them."""
    copy_out = copy.deepcopy(rendered)
    if "chart" in target:
        chart = copy_out.charts[target["chart"]]
        chart["datasets"].pop(target["dataset"], None)
        for path in target["refs"]:
            node = chart
            for key in path:
                node = node[key]
            node["name"] = "$samples"
    else:
        fig = copy_out.figures[target["figure"]]["figure"]
        for path in target["paths"]:
            parent = fig
            for key in path[:-1]:
                parent = parent[key]
            parent[path[-1]] = None
    return copy_out.html, copy_out.charts, copy_out.figures


def sampler_group(builder, gid: str, group: dict) -> dict:
    s, controls = builder.s, builder.page.controls
    names = group["controls"]
    if any(controls[n]["kind"] != "matrix" for n in names):
        raise UnsupportedGroup("matrix inputs together with other controls")
    cells = sorted(group["cells"])
    if len(cells) != 1:
        raise UnsupportedGroup("matrix inputs that change more than one cell")
    cell = cells[0]

    probes = []
    for variant in (1, 2):
        s.restore(builder.base)
        values = {n: _matrix_value(controls[n], variant) for n in names}
        for n in names[:-1]:
            s.set_value(n, values[n], seed=rng.event_seed(gid))
        with rng.recording() as recorder:
            s.set_value(names[-1], values[names[-1]], seed=rng.event_seed(gid))
        calls = [c for c in recorder.calls if c.fn == "multivariate_normal" and c.result is not None]
        if len(calls) != 1:
            raise UnsupportedGroup(f"{len(calls)} multivariate_normal calls (exactly 1 is supported)")
        probes.append((values, calls[0], builder.rendered(cell)))

    roles = {}
    for name in names:
        for role in ("mean", "cov"):
            if all(np.allclose(np.asarray(values[name], dtype=float).reshape(np.shape(call.params[role])),
                               call.params[role]) if np.size(values[name]) == np.size(call.params[role]) else False
                   for values, call, _ in probes):
                roles[role] = name
    if "cov" not in roles:
        raise UnsupportedGroup("the covariance is not a matrix input value")
    mean = {"control": roles["mean"]} if "mean" in roles else {"value": O.compact(probes[0][1].params["mean"])}

    samples = [np.asarray(call.result).reshape(-1, call.result.shape[-1]) for _, call, _ in probes]
    targets = [_find_target(out, sample) for (_, _, out), sample in zip(probes, samples)]

    def place(target):  # a target without the dataset name (which changes with the values)
        return None if target is None else {k: v for k, v in target.items() if k != "dataset"}

    if targets[0] is None or place(targets[0]) != place(targets[1]):
        raise UnsupportedGroup("the samples are not found in the output")

    # The page shows the cell as after an event at the default values: it then uses the same draws
    # as the browser, so the browser's samples agree with the page at the default values.
    s.restore(builder.base)
    with rng.recording() as recorder:
        s.set_value(names[-1], controls[names[-1]]["value"], seed=rng.event_seed(gid))
    default_out = builder.rendered(cell)
    default_calls = [c for c in recorder.calls if c.fn == "multivariate_normal" and c.result is not None]
    target = None if default_out is None or len(default_calls) != 1 else _find_target(
        default_out, np.asarray(default_calls[0].result).reshape(samples[0].shape))
    if target is None or place(target) != place(targets[0]):
        raise UnsupportedGroup("the output does not have the same form at the default values")
    rest = [_without_target(out, t) for (_, _, out), t in zip(probes, targets)]
    if rest[0] != rest[1] or rest[0] != _without_target(default_out, target):
        raise UnsupportedGroup("other parts of the output change with the matrices")
    builder.set_default(cell, default_out)

    call = probes[0][1]
    s.restore(builder.base)
    with rng.recording() as recorder:
        s.set_value(roles["cov"], _invalid_cov(controls[roles["cov"]]), seed=rng.event_seed(gid))
    raises = any(c.fn == "multivariate_normal" and c.error for c in recorder.calls)
    return {
        "kind": "sampler",
        "cell": cell,
        "cells": cells,
        "mean": mean,
        "cov": {"control": roles["cov"]},
        "z": O.compact(np.asarray(call.z).tolist()),
        "check": "raise" if raises else "warn",
        "target": target,
        "error": cell_payload(builder.rendered(cell)) if raises else None,
    }
