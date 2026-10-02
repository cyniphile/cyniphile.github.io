"""Unit tests for the marimo → blog converter (no notebook run)."""

import base64
import json
import warnings

import numpy as np
import pytest

from marimo_blog import emit as E
from marimo_blog import html as H
from marimo_blog import model as M
from marimo_blog import ops as O
from marimo_blog import rng


# ---- rng ----

def test_normal_gives_numpy_legacy_values():
    np.random.seed(7)
    expected = np.random.normal(1.5, 2.0, size=6)
    np.random.seed(7)
    assert np.allclose(rng.normal(1.5, 2.0, size=6), expected)


def test_normal_with_array_parameters_and_no_size():
    np.random.seed(3)
    expected = np.random.normal([0.0, 10.0], [1.0, 2.0])
    np.random.seed(3)
    assert np.allclose(rng.normal([0.0, 10.0], [1.0, 2.0]), expected)


def test_normal_scalar_returns_a_float_and_rejects_negative_scale():
    assert isinstance(rng.normal(0.0, 1.0), float)
    with pytest.raises(ValueError, match="scale < 0"):
        rng.normal(0.0, -1.0, size=2)


def test_multivariate_normal_shape_mean_and_covariance():
    np.random.seed(0)
    cov = [[2.0, 0.6], [0.6, 1.0]]
    x = rng.multivariate_normal([1.0, -2.0], cov, size=20000)
    assert x.shape == (20000, 2)
    assert np.allclose(x.mean(axis=0), [1.0, -2.0], atol=0.05)
    assert np.allclose(np.cov(x.T), cov, atol=0.06)


def test_multivariate_normal_records_draws_that_repeat_the_result():
    np.random.seed(1)
    with rng.recording() as recorder:
        x = rng.multivariate_normal([0.5, 0.0], [[1.2, 0.1], [0.1, 1.3]], size=4)
    call = recorder.calls[0]
    assert np.allclose(call.z @ rng.sqrt_factor(call.params["cov"]) + call.params["mean"], x)


def test_multivariate_normal_invalid_covariance():
    bad = [[1.0, 2.0], [2.0, 1.0]]
    with pytest.raises(ValueError, match="positive-semidefinite"):
        rng.multivariate_normal([0.0, 0.0], bad, size=3, check_valid="raise")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rng.multivariate_normal([0.0, 0.0], bad, size=3)
    assert any("positive-semidefinite" in str(w.message) for w in caught)


def test_is_psd_and_sqrt_factor():
    assert rng.is_psd([[1.0, 1.0], [1.0, 1.0]])  # singular is valid
    assert not rng.is_psd([[0.5, 0.6], [0.6, 0.7]])
    assert not rng.is_psd([[1.0, 0.2], [0.1, 1.0]])  # not symmetric
    cov = np.array([[4.0, 2.0, 0.6], [2.0, 2.0, 0.4], [0.6, 0.4, 3.0]])
    f = rng.sqrt_factor(cov)
    assert np.allclose(f.T @ f, cov)


def test_jacobi_matches_numpy_eigenvalues():
    cov = np.array([[4.0, 2.0, 0.6], [2.0, 2.0, 0.4], [0.6, 0.4, 3.0]])
    values, vectors = rng.jacobi_eigh(cov)
    assert np.allclose(sorted(values), np.linalg.eigvalsh(cov))
    assert np.allclose(vectors @ np.diag(values) @ vectors.T, cov)


def test_controlled_restores_numpy():
    original = np.random.normal
    with rng.controlled(seed=1):
        assert np.random.normal is rng.normal
    assert np.random.normal is original


def test_event_seed_is_stable():
    assert rng.event_seed("g1", "slider") == rng.event_seed("g1", "slider")
    assert rng.event_seed("g1", "a") != rng.event_seed("g1", "b")


# ---- ops ----

def test_decode_plotly_binary_arrays():
    values = np.arange(6, dtype="f8").reshape(2, 3)
    packed = {"dtype": "f8", "bdata": base64.b64encode(values.tobytes()).decode(), "shape": "2, 3"}
    assert O.decode({"z": packed}) == {"z": values.tolist()}


