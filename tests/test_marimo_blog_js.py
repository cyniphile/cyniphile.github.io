"""The browser runtime's pure functions (mb-core.js) give the same results as the Python side."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from marimo_blog import ops as O
from marimo_blog import rng

CORE = Path(__file__).resolve().parents[1] / "blog" / "assets" / "mb" / "mb-core.js"
SCRIPT = """
import * as core from %s;
let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  const c = JSON.parse(input);
  const out = {
    mvn: c.mvn.map((x) => ({ eig: core.jacobiEigh(x.cov), psd: core.isPsd(x.cov),
                             factor: core.sqrtFactor(x.cov), samples: core.mvnSamples(x.mean, x.cov, x.z) })),
    ops: c.ops.map((x) => core.applyOps(x.figure, x.ops, x.default)),
    normal: c.normal.map((x) => core.normal(x.loc, x.scale, x.z)),
    drag: c.drag.map((args) => core.dragValue(...args)),
    resolve: core.resolve(c.resolve.value, c.resolve.tables),
  };
  process.stdout.write(JSON.stringify(out));
});
"""

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

COVS = [
    [[1.0, 0.0], [0.0, 1.0]],
    [[1.2, 0.1], [0.1, 1.3]],
    [[2.0, 1.9], [1.9, 2.0]],
    [[1.0, 1.0], [1.0, 1.0]],
    [[1.0, 2.0], [2.0, 1.0]],
    [[0.5, 0.6], [0.6, 0.7]],
    [[4.0, 2.0, 0.6], [2.0, 2.0, 0.4], [0.6, 0.4, 3.0]],
]


def run_node(cases: dict) -> dict:
    proc = subprocess.run(["node", "--input-type=module", "-e", SCRIPT % json.dumps(CORE.as_uri())],
                          input=json.dumps(cases), capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def test_js_core_matches_python():
    z_rng = np.random.default_rng(0)
    mvn = [{"cov": cov, "mean": [0.5] * len(cov), "z": z_rng.standard_normal((6, len(cov))).tolist()} for cov in COVS]
    fig = {"data": [{"y": [1, 2]}], "layout": {"height": 300}}
    ops_cases = [
        {"figure": fig, "default": fig, "ops": [{"op": "add", "traces": [{"y": [3]}]},
                                                {"op": "set", "path": ["layout", "height"], "value": 350}]},
        {"figure": fig, "default": fig, "ops": [{"op": "restyle_all", "style": {"mode": "lines"}},
                                                {"op": "truncate", "n": 0}]},
        {"figure": {"data": [], "layout": {}}, "default": fig,
         "ops": [{"op": "reset"}, {"op": "del", "path": ["layout", "height"]}]},
    ]
    normal = [{"loc": 1.5, "scale": 2.0, "z": [0.0, 1.0, -1.0]}, {"loc": [0, 10], "scale": [1, 2], "z": [1.0, 1.0]}]
    drag = [[1.0, 20, 0.1, 0, None], [1.0, -200, 0.1, 0, None], [0.5, 4, 0.1, None, 0.5], [2, 37, 1, None, None]]
    resolve = {"value": {"y": {"$a": "k"}, "x": {"$normal": {"loc": 1, "scale": 2, "z": "p"}},
                         "t": {"$template": "t1"}},
               "tables": {"arrays": {"k": [1, 2]}, "pools": {"p": [0.5, -0.5]}, "templates": {"t1": {"layout": {}}}}}
    out = run_node({"mvn": mvn, "ops": ops_cases, "normal": normal, "drag": drag, "resolve": resolve})

    for case, js in zip(mvn, out["mvn"]):
        values, vectors = rng.jacobi_eigh(case["cov"])
        assert np.allclose(js["eig"]["values"], values, atol=1e-12)
        assert np.allclose(js["eig"]["vectors"], vectors, atol=1e-12)
        assert js["psd"] == rng.is_psd(case["cov"])
        factor = rng.sqrt_factor(case["cov"])
        assert np.allclose(js["factor"], factor, atol=1e-12)
        assert np.allclose(js["samples"], np.asarray(case["z"]) @ factor + case["mean"], atol=1e-12)
    for case, js in zip(ops_cases, out["ops"]):
        assert js == O.apply(case["figure"], case["ops"], case["default"])
    assert out["normal"] == [[1.5, 3.5, -0.5], [1, 12]]
    assert out["drag"] == [1.2, 0, 0.5, 6]
    assert out["resolve"] == {"y": [1, 2], "x": [2, 0], "t": {"layout": {}}}
