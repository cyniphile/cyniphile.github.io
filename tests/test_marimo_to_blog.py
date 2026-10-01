"""End-to-end: convert a small notebook with each supported widget kind."""

import json
import re
import shutil
from pathlib import Path

import pytest

import marimo_to_blog

FIXTURE = Path(__file__).parent / "fixtures" / "marimo" / "mini"


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    post = tmp_path_factory.mktemp("post")
    for name in ("notebook.py", "post.yml"):
        shutil.copy(FIXTURE / name, post / name)
    page = marimo_to_blog.convert(post)
    qmd = (post / "index.qmd").read_text()
    model = json.loads(re.search(r'<script type="application/json" id="mb-model">(.*?)</script>', qmd).group(1))
    groups = {gid: json.loads((post / info["src"]).read_text()) for gid, info in model["groups"].items()}
    return post, page, qmd, model, groups


def group_of(model, groups, control):
    return groups[model["controls"][control]["group"]]


def test_front_matter_markdown_and_runtime(converted):
    post, page, qmd, model, _ = converted
    assert qmd.startswith("---\ntitle: Mini notebook\n")
    assert "resources:\n- widgets/*.json" in qmd
    assert "Some math: $x^2$." in qmd and "# Mini notebook" not in qmd  # the title heading goes
    assert '<script type="module" src="/assets/mb/mb.js"></script>' in qmd
    assert marimo_to_blog.up_to_date(post)
    assert not page.warnings


def test_controls(converted):
    _, _, _, model, _ = converted
    kinds = {name: spec["kind"] for name, spec in model["controls"].items()}
    assert kinds == {"size": "slider", "new": "button", "reset": "button", "mat": "matrix", "editor": "editor"}
    assert model["controls"]["size"]["values"] == [1, 2, 3, 4]


def test_reactive_slider_states(converted):
    _, _, _, model, groups = converted
    group = group_of(model, groups, "size")
    assert group["kind"] == "table" and group["sliders"] == ["size"]
    assert set(group["states"]) == {"0", "1", "2", "3"}
    (cell, change), = group["states"]["3"].items()
    ops = change["figures"]["0"]
    # no reset (it would remove click history that marimo keeps): each changed path is set
    assert all(op["op"] != "reset" for op in ops)
    assert {"op": "set", "path": ["layout", "title", "text"], "value": "size=4"} in ops
    (change,) = group["states"]["1"].values()  # back at the default value
    assert {"op": "set", "path": ["layout", "title", "text"], "value": "size=2"} in change["figures"]["0"]


def test_buttons(converted):
    _, _, _, model, groups = converted
    group = group_of(model, groups, "new")
    new, reset = group["buttons"]["new"], group["buttons"]["reset"]
    assert new["kind"] == "list" and new["pool"] == 20 and new["keys"] == []
    clicks = new["table"][""]
    assert len(clicks) == 20
    (change,) = clicks[0].values()
    assert change["figures"]["0"][0]["op"] == "add"
    assert reset["kind"] == "fixed" and reset["keys"] == [] and reset["resets"] == ["new"]
    (change,) = reset["table"][""].values()
    assert change["figures"]["0"] == [{"op": "truncate", "n": 1}]


def test_matrix_sampler(converted):
    _, _, _, model, groups = converted
    group = group_of(model, groups, "mat")
    assert group["kind"] == "sampler"
    assert group["mean"] == {"value": [0, 0]} and group["cov"] == {"control": "mat"}
    assert group["target"]["fields"] == ["x", "y"] and len(group["z"]) == 50
    assert group["check"] == "raise" and "Error" in group["error"]["html"]


def test_live_editor(converted):
    _, _, _, model, groups = converted
    group = group_of(model, groups, "editor")
    assert group["kind"] == "live" and group["editor"] == "editor"
    assert [cell for cell, _ in group["run"]] == [str(c) for c in group["cells"]]
    assert "import plotly.graph_objects as go" in group["setup"]
    assert "pandas" not in group["setup"] and "altair" not in group["setup"]
    assert any(p.startswith("plotly==") for p in group["packages"])