def test_compact_rounds_arrays_to_their_largest_value():
    assert O.compact([1.0, 0.123456789, 1.2e-15]) == [1, 0.1235, 0]
    assert O.compact([[300000.123, 1.0]]) == [[300000, 0]]
    assert O.compact([1.0, 1.2e-15], relative=False) == [1, 1.2e-15]
    log_fig = {"data": [{"y": [1e-6, 1.0]}], "layout": {"yaxis": {"type": "log"}}}
    assert O.compact_figure(log_fig)["data"][0]["y"] == [1e-6, 1]
    assert O.compact({"a": np.float64(1.23456789), "b": np.int64(3), "c": np.bool_(True)}) == \
        {"a": 1.2346, "b": 3, "c": True}
    assert O.compact([float("nan"), 1.0]) == [None, 1]


def _fig(*traces, **layout):
    return {"data": [dict(t) for t in traces], "layout": dict(layout)}


def test_figure_ops_append_truncate_restyle_and_layout():
    a = _fig({"y": [1]}, height=300)
    b = _fig({"y": [1]}, {"y": [2]}, height=350)
    ops = O.figure_ops(a, b)
    assert ops[0] == {"op": "add", "traces": [{"y": [2]}]}
    assert O.apply(a, ops) == b
    assert O.figure_ops(b, _fig({"y": [1]}, height=350)) == [{"op": "truncate", "n": 1}]
    connected = _fig({"y": [1], "mode": "lines"}, {"y": [2], "mode": "lines"}, height=350)
    assert O.figure_ops(b, connected) == [{"op": "restyle_all", "style": {"mode": "lines"}}]


def test_figure_ops_other_changes_round_trip():
    a = _fig({"z": [[1, 2]], "name": "a"}, title={"text": "x"})
    b = _fig({"z": [[1, 3]], "name": "a"}, title={"text": "y"}, width=400)
    assert O.apply(a, O.figure_ops(a, b)) == b


def test_reset_ops_go_back_to_the_default_first():
    default = _fig({"y": [1]})
    state = _fig({"y": [5]})
    current = _fig({"y": [1]}, {"y": [9]})
    assert O.apply(current, O.reset_ops(default, state), default) == state


# ---- html ----

def _ui(object_id, inner):
    return f"<marimo-ui-element object-id='{object_id}' random-id='r'>{inner}</marimo-ui-element>"


def _attr(value):
    return json.dumps(value).replace("&", "&amp;").replace("'", "&#39;").replace('"', "&quot;")


def test_render_replaces_marimo_elements():
    fig = {"data": [{"y": [1, 2]}], "layout": {}}
    html = (
        "<div style='display: flex'>"
        + _ui("p", f"<marimo-plotly data-figure='{_attr(fig)}' data-config='{_attr({'staticPlot': True})}'></marimo-plotly>")
        + _ui("b", f"<marimo-button data-label='{_attr('<span>New Sample</span>')}' data-kind='{_attr('success')}'></marimo-button>")
        + _ui("s", "<marimo-slider data-start='1' data-stop='3' data-step='1' data-initial-value='2' "
                   f"data-label='{_attr('Size')}' data-debounce='true'></marimo-slider>")
        + "<span class=\"paragraph\">Text <marimo-tex class='arithmatex'>||(x^2||)</marimo-tex></span>"
        + "</div>"
    )
    names = {"b": "new", "s": "size"}
    out = H.render(html, names.get)
    assert out.figures == [{"figure": fig, "config": {"staticPlot": True}}]
    assert [(c["kind"], c["name"]) for c in out.controls] == [("button", "new"), ("slider", "size")]
    assert out.controls[0]["label"] == "New Sample" and out.controls[0]["kind_style"] == "success"
    assert out.controls[1]["values"] == [1, 2, 3] and out.controls[1]["index"] == 1
    assert 'class="mb-plot" data-fig="0"' in out.html
    assert 'data-control="new"' in out.html and 'data-control="size"' in out.html
    assert '<span class="math inline">x^2</span>' in out.html and "<p>" in out.html
    assert "marimo-" not in out.html


def test_render_shown_code_and_editor():
    code = _ui("c", f"<marimo-code-editor data-initial-value='{_attr('x = 1')}' data-disabled='true'></marimo-code-editor>")
    assert H.render(code, lambda _: None).code == "x = 1"
    editor = _ui("e", f"<marimo-code-editor data-initial-value='{_attr('y = 2')}' data-disabled='false'></marimo-code-editor>")
    out = H.render(editor, {"e": "editor"}.get)
    assert out.code is None and out.controls[0]["kind"] == "editor" and out.controls[0]["value"] == "y = 2"


def test_render_vega_chart_and_unknown_elements():
    spec = {"$schema": "https://vega.github.io/schema/vega-lite/v6.json", "mark": "point"}
    html = (f"<marimo-mime-renderer data-mime='{_attr('application/vnd.vegalite.v6+json')}' "
            f"data-data='{_attr(json.dumps(spec))}'></marimo-mime-renderer><marimo-thing></marimo-thing>")
    out = H.render(html, lambda _: None)
    assert out.charts == [spec] and 'class="mb-chart"' in out.html
    assert any("marimo-thing" in w for w in out.warnings)


def test_slider_values():
    assert H.slider_values({"start": 1, "stop": 30}) == list(range(1, 31))
    values = H.slider_values({"start": -5, "stop": 5, "step": 0.1})
    assert len(values) == 101 and values[0] == -5 and values[50] == 0 and values[-1] == 5
    assert H.slider_values({"start": 0.01, "stop": 2.0, "step": 0.01})[-1] == 2.0
    assert H.slider_values({"start": 0, "stop": 1, "steps": [0, 0.5, 1]}) == [0, 0.5, 1]


# ---- model and emit helpers ----

def test_markdown_of_only_takes_literal_md_cells():
    assert M.markdown_of('mo.md(r"""\n    # Title\n\n    Text\n    """)') == "# Title\n\nText"
    assert M.markdown_of('mo.md(f"{x}")') is None
    assert M.markdown_of("x = 1\nmo.md('a')") is None


def test_post_markdown_headings():
    assert E.post_markdown("# Title\n\nText\n\n# Part", "Title", first=True) == "Text\n\n## Part"
    assert E.post_markdown("# Other\n## Sub", "Title", first=True) == "## Other\n## Sub"


def test_share_arrays_and_templates():
    row = list(range(20))
    shared, table = E.share_arrays({"a": row, "b": [row, list(range(30))]})
    assert shared["a"] == shared["b"][0] and len(table) == 1
    templates = {}
    out = E.share_templates({"layout": {"template": {"layout": {"font": {}}}}}, templates)
    assert list(out["layout"]["template"]) == ["$template"] and len(templates) == 1


def test_trace_types_and_plotly_bundle():
    figs = {"data": [{"type": "heatmap"}, {"y": [1]}], "group": {"ops": [{"op": "add", "traces": [{"type": "histogram"}]}]}}
    assert E.trace_types(figs) == {"heatmap", "scatter", "histogram"}
    assert E.plotly_bundle({"scatter", "bar"}) == "basic"
    assert E.plotly_bundle({"scatter", "heatmap", "histogram"}) == "cartesian"
    assert E.plotly_bundle({"scatter3d"}) == "full"


def test_project_links_and_blog_base(tmp_path):
    text = 'See the [live notebook](/blog/gp/live/) and [x](https://a.b/blog/c) <a href="/blog/gp/">p</a>'
    assert E.project_links(text, "/blog") == \
        'See the [live notebook](/gp/live/) and [x](https://a.b/blog/c) <a href="/gp/">p</a>'
    assert E.project_links(text, "") == text
    (tmp_path / "_quarto.yml").write_text("website:\n  site-url: https://www.example.com/blog\n")
    (tmp_path / "post").mkdir()
    assert E.blog_base(tmp_path / "post") == "/blog"
    assert E.blog_base(tmp_path / "missing" / "post") == ""


def test_post_markdown_keeps_comments_in_code_blocks():
    text = "Intro\n\n```python\n# a comment\nx = 1\n```\n\n# Part"
    assert E.post_markdown(text, "T", first=True) == "Intro\n\n```python\n# a comment\nx = 1\n```\n\n## Part"


def test_render_altair_chart_element_and_unknown_elements():
    spec = {"mark": "point"}
    html = (_ui("v", f"<marimo-vega data-spec='{_attr(json.dumps(spec))}'></marimo-vega>")
            + "<marimo-tabs><p>first tab</p></marimo-tabs>")
    out = H.render(html, lambda _: None)
    assert out.charts == [spec] and 'class="mb-chart"' in out.html
    assert "<p>first tab</p>" in out.html and "marimo-" not in out.html  # content stays, without interaction
    assert len(out.warnings) == 2


def test_apply_makes_missing_parents_and_ignores_missing_deletes():
    fig = {"data": [], "layout": {}}
    ops = [{"op": "set", "path": ["layout", "title", "text"], "value": "t"},
           {"op": "del", "path": ["layout", "xaxis", "range"]}]
    assert O.apply(fig, ops) == {"data": [], "layout": {"title": {"text": "t"}}}


def test_filled_ops_set_every_changed_path():
    default = {"layout": {"title": {"text": "d"}}, "data": [{"y": [1]}]}
    paths = {("layout", "title", "text"), ("data", 0, "y"), ("layout", "width")}
    own = [{"op": "set", "path": ["data", 0, "y"], "value": [5]}]
    ops = O.filled_ops(default, own, paths)
    current = {"layout": {"title": {"text": "x"}, "width": 3}, "data": [{"y": [9]}, {"y": [7]}]}  # 2nd: a click
    assert O.apply(current, ops) == {"layout": {"title": {"text": "d"}}, "data": [{"y": [5]}, {"y": [7]}]}


def test_invalid_cov_respects_bounds():
    from marimo_blog import sampler as S
    spec = {"value": [[1.0, 0.0], [0.0, 1.0]], "step": [[0.1, 0.1], [0.1, 0.1]], "min": [[0, 0], [0, 0]],
            "max": [[1, 1], [1, 1]], "symmetric": True}
    invalid = S._invalid_cov(spec)
    assert invalid is not None and not rng.is_psd(invalid) and all(0 <= v <= 1 for row in invalid for v in row)
    assert S._invalid_cov({**spec, "max": [[1, 0], [0, 1]]}) is None  # only diagonal matrices: always valid


def test_sampler_target_keeps_constant_fields():
    from marimo_blog import sampler as S
    samples = np.array([[1.0, 2.0], [3.0, 4.0]])
    rows = [{"x": 1.0, "y": 2.0, "kind": "sim"}, {"x": 3.0, "y": 4.0, "kind": "sim"}]
    out = H.Rendered(html="", charts=[{"datasets": {"d": rows}, "layer": [{"data": {"name": "d"}}]}])
    target = S._find_target(out, samples)
    assert target["fields"] == ["x", "y"] and target["extra"] == {"kind": "sim"}
    rows[1]["kind"] = "other"
    assert S._find_target(out, samples) is None  # a field that changes from row to row: not supported


def test_verify_reports_a_wrong_state(tmp_path):
    import copy
    from pathlib import Path as P
    from marimo_blog import verify as V
    from marimo_blog.runner import Session
    path = P(__file__).parent / "fixtures" / "marimo" / "mini" / "notebook.py"
    with Session(path) as session:
        page = M.build(session)
    assert V.verify(path, page) == []
    broken = copy.deepcopy(page)
    gid = broken.controls["size"]["group"]
    for key in broken.groups[gid]["states"]:
        broken.groups[gid]["states"][key] = {}  # slider moves that do nothing
    assert any("differs" in p or "in the blog" in p for p in V.verify(path, broken))


def test_label_math_is_rendered_by_the_runtime_not_by_quarto():
    label = '<span class="markdown"><span class="paragraph">Scale <marimo-tex>||(\\ell||)</marimo-tex></span></span>'
    assert H.label_html(label) == 'Scale <span class="mb-math inline">\\ell</span>'


def test_live_stand_in_blocks_only_the_users_of_a_failed_cell():
    from marimo_blog import live
    mb_live = live.load_mb_live()
    spec = {"editor": "ed", "setup": "", "run": [
        ["1", "x = int(ed.value)", ["ed"], ["x"]],
        ["2", "y = x + 1", ["x"], ["y"]],
        ["3", "z = y * 2", ["y"], ["z"]],
        ["4", "len(ed.value)", ["ed"], []],
    ]}
    mb_live.configure(json.dumps(spec))
    results = json.loads(mb_live.run("oops"))
    assert results["1"]["kind"] == "error" and "ValueError" in results["1"]["text"]
    assert results["2"]["text"] == results["3"]["text"] == "An ancestor raised an exception (ValueError)"
    assert results["4"] == {"kind": "html", "html": "<pre>4</pre>"}
    assert json.loads(mb_live.run("2"))["3"] == {"kind": "html", "html": ""}
